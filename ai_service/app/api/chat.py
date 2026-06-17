import json
import logging
import base64
import re
import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.rag_service import (
    get_retriever,
    get_chain,
    format_docs,
    format_history,
)
from app.services.tts_service import synthesize_speech
from app.services.chat_history_service import (
    get_recent_history,
    merge_history,
    save_exchange,
    save_message,
)
from app.services.metrics_service import record_metric
from typing import AsyncIterator, Any
from app.services.auth_service import get_current_user, get_current_user_optional, DummyUser

class ChatHistoryMessage(BaseModel):
    role: str
    content: str

class SaveMessageRequest(BaseModel):
    course_id: str = "default"
    role: str
    content: str

logger = logging.getLogger(__name__)
router = APIRouter()

# На главной (default) RAG по коллекции часто подмешивает случайные чанки (в т.ч. «приветствия») —
# модель начинает их повторять. Там достаточно списка курсов из промпта.
_GLOBAL_HOME_CONTEXT = (
    "Ты на главной странице платформы. "
    "На привет и «как дела?» отвечай по-человечески своими словами, не зеркаль вопрос. "
    "Переход на курс — только после согласия; в вопросе назови полное название курса. "
    "На первую просьбу «переведи/открой курс» тег [NAVIGATE:/courses/…] не ставь. "
    "Переход на главную по просьбе — можно сразу [NAVIGATE:/]."
)


async def retrieve_context_for_chat(message: str, course_id: str):
    if course_id == settings.DEFAULT_COURSE_ID:
        return [], _GLOBAL_HOME_CONTEXT, []
    retriever = get_retriever(course_id)
    source_docs = await retriever.ainvoke(message)
    sources = list(
        {doc.metadata.get("source", "") for doc in source_docs if doc.metadata.get("source")}
    )
    context = format_docs(source_docs)
    return source_docs, context, sources


_ACTION_RE = re.compile(r'\[(NAVIGATE|SHOW_COURSES):([^\]]*)\]', re.IGNORECASE)

# Тег подсветки фрагмента на странице урока: [HIGHLIGHT:дословная цитата]
_HIGHLIGHT_RE = re.compile(r'\[HIGHLIGHT:([^\]]*)\]', re.IGNORECASE)

def _normalize_nav_path(path: str) -> str:
    from app.services.navigation_service import normalize_nav_path
    return normalize_nav_path(path) or "/"


def _process_navigate_action(
    raw_path: str,
    page_context: dict,
    current_course_id: str | None = None,
) -> tuple[str | None, str | None, list | None]:
    """Валидация [NAVIGATE:...] по списку курсов из виджета платформы."""
    from app.services.navigation_service import CourseNavItem, validate_navigate_path

    available = (page_context or {}).get("available_courses") or []
    courses = [CourseNavItem.from_dict(c) for c in available if isinstance(c, dict) and c.get("id")]
    if not courses:
        # Нет списка с виджета — только нормализация (обратная совместимость)
        return "navigate", _normalize_nav_path(raw_path), None

    res = validate_navigate_path(raw_path, courses)
    if res.status in ("ok", "static") and res.path:
        # ЖЁСТКИЙ СТОРОЖ: внутри курса блокируем переход на ДРУГОЙ курс,
        # даже если модель поставила тег [NAVIGATE:/courses/<чужой_id>].
        # Статические пути (/, /profile, /journal, …) и тот же курс — разрешены.
        if current_course_id and current_course_id != settings.DEFAULT_COURSE_ID:
            target_course = res.course_id
            if not target_course:
                m = re.match(r"^/courses/([^/?]+)", res.path)
                if m:
                    target_course = m.group(1)
            if target_course and target_course != current_course_id:
                logger.info(
                    "Blocked cross-course NAVIGATE: %r (current=%s, target=%s)",
                    raw_path, current_course_id, target_course,
                )
                return None, None, None
        return "navigate", res.path, None
    if res.status == "ambiguous":
        return "show_courses", raw_path, res.matches
    logger.info("Navigation rejected: %s → %s", raw_path, res.message)
    return None, None, None
# Регулярка для разбивки на предложения
_SENTENCE_RE = re.compile(r'(?<=[.!?\n])\s+')


class HistoryMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []
    voice: bool = False
    course_id: str = settings.DEFAULT_COURSE_ID
    course_name: str = ""
    page_context: dict = {}


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []

def _strip_nav_tags(text: str) -> str:
    """Удаляет экшен-теги ([NAVIGATE:...], [SHOW_COURSES:...], [HIGHLIGHT:...]) из отображаемого текста."""
    text = _ACTION_RE.sub('', text)
    text = _HIGHLIGHT_RE.sub('', text)
    return text.strip()

async def _stream_tokens(chain, inputs: dict, page_context: dict | None = None, current_course_id: str | None = None):
    """Генератор токенов с обработкой экшен-тегов."""
    full_response = ""
    display_buffer = ""
    nav_buffer = ""        # накапливаем потенциальный тег
    in_nav_tag = False     # находимся внутри [TAG:...]

    async for token in chain.astream(inputs):
        full_response += token

        # Обрабатываем токен посимвольно для надёжного перехвата тегов
        for ch in token:
            if not in_nav_tag:
                if ch == '[':
                    # Возможное начало тега — сначала сбрасываем буфер
                    if display_buffer:
                        yield ('token', display_buffer)
                        display_buffer = ""
                    in_nav_tag = True
                    nav_buffer = '['
                else:
                    display_buffer += ch
            else:
                nav_buffer += ch
                if ch == ']':
                    # Конец тега
                    in_nav_tag = False
                    match = _ACTION_RE.match(nav_buffer)
                    if match:
                        action_type = match.group(1).upper()
                        val = match.group(2)
                        if action_type == 'NAVIGATE':
                            nav_kind, nav_val, _extra = _process_navigate_action(val, page_context or {}, current_course_id)
                            if nav_kind == 'navigate' and nav_val:
                                yield ('action', 'navigate', nav_val)
                            elif nav_kind == 'show_courses':
                                yield ('action', 'show_courses', nav_val or val, _extra)
                        elif action_type == 'SHOW_COURSES':
                            yield ('action', 'show_courses', val)
                    else:
                        hl_match = _HIGHLIGHT_RE.match(nav_buffer)
                        if hl_match:
                            # Тег подсветки — отдаём фрагмент отдельным событием, в текст не попадает
                            hl_text = hl_match.group(1).strip()
                            if hl_text:
                                yield ('highlight', hl_text)
                        else:
                            # Не экшен-тег — показываем как текст
                            display_buffer += nav_buffer
                    nav_buffer = ""

    # Сбрасываем остатки
    if display_buffer:
        yield ('token', display_buffer)
    if nav_buffer and not in_nav_tag:
        # Незакрытый тег — показываем как текст
        yield ('token', nav_buffer)

    yield ('full', full_response)


# ---------------------------------------------------------------------------
# Streaming SSE (text chat)
# ---------------------------------------------------------------------------

