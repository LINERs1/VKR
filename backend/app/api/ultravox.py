"""
Ultravox integration endpoints.

POST /api/ultravox/call  → создаёт Ultravox call, возвращает joinUrl
POST /api/ultravox/rag   → RAG tool endpoint, который вызывает Ultravox во время звонка
"""
import logging
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
from app.utils.navigation_prompt import build_navigation_prompt

logger = logging.getLogger(__name__)
router = APIRouter()

ULTRAVOX_BASE = "https://api.ultravox.ai/api"


# ─── Схемы ────────────────────────────────────────────────────────────────────

class CourseNavItem(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    icon: str = ""


class CreateCallRequest(BaseModel):
    course_id: Optional[str] = "default"
    course_name: Optional[str] = "EduAI"
    current_page: Optional[str] = "Главная"
    current_path: Optional[str] = "/"
    page_content: Optional[str] = ""
    voice_id: Optional[str] = None
    available_courses: Optional[List[CourseNavItem]] = None


class RagQueryRequest(BaseModel):
    query: str
    course_id: Optional[str] = "default"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _courses_for_prompt(req: CreateCallRequest, db: Session) -> List[Dict[str, Any]]:
    if req.available_courses:
        return [c.model_dump() for c in req.available_courses]
    rows = db.query(Course).all()
    if rows:
        return [
            {
                "id": c.id,
                "title": c.title,
                "description": c.description or "",
                "icon": c.icon or "",
            }
            for c in rows
        ]
    return []


def _build_system_prompt(
    user: User,
    req: CreateCallRequest,
    available_courses: List[Dict[str, Any]],
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

    nav_instructions = build_navigation_prompt(available_courses, voice=True)

    hw_rules = ""
    if role_en == "student":
        hw_rules = "ДОМАШНИЕ ЗАДАНИЯ: Никогда не пиши готовое решение или код. Задавай наводящие вопросы (сократический метод), давай подсказки."
    else:
        hw_rules = (
            "ДОМАШНИЕ ЗАДАНИЯ: Проводи полный анализ кода/ответа студента. "
            "Указывай на ошибки конкретно. В текстовом чате ошибочный фрагмент оборачивай в "
            "<span style='color:#ef4444;font-weight:bold'>ошибочный код</span>."
        )

    prompt = f"""### КРИТИЧЕСКИ ВАЖНОЕ ПРАВИЛО
ОТВЕЧАЙ ИСКЛЮЧИТЕЛЬНО НА РУССКОМ ЯЗЫКЕ. НИ ОДНОГО СЛОВА НА ДРУГИХ ЯЗЫКАХ.

### ПРИВЕТСТВИЕ
Если начинаешь разговор — скажи только: «Привет! Я EduAI. Чем могу помочь?» Без тегов [NAVIGATE:...].

### РОЛЬ
Ты — EduAI, профессиональный образовательный голосовой ассистент.
Текущий пользователь: {user.username} ({role_ru}).
Текущий курс/контекст: {req.course_name}.

### ПРАВИЛА
1. Отвечай ТОЛЬКО на русском языке.
2. Будь лаконичным и доброжелательным. Для голоса: без таблиц, кода и markdown.
3. {hw_rules}
4. Используй инструмент queryKnowledgeBase чтобы искать информацию из материалов курса.

### КОНТЕКСТ
{page_info}

{nav_instructions}

Пользователь: {user.username}
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

    courses = _courses_for_prompt(req, db)
    system_prompt = _build_system_prompt(current_user, req, courses)

    # RAG Tool — Ultravox будет вызывать наш FastAPI endpoint
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
            "staticParameters": [
                {
                    "name": "course_id",
                    "location": "PARAMETER_LOCATION_BODY",
                    "value": req.course_id or "default"
                }
            ],
            "http": {
                # Ultravox вызывает этот endpoint с нашего сервера
                "baseUrlPattern": f"{settings.BACKEND_PUBLIC_URL}/api/ultravox/rag",
                "httpMethod": "POST"
            }
        }
    }

    payload = {
        "systemPrompt": system_prompt,
        "model": settings.ULTRAVOX_MODEL,
        "voice": req.voice_id or settings.ULTRAVOX_VOICE_ID or None,
        "languageHint": "ru",
        "selectedTools": [rag_tool],
        "maxDuration": "1800s",
        "recordingEnabled": False,
        "firstSpeakerSettings": {
            "agent": {
                "text": "Привет! Я EduAI. Чем могу помочь?",
            }
        },
    }
    # Убираем None значения
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
    }


@router.post("/rag")
async def rag_query(req: RagQueryRequest):
    """
    RAG endpoint, который вызывается Ultravox во время разговора.
    Это публичный endpoint — запросы идут от серверов Ultravox, не от пользователя.
    """
    try:
        if req.course_id == "default" or not req.course_id:
            return {"results": "Общие знания. Конкретного курса не выбрано."}

        retriever = get_retriever(req.course_id)
        docs = await retriever.ainvoke(req.query)
        context = format_docs(docs)

        if not context.strip():
            return {"results": "Информация по данному запросу не найдена в материалах курса."}

        return {"results": context}

    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return {"results": "Ошибка поиска в базе знаний."}
