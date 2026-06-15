"""
Ultravox integration endpoints.

POST /api/ultravox/call  → создаёт Ultravox call, возвращает joinUrl
POST /api/ultravox/rag   → RAG tool endpoint, который вызывает Ultravox во время звонка
"""
import logging
import time
import uuid
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.auth_service import get_current_user, DummyUser
from app.models.mirror import CourseRef, LessonRef
from app.services.rag_service import get_retriever, format_docs
from app.utils.navigation_prompt import build_navigation_prompt, build_db_navigation_routes_list
from app.utils.role_capabilities import build_role_capabilities_prompt
from app.services.ultravox_tools import build_voice_tools
from app.services.permissions import resolve_permissions
from app.services.audit_service import record_audit
from app.services.metrics_service import record_metric


logger = logging.getLogger(__name__)
router = APIRouter()

ULTRAVOX_BASE = "https://api.ultravox.ai/api"

# Контекст страницы во время голосового звонка (обновляется с фронтенда при навигации)
_voice_sessions: Dict[str, Dict[str, Any]] = {}
_SESSION_TTL_SEC = 7200


# ─── Схемы ────────────────────────────────────────────────────────────────────

class CourseNavItem(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    icon: str = ""


class BreadcrumbItem(BaseModel):
    label: str
    path: str = ""


class CreateCallRequest(BaseModel):
    session_id: Optional[str] = None
    course_id: Optional[str] = "default"
    course_name: Optional[str] = "EduAI"
    current_page: Optional[str] = "Главная"
    current_path: Optional[str] = "/"
    page_content: Optional[str] = ""
    breadcrumbs: Optional[List[BreadcrumbItem]] = None
    voice_id: Optional[str] = None
    available_courses: Optional[List[CourseNavItem]] = None
    permissions: Optional[List[str]] = None
    platform_user_id: Optional[str] = None


class UpdateVoiceContextRequest(BaseModel):
    session_id: str
    course_id: str = "default"
    course_name: str = "EduAI"
    current_page: str = ""
    current_path: str = "/"
    page_content: str = ""
    breadcrumbs: Optional[List[BreadcrumbItem]] = None
    lesson_id: Optional[str] = None
    lesson_title: Optional[str] = None
    lesson_index: Optional[int] = None
    total_lessons: Optional[int] = None
    homework_id: Optional[int] = None
    assignment_id: Optional[int] = None
    assignment_student: Optional[str] = None
    assignment_status: Optional[str] = None
    assignment_grade: Optional[float] = None


class RagQueryRequest(BaseModel):
    query: str
    course_id: Optional[str] = None
    session_id: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=16)
def _voice_definition_key(voice_id: str) -> Optional[str]:
    """Возвращает ключ провайдера в definition (elevenLabs, cartesia, …)."""
    if not voice_id or not settings.ULTRAVOX_API_KEY:
        return None
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(
                f"{ULTRAVOX_BASE}/voices/{voice_id}",
                headers={"X-API-Key": settings.ULTRAVOX_API_KEY},
            )
        if resp.status_code != 200:
            return None
        definition = resp.json().get("definition") or {}
        for key in ("elevenLabs", "cartesia", "lmnt", "google", "inworld"):
            if key in definition:
                return key
    except Exception as e:
        logger.warning("voice lookup failed: %s", e)
    return None


def _build_voice_overrides(voice_id: str) -> Optional[Dict[str, Any]]:
    """voiceOverrides для create call — замедление/ускорение речи."""
    speed = settings.ULTRAVOX_VOICE_SPEED
    if not voice_id or abs(speed - 1.0) < 0.01:
        return None

    provider = _voice_definition_key(voice_id) or "elevenLabs"
    if provider == "elevenLabs":
        return {"elevenLabs": {"speed": max(0.7, min(1.2, speed))}}
    if provider == "lmnt":
        return {"lmnt": {"speed": max(0.25, min(2.0, speed))}}
    if provider == "google":
        return {"google": {"speakingRate": max(0.25, min(2.0, speed))}}
    if provider == "inworld":
        return {"inworld": {"speakingRate": max(0.5, min(1.5, speed))}}
    if provider == "cartesia":
        return {"cartesia": {"generationConfig": {"speed": max(0.6, min(1.5, speed))}}}
    return {"elevenLabs": {"speed": max(0.7, min(1.2, speed))}}


