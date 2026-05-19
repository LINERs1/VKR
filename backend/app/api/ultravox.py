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
from app.services.auth_service import get_current_user
from app.models.user import User
from app.models.course import Course
from app.services.rag_service import get_retriever, format_docs
from app.services.homework_journal_service import build_journal_summary, build_reminders
from app.services.weak_topics_service import build_weak_topics_prompt_block
from app.utils.navigation_prompt import build_navigation_prompt
from app.utils.role_capabilities import build_role_capabilities_prompt

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


class CreateCallRequest(BaseModel):
    session_id: Optional[str] = None
    course_id: Optional[str] = "default"
    course_name: Optional[str] = "EduAI"
    current_page: Optional[str] = "Главная"
    current_path: Optional[str] = "/"
    page_content: Optional[str] = ""
    voice_id: Optional[str] = None
    available_courses: Optional[List[CourseNavItem]] = None


class UpdateVoiceContextRequest(BaseModel):
    session_id: str
    course_id: str = "default"
    course_name: str = "EduAI"
    current_page: str = ""
    current_path: str = "/"
    page_content: str = ""
    lesson_id: Optional[str] = None
    lesson_title: Optional[str] = None
    lesson_index: Optional[int] = None
    total_lessons: Optional[int] = None
    homework_id: Optional[int] = None
    assignment_id: Optional[int] = None
    assignment_student: Optional[str] = None
    assignment_status: Optional[str] = None


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
    if req.available_courses:
        out = [c.model_dump() for c in req.available_courses]
        rows = {c.id: c for c in db.query(Course).all()}
        for item in out:
            row = rows.get(item.get("id"))
            if row and row.lessons:
                item["lessons"] = [{"id": l.id, "title": l.title} for l in row.lessons]
        return out
    rows = db.query(Course).all()
    if rows:
        return [
            {
                "id": c.id,
                "title": c.title,
                "description": c.description or "",
                "icon": c.icon or "",
                "lessons": [{"id": l.id, "title": l.title} for l in c.lessons],
            }
            for c in rows
        ]
    return []