async def stream_rag_response(
    message: str,
    history: list[HistoryMessage],
    course_id: str,
    course_name: str,
    page_context: dict = {},
    current_user: Any = None,
    db: Session | None = None,
) -> AsyncIterator[str]:
    full_response = ""
    try:
        ctx = dict(page_context or {})
        if db:
            from app.utils.navigation_prompt import build_db_navigation_routes_list
            role = current_user.role if current_user else None
            ctx["db_nav_routes"] = build_db_navigation_routes_list(db, role=role, current_course_id=course_id)

        t_rag = time.perf_counter()
        _docs, context, sources = await retrieve_context_for_chat(message, course_id)
        rag_ms = (time.perf_counter() - t_rag) * 1000
        if db and current_user:
            record_metric(
                db,
                event_type="chat_rag",
                user_id=current_user.id,
                course_id=course_id,
                duration_ms=rag_ms,
                success=True,
            )

        yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"

        client_hist = [m.model_dump() for m in history]
        if db and current_user:
            db_hist = get_recent_history(db, current_user.id, course_id)
            client_hist = merge_history(client_hist, db_hist)
        history_text = format_history(client_hist)
        chain = get_chain(course_name, course_id, ctx, current_user)

        t_llm = time.perf_counter()
        async for event_type, *content_args in _stream_tokens(
            chain, {"context": context, "question": message, "history": history_text}, ctx, course_id
        ):
            if event_type == 'token':
                yield f"data: {json.dumps({'type': 'token', 'content': content_args[0]})}\n\n"
            elif event_type == 'action':
                action_name = content_args[0]
                action_val = content_args[1]
                if action_name == 'navigate':
                    yield f"data: {json.dumps({'type': 'action', 'action': 'navigate', 'path': action_val})}\n\n"
                elif action_name == 'show_courses':
                    payload = {'type': 'action', 'action': 'show_courses', 'query': action_val}
                    if len(content_args) > 2 and content_args[2]:
                        payload['matches'] = content_args[2]
                    yield f"data: {json.dumps(payload)}\n\n"
            elif event_type == 'highlight':
                yield f"data: {json.dumps({'type': 'highlight', 'text': content_args[0]})}\n\n"
            elif event_type == 'full':
                full_response = content_args[0]

        llm_ms = (time.perf_counter() - t_llm) * 1000
        if db and current_user:
            record_metric(
                db,
                event_type="chat_llm",
                user_id=current_user.id,
                course_id=course_id,
                duration_ms=llm_ms,
                success=True,
            )
            save_exchange(
                db,
                user_id=current_user.id,
                course_id=course_id,
                page_context=ctx,
                user_message=message,
                assistant_message=_strip_nav_tags(full_response),
            )

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        err_str = str(e)
        logger.error(f"Chat stream error: {e}")
        if '503' in err_str or 'ResponseError' in err_str:
            if settings.LLM_PROVIDER == 'ollama':
                msg = 'Ollama недоступна. Убедитесь, что Ollama запущена, и перезапустите бэкенд.'
            else:
                msg = 'Сервис LLM временно недоступен. Подождите и повторите запрос.'
        elif 'UNAVAILABLE' in err_str or 'high demand' in err_str:
            msg = 'API сейчас перегружен. Подождите 10-30 секунд и повторите запрос.'
        else:
            msg = f'Ошибка: {err_str}'
        yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"