def _prune_voice_sessions() -> None:
    now = time.time()
    expired = [
        sid for sid, ctx in _voice_sessions.items()
        if now - ctx.get("updated_at", 0) > _SESSION_TTL_SEC
    ]
    for sid in expired:
        _voice_sessions.pop(sid, None)


def _save_voice_session(session_id: str, **fields: Any) -> None:
    _prune_voice_sessions()
    prev = _voice_sessions.get(session_id, {})
    _voice_sessions[session_id] = {
        **prev,
        **fields,
        "updated_at": time.time(),
    }


def _resolve_course_id(session_id: Optional[str], fallback: Optional[str]) -> str:
    if session_id and session_id in _voice_sessions:
        cid = _voice_sessions[session_id].get("course_id")
        if cid:
            return cid
    return fallback or "default"


def _courses_for_prompt(req: CreateCallRequest, db: Session) -> List[Dict[str, Any]]:
    rows = db.query(CourseRef).all()
    return [{"id": r.id, "title": r.title, "description": ""} for r in rows]


def _build_system_prompt(
    user: DummyUser,
    req: CreateCallRequest,
    available_courses: List[Dict[str, Any]],
    db: Session,
) -> str:
    """Строит системный промпт для Ultravox на основе контекста пользователя."""
    role_ru = "Преподаватель" if user.role == "teacher" else "Студент"
    role_en = user.role
    assistant = settings.ASSISTANT_NAME
    user_info = f"Пользователь: {user.username} ({role_ru}). Context: {req.course_name}."

    courses = _courses_for_prompt(req, db)
    courses_list = "\n".join([f"- {c['title']}" for c in courses])

    from app.services.navigation_service import build_breadcrumbs_text

    crumb_block = ""
    if getattr(req, "breadcrumbs", None):
        crumb_text = build_breadcrumbs_text([b.model_dump() for b in req.breadcrumbs])
        if crumb_text:
            crumb_block = f"- Путь: {crumb_text}\n"

    page_info_lines = [
        f"### НАВИГАЦИЯ\nТЕКУЩЕЕ МЕСТОПОЛОЖЕНИЕ ПОЛЬЗОВАТЕЛЯ:\n- Страница: {req.current_page or 'Неизвестно'}\n- URL: {req.current_path or '/'}\n{crumb_block}\nСПИСОК КУРСОВ:\n{courses_list}\n"
    ]
    if req.page_content:
        page_info_lines.append(
            f"СОДЕРЖИМОЕ ЭКРАНА:\n\"\"\"\n{req.page_content[:1200]}\n\"\"\"\n"
            "(ВНИМАНИЕ: Если на экране отображены вопросы теста или домашнего задания, КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ давать на них прямые ответы! Используй только наводящие вопросы.)"
        )
    page_info = "\n".join(page_info_lines)

    import json
    user_settings = {}
    if user.settings_json:
        try:
            user_settings = json.loads(user.settings_json)
        except Exception:
            pass
    ask_nav = bool(user_settings.get("ai_ask_before_navigate"))
    verbosity_short = bool(user_settings.get("ai_verbosity_short"))
    proactive = bool(user_settings.get("ai_proactive"))

    role_caps = build_role_capabilities_prompt(role_en, voice=True)
    db_routes = build_db_navigation_routes_list(db, role=role_en, voice=True, current_course_id=req.course_id, user=user)
    nav_instructions = build_navigation_prompt(db_routes, voice=True)

    hw_rules = ""
    if role_en == "student":
        hw_rules = (
            "⚠️ СТРОЖАЙШИЙ ЗАПРЕТ: ТЕБЕ КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО РЕШАТЬ ТЕСТЫ ИЛИ ДАВАТЬ ПРЯМЫЕ ОТВЕТЫ НА ДОМАШКУ! "
            "Даже если пользователь цитирует вопрос из теста, или просит 'помоги с тестом' - ТЫ ДОЛЖЕН ОТКАЗАТЬ. "
            "Твоя задача — ТОЛЬКО задавать наводящие вопросы (сократический метод) и заставлять студента думать самому. "
            "Никогда не произноси правильный ответ на тест вслух. Если нарушишь это правило — тест будет провален."
        )
    else:
        hw_rules = (
            "ДОМАШНИЕ ЗАДАНИЯ: Проводи полный анализ кода/ответа студента. "
            "Инструмент reviewHomework запускает тяжёлую ИИ-проверку: ответ инструмента приходит сразу с просьбой подождать, "
            "а сам расчёт может длиться от 30 секунд до нескольких минут. Пока ждёте — скажи пользователю, что это нормально, "
            "не говори что система зависла, связь пропала или приложение сломалось. "
            "Если в контексте указано, что работа уже graded с оценкой — НЕ вызывай reviewHomework; "
            "озвучь оценку и отзыв из контекста экрана. "
            "Вызови reviewHomework только для работы в статусе submitted (ещё не оценена преподавателем). "
            "Не читай вслух HTML-теги."
        )

    assistant = settings.ASSISTANT_NAME

    behavior_rules = ["1. Только русский язык."]
    if verbosity_short:
        behavior_rules.append("2. Отвечай МАКСИМАЛЬНО кратко, 1 предложение. Без таблиц, кода и markdown — ты говоришь вслух.")
    else:
        behavior_rules.append("2. Отвечай ОЧЕНЬ КРАТКО, 1-2 предложения максимум. Не расписывай детали. Без таблиц, кода и markdown — ты говоришь вслух.")

    if proactive:
        behavior_rules.append("3. Ты можешь сам проявлять инициативу. Если видишь на экране новые данные (например, несданную работу или оповещение) — прокомментируй их или предложи свою помощь первым.")
    else:
        behavior_rules.append("3. Не комментируй экран по своей инициативе, отвечай только на прямые вопросы пользователя.")

    behavior_rules.append("4. На приветствие отвечай тепло и коротко, без навигации.")
    behavior_rules.append(f"5. {hw_rules}")
    behavior_rules.append("6. ПОИСК ПЕРЕД ОТВЕТОМ: Прежде чем отвечать на вопрос по теме курса, вызови queryKnowledgeBase. Отвечай только по найденной информации. Если пользователь явно попросил НАЙТИ фрагмент текста или ПОКАЗАТЬ где это написано — перейди на найденный урок (navigatePage) и передай highlight_text. Если пользователь просто задал вопрос (например, 'что такое функция?') — просто ответь вслух, НИКУДА НЕ ПЕРЕХОДЯ.")

    # Workshop-specific instructions
    is_on_workshop = (req.current_path or '').startswith('/homeworks/workshop/')
    if role_en == 'teacher' and is_on_workshop:
        behavior_rules.append(
            "7. МАСТЕРСКАЯ ДЗ: Ты сейчас находишься на странице создания домашнего задания. "
            "Если преподаватель говорит что-то вроде 'создай задание', 'придумай описание', 'напиши тест', 'добавь вопрос', 'заполни код' — "
            "НЕМЕДЛЕННО вызови инструмент fillHomeworkForm с нужными параметрами. "
            "Можешь заполнить одно поле или сразу все. Генерируй содержательный, реальный текст задания по теме курса. "
            "После вызова скажи вслух что именно ты заполнил."
        )

    if role_en == 'admin':
        behavior_rules.append(
            "8. ОТЧЕТЫ ДЛЯ АДМИНИСТРАТОРА: Если администратор просит аналитический отчет или статистику системы, "
            "СНАЧАЛА спроси у него, какой именно нужен: Сводный (summary) или Детальный (detailed). "
            "Дождись его ответа. Когда он ответит, вызови инструмент adminGetReport с параметром report_type. "
            "Получив данные от сервера, не читай их как код! Выдели 2-3 самые главные цифры (количество курсов, пользователей, "
            "или количество диалогов с ИИ) и зачитай их внятно вслух."
        )

    behavior_rules_str = "\n".join(behavior_rules)

    prompt = f"""### ЯЗЫК
ОТВЕЧАЙ ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ. Ни слова на других языках.

### КТО ТЫ
Ты — {assistant}, голосовой ассистент образовательной платформы EduAI.
Пользователь: {user.username} ({role_ru}).
Контекст: {req.course_name}.

### КАК СЕБЯ ВЕСТИ
{behavior_rules_str}

{role_caps}

### ПРИВЕТСТВИЕ
Если начинаешь разговор — скажи только: «{settings.ASSISTANT_GREETING}» Без навигации и без слова navigate.

### НАВИГАЦИЯ
Переходы — только через инструмент navigatePage. Никогда не говори вслух navigate, NAVIGATE, path или URL.

### КОНТЕКСТ СТРАНИЦЫ
{page_info}

Во время звонка контекст страницы ОБНОВЛЯЕТСЯ:
- приходят сообщения «[СИСТЕМА: обновление контекста страницы]» — это актуальное местоположение и текст экрана;
- инструмент getPageContext — свежий снимок экрана (если сомневаешься);
- после навигации ориентируйся на последнее обновление, не на старый контекст из начала звонка.
Для queryKnowledgeBase course_id бери из последнего обновления контекста (поле course_id).

{nav_instructions}
"""
    return prompt


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/models")
async def list_ultravox_models(current_user: DummyUser = Depends(get_current_user)):
    """Список моделей, доступных вашему API-ключу (актуально с Ultravox)."""
    if not settings.ULTRAVOX_API_KEY:
        raise HTTPException(status_code=500, detail="ULTRAVOX_API_KEY not configured")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{ULTRAVOX_BASE}/models",
            headers={"X-API-Key": settings.ULTRAVOX_API_KEY},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Ultravox models error: {resp.status_code} — {resp.text[:300]}",
        )
    return resp.json()