def _build_system_prompt(
    user: User,
    req: CreateCallRequest,
    available_courses: List[Dict[str, Any]],
    db: Session,
) -> str:
    """Строит системный промпт для Ultravox на основе контекста пользователя."""
    role_ru = "Преподаватель" if user.role == "teacher" else "Студент"
    role_en = user.role

    page_info_lines = [
        f"ТЕКУЩЕЕ МЕСТОПОЛОЖЕНИЕ: Страница «{req.current_page}», URL: {req.current_path}"
    ]
    if req.page_content:
        page_info_lines.append(
            f"СОДЕРЖИМОЕ ЭКРАНА:\n\"\"\"\n{req.page_content[:1200]}\n\"\"\"\n"
            "(Опирайся на эти данные, если пользователь просит проанализировать страницу, оценки или графики.)"
        )
    page_info = "\n".join(page_info_lines)

    role_caps = build_role_capabilities_prompt(role_en, voice=True)
    nav_instructions = build_navigation_prompt(available_courses, voice=True, role=role_en)

    hw_rules = ""
    extra_tools = ""
    if role_en == "student":
        hw_rules = (
            "ДОМАШНИЕ ЗАДАНИЯ: Никогда не пиши готовое решение или код. "
            "Задавай наводящие вопросы (сократический метод). "
            "Для подсказки по текущему ДЗ вызови getHomeworkHint. "
            "Для списка несданных заданий — getHomeworkReminders."
        )
        try:
            rem = build_reminders(db, user)
            if rem.get("message"):
                page_info_lines.append(f"НАПОМИНАНИЕ О ДЗ: {rem['message']}")
            weak_block = build_weak_topics_prompt_block(db, user.id, req.course_id or "default")
            if weak_block:
                page_info_lines.append(weak_block)
        except Exception:
            pass
    else:
        hw_rules = (
            "ДОМАШНИЕ ЗАДАНИЯ: Проводи полный анализ кода/ответа студента. "
            "Инструмент reviewHomework запускает тяжёлую ИИ-проверку: ответ инструмента приходит сразу с просьбой подождать, "
            "а сам расчёт может длиться от 30 секунд до нескольких минут. Пока ждёте — скажи пользователю, что это нормально, "
            "не говори что система зависла, связь пропала или приложение сломалось. "
            "Если в контексте указано, что работа уже graded с оценкой — НЕ вызывай reviewHomework; "
            "озвучь оценку и отзыв из контекста экрана. "
            "Вызови reviewHomework только для работы в статусе submitted (ещё не оценена преподавателем). "
            "Для сводки «кто не сдал», «средний балл», «кто ждёт проверки» — getTeacherSummary. "
            "Не читай вслух HTML-теги."
        )
        extra_tools = (
            "Инструмент getTeacherSummary — актуальная сводка журнала: средние баллы по курсам, "
            "кто не сдал, что ждёт проверки."
        )
        try:
            summary = build_journal_summary(db, user.id)
            if summary.get("overall_avg") is not None:
                page_info_lines.append(
                    f"СВОДКА ЖУРНАЛА: средний балл {summary['overall_avg']}, "
                    f"на проверке {summary['pending_review_count']}, не сдано {summary['not_submitted_count']}."
                )
        except Exception:
            pass

    assistant = settings.ASSISTANT_NAME

    prompt = f"""### ЯЗЫК
ОТВЕЧАЙ ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ. Ни слова на других языках.

### КТО ТЫ
Ты — {assistant}, голосовой ассистент образовательной платформы EduAI.
Пользователь: {user.username} ({role_ru}).
Контекст: {req.course_name}.

### КАК СЕБЯ ВЕСТИ
1. Только русский язык.
2. Отвечай кратко и по-человечески. Без таблиц, кода и markdown — ты говоришь вслух.
3. На приветствие отвечай тепло и коротко, без навигации.
4. {hw_rules}
5. Для поиска по материалам курса используй инструмент queryKnowledgeBase.
{f'6. {extra_tools}' if extra_tools else ''}

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
async def list_ultravox_models(current_user: User = Depends(get_current_user)):
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создаёт Ultravox call и возвращает joinUrl.
    Ключ API никогда не передаётся на фронтенд.
    """
    if not settings.ULTRAVOX_API_KEY:
        raise HTTPException(status_code=500, detail="ULTRAVOX_API_KEY not configured")

    session_id = req.session_id or str(uuid.uuid4())
    _save_voice_session(
        session_id,
        course_id=req.course_id or "default",
        course_name=req.course_name or "EduAI",
        current_page=req.current_page or "",
        current_path=req.current_path or "/",
        page_content=(req.page_content or "")[:1500],
    )

    courses = _courses_for_prompt(req, db)
    system_prompt = _build_system_prompt(current_user, req, courses, db)

    navigate_tool = {
        "temporaryTool": {
            "modelToolName": "navigatePage",
            "description": (
                "Переводит пользователя на страницу платформы (курс, урок, журнал, профиль, главная, ДЗ). "
                "Сначала одной фразой по-русски скажи, куда переходишь («Открываю журнал»), затем вызови инструмент. "
                "После вызова не повторяй переход и не комментируй смену экрана. "
                "Не произноси navigate, NAVIGATE, path, URL или слэши."
            ),
            "dynamicParameters": [
                {
                    "name": "path",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {
                        "description": (
                            "Маршрут: /, /journal, /profile, /homeworks, "
                            "/courses/{course_id} или /courses/{course_id}?lesson={lesson_id}"
                        ),
                        "type": "string",
                    },
                    "required": True,
                },
            ],
            "client": {},
        }
    }

    page_context_tool = {
        "temporaryTool": {
            "modelToolName": "getPageContext",
            "description": (
                "Возвращает актуальное местоположение пользователя на сайте и текст, "
                "который сейчас виден на экране. Вызывай после перехода на другую страницу "
                "или если пользователь спрашивает «где я», «что на экране»."
            ),
            "client": {},
        }
    }

    # RAG Tool — выполняется в браузере (client), без публичного HTTPS URL
    rag_tool = {
        "temporaryTool": {
            "modelToolName": "queryKnowledgeBase",
            "description": (
                "Ищет информацию в материалах курса по смысловому сходству. "
                "Используй этот инструмент, когда пользователь задаёт вопросы по теме курса, "
                "просит объяснить тему или найти информацию в учебных материалах."
            ),
            "dynamicParameters": [
                {
                    "name": "query",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {
                        "description": "Поисковый запрос для поиска в материалах курса",
                        "type": "string"
                    },
                    "required": True
                },
            ],
            "client": {},
        }
    }

    selected_tools = [rag_tool, page_context_tool, navigate_tool]
    if current_user.role == "teacher":
        selected_tools.append({
            "temporaryTool": {
                "modelToolName": "reviewHomework",
                "description": (
                    "Запускает автоматическую ИИ-проверку домашнего задания выбранного ученика. "
                    "Только если работа сдана и ещё не оценена (submitted). "
                    "Если работа уже оценена (graded) — не вызывай, ответь по данным на экране. "
                    "Проверка на сервере может занять до нескольких минут: сразу скажи пользователю подождать, не называй это зависанием."
                ),
                "client": {},
            }
        })
        selected_tools.append({
            "temporaryTool": {
                "modelToolName": "getTeacherSummary",
                "description": (
                    "Сводка журнала: средний балл, кто не сдал ДЗ, что ждёт проверки, успеваемость по курсам. "
                    "Вызывай на вопросы «кто не сдал», «средний балл», «что на проверке»."
                ),
                "client": {},
            }
        })
    else:
        selected_tools.append({
            "temporaryTool": {
                "modelToolName": "getHomeworkReminders",
                "description": (
                    "Список несданных домашних заданий и работ на проверке у преподавателя. "
                    "Вызывай, если ученик спрашивает «что мне сделать», «какие ДЗ остались»."
                ),
                "client": {},
            }
        })
        selected_tools.append({
            "temporaryTool": {
                "modelToolName": "getHomeworkHint",
                "description": (
                    "Сократическая подсказка по текущему домашнему заданию без готового решения. "
                    "Вызывай, если ученик просит подсказку, намёк или помощь с кодом на странице ДЗ."
                ),
                "client": {},
            }
        })

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

    if resp.status_code not in (200, 201):
        logger.error(f"Ultravox API error: {resp.status_code} {resp.text}")
        raise HTTPException(
            status_code=502,
            detail=f"Ultravox API error: {resp.status_code} — {resp.text[:300]}"
        )

    data = resp.json()
    return {
        "joinUrl": data.get("joinUrl"),
        "callId": data.get("callId"),
        "sessionId": session_id,
    }


@router.post("/context")
async def update_voice_context(
    req: UpdateVoiceContextRequest,
    current_user: User = Depends(get_current_user),
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
async def rag_query(req: RagQueryRequest):
    """
    RAG endpoint, который вызывается Ultravox во время разговора.
    Это публичный endpoint — запросы идут от серверов Ultravox, не от пользователя.
    """
    try:
        course_id = _resolve_course_id(req.session_id, req.course_id)
        if course_id == "default" or not course_id:
            return {"results": "Общие знания. Конкретного курса не выбрано."}

        retriever = get_retriever(course_id)
        docs = await retriever.ainvoke(req.query)
        context = format_docs(docs)

        if not context.strip():
            return {"results": "Информация по данному запросу не найдена в материалах курса."}

        return {"results": context}

    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return {"results": "Ошибка поиска в базе знаний."}
