import json
import logging
import base64
import re
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from app.config import settings
from app.services.rag_service import (
    get_retriever,
    get_chain,
    format_docs,
    format_history,
)
from app.services.tts_service import synthesize_speech
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# На главной (default) RAG по коллекции часто подмешивает случайные чанки (в т.ч. «приветствия») —
# модель начинает их повторять. Там достаточно списка курсов из промпта.
_GLOBAL_HOME_CONTEXT = (
    "Ты на главной странице платформы. "
    "На привет и «как дела?» отвечай по-человечески своими словами, не зеркаль вопрос. "
    "Переход на страницу курса — только после явного согласия пользователя на твой вопрос «подходит? перевести?»; "
    "на первую просьбу «переведи/открой курс» тег [NAVIGATE:/courses/…] не ставь. "
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


# Регулярка для NAVIGATE-тегов
_NAV_RE = re.compile(r'\[NAVIGATE:([^\]]+)\]')
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
    """Удаляет [NAVIGATE:...] теги из отображаемого текста."""
    return _NAV_RE.sub('', text).strip()


async def _stream_tokens(chain, inputs: dict):
    """Генератор токенов с обработкой NAVIGATE-тегов."""
    full_response = ""
    display_buffer = ""
    nav_buffer = ""        # накапливаем потенциальный тег
    in_nav_tag = False     # находимся внутри [NAVIGATE:...]

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
                    match = _NAV_RE.match(nav_buffer)
                    if match:
                        # Это навигационный тег — выдаём action, не показываем пользователю
                        yield ('action', match.group(1).strip())
                    else:
                        # Не навигационный тег — показываем как текст
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
    current_user: User = None
) -> AsyncIterator[str]:
    try:
        _docs, context, sources = await retrieve_context_for_chat(message, course_id)

        yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"

        history_text = format_history([m.model_dump() for m in history])
        chain = get_chain(course_name, course_id, page_context, current_user)

        async for event_type, content in _stream_tokens(
            chain, {"context": context, "question": message, "history": history_text}
        ):
            if event_type == 'token':
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
            elif event_type == 'action':
                yield f"data: {json.dumps({'type': 'action', 'action': 'navigate', 'path': content})}\n\n"
            # 'full' — не отправляем клиенту

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        err_str = str(e)
        logger.error(f"Chat stream error: {e}")
        if '503' in err_str or 'UNAVAILABLE' in err_str or 'high demand' in err_str:
            msg = 'Gemini API сейчас перегружен. Подождите 10-30 секунд и повторите запрос.'
        else:
            msg = f'Ошибка: {err_str}'
        yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"


from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response
from app.services.auth_service import get_current_user_optional
from app.models.user import User

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, current_user: User = Depends(get_current_user_optional)):
    # pass user info into rag service later
    return StreamingResponse(
        stream_rag_response(
            request.message, request.history,
            request.course_id, request.course_name,
            request.page_context,
            current_user
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
    current_user: User = None
) -> AsyncIterator[str]:
    try:
        _docs, context, sources = await retrieve_context_for_chat(message, course_id)

        yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"

        history_text = format_history([m.model_dump() for m in history])
        chain = get_chain(course_name, course_id, page_context, current_user)

        sentence_buffer = ""
        # Конец предложения ИЛИ запятая/точка с запятой при буфере > 35 символов (живее ритм речи)
        sentence_end_re = re.compile(r'([.!?]+[\s\n]+|[.!?]+$|\n{2,})')
        comma_re = re.compile(r'([,;]\s+)')

        async for event_type, content in _stream_tokens(
            chain, {"context": context, "question": message, "history": history_text}
        ):
            if event_type == 'token':
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
                yield f"data: {json.dumps({'type': 'action', 'action': 'navigate', 'path': content})}\n\n"

        # Озвучиваем остаток
        sentence_buffer = sentence_buffer.strip()
        if sentence_buffer and len(sentence_buffer) > 3 and any(c.isalpha() for c in sentence_buffer):
            audio_bytes = await synthesize_speech(sentence_buffer)
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                yield f"data: {json.dumps({'type': 'sentence', 'text': sentence_buffer, 'audio_b64': audio_b64})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        err_str = str(e)
        logger.exception("Chat voice stream error:")
        if '503' in err_str or 'UNAVAILABLE' in err_str or 'high demand' in err_str:
            msg = 'Gemini API сейчас перегружен. Пожалуйста, повторите через несколько секунд.'
        else:
            msg = f'Ошибка: {err_str}'
        yield f"data: {json.dumps({'type': 'error', 'content': msg})}\n\n"


@router.post("/chat/voice")
async def chat_voice(request: ChatRequest, current_user: User = Depends(get_current_user_optional)):
    return StreamingResponse(
        stream_rag_voice_response(
            request.message, request.history,
            request.course_id, request.course_name,
            request.page_context,
            current_user
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Non-streaming endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        _docs, context, sources = await retrieve_context_for_chat(request.message, request.course_id)
        history_text = format_history([m.model_dump() for m in request.history])
        chain = get_chain(request.course_name, request.course_id, request.page_context)
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