@router.post("/call")
async def create_ultravox_call(
    req: CreateCallRequest,
    current_user: DummyUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создаёт Ultravox call и возвращает joinUrl.
    Ключ API никогда не передаётся на фронтенд.
    """
    if not settings.ULTRAVOX_API_KEY:
        raise HTTPException(status_code=500, detail="ULTRAVOX_API_KEY not configured")

    session_id = req.session_id or str(uuid.uuid4())
    granted = resolve_permissions(current_user.role, req.permissions)
    _save_voice_session(
        session_id,
        course_id=req.course_id or "default",
        course_name=req.course_name or "EduAI",
        current_page=req.current_page or "",
        current_path=req.current_path or "/",
        page_content=(req.page_content or "")[:1500],
        user_id=current_user.id,
        user_role=current_user.role,
        permissions=list(granted),
        platform_user_id=req.platform_user_id,
    )

    courses = _courses_for_prompt(req, db)
    system_prompt = _build_system_prompt(current_user, req, courses, db)

    selected_tools = build_voice_tools(current_user.role)

    voice_id = req.voice_id or settings.ULTRAVOX_VOICE_ID or None
    voice_overrides = _build_voice_overrides(voice_id) if voice_id else None

    payload = {
        "systemPrompt": system_prompt,
        "model": settings.ULTRAVOX_MODEL,
        "voice": voice_id,
        "languageHint": "ru",
        "selectedTools": selected_tools,
        "maxDuration": "1800s",
        "recordingEnabled": False,
        "firstSpeakerSettings": {
            "agent": {
                "text": settings.ASSISTANT_GREETING,
            }
        },
    }
    if voice_overrides:
        payload["voiceOverrides"] = voice_overrides

    payload = {k: v for k, v in payload.items() if v is not None}

    t_start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{ULTRAVOX_BASE}/calls",
            params={"enableGreetingPrompt": "false"},
            json=payload,
            headers={
                "X-API-Key": settings.ULTRAVOX_API_KEY,
                "Content-Type": "application/json"
            }
        )
    duration_ms = (time.perf_counter() - t_start) * 1000

    if resp.status_code not in (200, 201):
        logger.error(f"Ultravox API error: {resp.status_code} {resp.text}")
        record_metric(
            db,
            event_type="voice_session",
            user_id=current_user.id,
            course_id=req.course_id,
            duration_ms=duration_ms,
            success=False
        )
        raise HTTPException(
            status_code=502,
            detail=f"Ultravox API error: {resp.status_code} — {resp.text[:300]}"
        )

    record_metric(
        db,
        event_type="voice_session",
        user_id=current_user.id,
        course_id=req.course_id,
        duration_ms=duration_ms,
        success=True
    )

    data = resp.json()
    record_audit(
        db,
        action="voice_call_started",
        user_id=current_user.id,
        session_id=session_id,
        resource="ultravox",
        success=True,
        meta={
            "role": current_user.role,
            "permissions": sorted(granted),
            "tools_count": len(selected_tools),
            "path": req.current_path,
        },
    )
    return {
        "joinUrl": data.get("joinUrl"),
        "callId": data.get("callId"),
        "sessionId": session_id,
        "granted_permissions": sorted(granted),
    }


@router.post("/context")
async def update_voice_context(
    req: UpdateVoiceContextRequest,
    current_user: DummyUser = Depends(get_current_user),
):
    """Обновляет контекст страницы во время активного голосового звонка."""
    _save_voice_session(
        req.session_id,
        course_id=req.course_id,
        course_name=req.course_name,
        current_page=req.current_page,
        current_path=req.current_path,
        page_content=(req.page_content or "")[:1500],
        lesson_id=req.lesson_id,
        lesson_title=req.lesson_title,
        lesson_index=req.lesson_index,
        total_lessons=req.total_lessons,
        homework_id=req.homework_id,
        assignment_id=req.assignment_id,
        assignment_student=req.assignment_student,
        assignment_status=req.assignment_status,
        user_id=current_user.id,
        user_role=current_user.role,
    )
    lesson_info = f" lesson={req.lesson_title!r}" if req.lesson_title else ""
    logger.info(
        "Voice context [%s]: %s %s course=%s%s",
        req.session_id[:8],
        req.current_page,
        req.current_path,
        req.course_id,
        lesson_info,
    )
    return {"ok": True, "session_id": req.session_id}


@router.post("/rag")
async def rag_query(req: RagQueryRequest, db: Session = Depends(get_db)):
    """
    RAG endpoint, который вызывается Ultravox во время разговора.
    Это публичный endpoint — запросы идут от серверов Ultravox, не от пользователя.
    """
    try:
        session_data = _voice_sessions.get(req.session_id) or {}
        user_id = session_data.get("user_id")

        course_id = _resolve_course_id(req.session_id, req.course_id)
        if course_id == "default" or not course_id:
            return {
                "results": "Информация по данному запросу не найдена: откройте курс или укажите course_id.",
                "indexed_chunks": 0,
            }

        t_rag = time.perf_counter()
        indexed = _collection_doc_count(course_id)
        docs = await retrieve_course_docs(course_id, req.query)
        context = format_docs(docs, db)
        rag_ms = (time.perf_counter() - t_rag) * 1000

        record_metric(
            db,
            event_type="voice_rag",
            user_id=user_id,
            course_id=course_id,
            duration_ms=rag_ms,
            success=True,
        )

        if not context.strip() or "(материалы курса не найдены)" in context:
            hint = (
                f" В индексе курса «{course_id}» сейчас {indexed} фрагментов. "
                "Если 0 — платформа должна отправить webhooks уроков или запустить sync_all_to_ai.py."
            )
            return {
                "results": "Информация по данному запросу не найдена в материалах курса." + hint,
                "indexed_chunks": indexed,
            }

        import json

        from app.services.highlight_service import extract_highlight_quote
        from app.services.rag_service import parse_lesson_id_from_source

        vpath = None
        highlight_quote = ""
        if docs:
            first = docs[0]
            source = first.metadata.get("source", "")
            cid = first.metadata.get("course_id")
            if source.startswith("lesson_") and cid:
                lesson_id = parse_lesson_id_from_source(source, cid)
                if lesson_id is not None:
                    vpath = f"/courses/{cid}?lesson={lesson_id}"
            highlight_quote = extract_highlight_quote(first.page_content, query=req.query)

        nav_instruction = ""
        if vpath:
            trigger_word = ""
            if req.session_id and req.session_id in _voice_sessions:
                uid = _voice_sessions[req.session_id].get("user_id")
                if uid:
                    from app.models.user import User
                    u = db.query(User).filter(User.id == uid).first()
                    if u and u.settings_json:
                        try:
                            us = json.loads(u.settings_json)
                            trigger_word = us.get("ai_highlight_trigger", "").strip()
                        except Exception:
                            pass

            trigger_condition = (
                f"ТОЛЬКО ЕСЛИ пользователь явно просил найти/показать фрагмент"
                + (f" или использовал слово «{trigger_word}»" if trigger_word else "")
            )
            highlight_part = ""
            if highlight_quote:
                highlight_part = (
                    f" При переходе передай highlight_text='{highlight_quote}' "
                    f"(это точная цитата из материала, не меняй её), {trigger_condition}."
                )
            else:
                highlight_part = " Не передавай highlight_text — цитата не найдена в чанке."

            nav_instruction = (
                f"\n\n[ИНСТРУКЦИЯ ДЛЯ ИИ]: Информация найдена. "
                f"Переходи на урок ТОЛЬКО если пользователь явно просил найти/показать на странице; "
                f"иначе ответь вслух без навигации. "
                f"Если переход нужен — вызови openLesson или navigatePage с path='{vpath}'."
                f"{highlight_part} "
                f"Кратко ответь по найденному тексту ниже."
            )

        return {
            "results": context + nav_instruction,
            "vpath": vpath,
            "highlight_text": highlight_quote or None,
            "course_id": course_id,
            "indexed_chunks": indexed,
            "sources_found": len(docs),
        }

    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return {"results": "Ошибка поиска в базе знаний."}