@router.get("/chat/history", response_model=list[ChatHistoryMessage])
def chat_history(
    course_id: str = Query("default"),
    limit: int = Query(12, ge=1, le=40),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    if not current_user:
        return []
    rows = get_recent_history(db, current_user.id, course_id, limit=limit)
    return [ChatHistoryMessage(**r) for r in rows]

@router.post("/chat/save_message")
def api_save_message(
    request: SaveMessageRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    if current_user:
        save_message(
            db,
            user_id=current_user.id,
            course_id=request.course_id,
            role=request.role,
            content=request.content,
        )
    return {"status": "ok"}


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    return StreamingResponse(
        stream_rag_response(
            request.message, request.history,
            request.course_id, request.course_name,
            request.page_context,
            current_user,
            db,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Streaming SSE (voice chat) — TTS по предложениям
# ---------------------------------------------------------------------------

async def stream_rag_voice_response(
    message: str,
    history: list[HistoryMessage],
    course_id: str,
    course_name: str,
    page_context: dict = {},
    current_user: Any = None,
    db: Session | None = None,
) -> AsyncIterator[str]:
    full_response = ""
    try:
        ctx = dict(page_context or {})

        t_rag = time.perf_counter()
        _docs, context, sources = await retrieve_context_for_chat(message, course_id)
        rag_ms = (time.perf_counter() - t_rag) * 1000
        if db and current_user:
            record_metric(
                db,
                event_type="chat_rag",
                user_id=current_user.id,
                course_id=course_id,
                duration_ms=rag_ms,
                success=True,
            )

        yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"

        client_hist = [m.model_dump() for m in history]
        if db and current_user:
            client_hist = merge_history(client_hist, get_recent_history(db, current_user.id, course_id))
        history_text = format_history(client_hist)
        chain = get_chain(course_name, course_id, ctx, current_user)

        sentence_buffer = ""
        # Конец предложения ИЛИ запятая/точка с запятой при буфере > 35 символов (живее ритм речи)
        sentence_end_re = re.compile(r'([.!?]+[\s\n]+|[.!?]+$|\n{2,})')
        comma_re = re.compile(r'([,;]\s+)')

        async for event_type, *content_args in _stream_tokens(
            chain, {"context": context, "question": message, "history": history_text}, ctx, course_id
        ):
            if event_type == 'token':
                content = content_args[0]
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
                sentence_buffer += content

                # Проверяем конец предложения
                match = sentence_end_re.search(sentence_buffer)
                if not match and len(sentence_buffer) > 35:
                    # При длинном буфере разрезаем по запятой/точке с запятой
                    match = comma_re.search(sentence_buffer)

                if match:
                    end_idx = match.end()
                    sentence = sentence_buffer[:end_idx].strip()
                    sentence_buffer = sentence_buffer[end_idx:]

                    if sentence and len(sentence) > 3 and any(c.isalpha() for c in sentence):
                        audio_bytes = await synthesize_speech(sentence)
                        if audio_bytes:
                            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                            yield f"data: {json.dumps({'type': 'sentence', 'text': sentence, 'audio_b64': audio_b64})}\n\n"

            elif event_type == 'action':
                action_name = content_args[0]
                action_val = content_args[1]
                if action_name == 'navigate':
                    yield f"data: {json.dumps({'type': 'action', 'action': 'navigate', 'path': action_val})}\n\n"
                elif action_name == 'show_courses':
                    payload = {'type': 'action', 'action': 'show_courses', 'query': action_val}
                    if len(content_args) > 2 and content_args[2]:
                        payload['matches'] = content_args[2]
                    yield f"data: {json.dumps(payload)}\n\n"
            elif event_type == 'highlight':
                yield f"data: {json.dumps({'type': 'highlight', 'text': content_args[0]})}\n\n"
            elif event_type == 'full':
                full_response = content_args[0]

        # Озвучиваем остаток
        sentence_buffer = sentence_buffer.strip()
        if sentence_buffer and len(sentence_buffer) > 3 and any(c.isalpha() for c in sentence_buffer):
            audio_bytes = await synthesize_speech(sentence_buffer)
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                yield f"data: {json.dumps({'type': 'sentence', 'text': sentence_buffer, 'audio_b64': audio_b64})}\n\n"

        if db and current_user and full_response:
            save_exchange(
                db,
                user_id=current_user.id,
                course_id=course_id,
                page_context=ctx,
                user_message=message,
                assistant_message=_strip_nav_tags(full_response),
            )

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        err_str = str(e)
        logger.exception("Chat voice stream error:")
        if '503' in err_str or 'ResponseError' in err_str:
            if settings.LLM_PROVIDER == 'ollama':
                msg = 'Ollama недоступна. Убедитесь, что Ollama запущена, и перезапустите бэкенд.'
            else:
                msg = 'Сервис LLM временно недоступен. Подождите и повторите запрос.'
        elif 'UNAVAILABLE' in err_str or 'high demand' in err_str:
            msg = 'API сейчас перегружен. Пожалуйста, повторите через несколько секунд.'
        else:
            msg = f'Ошибка: {err_str}'
        yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"


@router.post("/chat/voice")
async def chat_voice(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    return StreamingResponse(
        stream_rag_voice_response(
            request.message, request.history,
            request.course_id, request.course_name,
            request.page_context,
            current_user,
            db,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Non-streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user_optional),
):
    try:
        ctx = dict(request.page_context or {})
        from app.utils.navigation_prompt import build_db_navigation_routes_list
        role = current_user.role if current_user else None
        ctx["db_nav_routes"] = build_db_navigation_routes_list(db, role=role, current_course_id=request.course_id)
        
        _docs, context, sources = await retrieve_context_for_chat(request.message, request.course_id)
        
        client_hist = [m.model_dump() for m in request.history]
        if current_user:
            client_hist = merge_history(client_hist, get_recent_history(db, current_user.id, request.course_id))
        history_text = format_history(client_hist)
        
        chain = get_chain(request.course_name, request.course_id, ctx, current_user)
        answer = await chain.ainvoke(
            {"context": context, "question": request.message, "history": history_text}
        )
        # Убираем навигационные теги из ответа
        answer = _strip_nav_tags(answer)
        return ChatResponse(answer=answer, sources=sources)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts")
async def text_to_speech(request: ChatRequest):
    audio = await synthesize_speech(request.message)
    if audio is None:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/mpeg")
