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
from app.models.mirror import CourseRef, LessonRef
from app.services.rag_service import get_retriever, format_docs
from app.services.homework_journal_service import build_journal_summary, build_reminders
from app.services.weak_topics_service import build_weak_topics_prompt_block
from app.utils.navigation_prompt import build_navigation_prompt, build_db_navigation_routes_list
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
    user: User,
    req: CreateCallRequest,
    available_courses: List[Dict[str, Any]],
    db: Session,
) -> str:
    """Строит системный промпт для Ultravox на основе контекста пользователя."""
    role_ru = "Преподаватель" if user.role == "teacher" else "Студент"
    role_en = user.role
    assistant = settings.ASSISTANT_NAME
    user_info = f"Пользователь: {user.username} ({role_ru}). Контекст: {req.course_name}."

    courses = _courses_for_prompt(req, db)
    courses_list = "\n".join([f"- {c['title']}" for c in courses])

    page_info_lines = [
        f"### НАВИГАЦИЯ\nТЕКУЩЕЕ МЕСТОПОЛОЖЕНИЕ ПОЛЬЗОВАТЕЛЯ:\n- Страница: {req.current_page or 'Неизвестно'}\n- URL: {req.current_path or '/'}\n\nСПИСОК КУРСОВ:\n{courses_list}\n"
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
    extra_tools = ""
    if role_en == "student":
        hw_rules = (
            "⚠️ СТРОЖАЙШИЙ ЗАПРЕТ: ТЕБЕ КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО РЕШАТЬ ТЕСТЫ ИЛИ ДАВАТЬ ПРЯМЫЕ ОТВЕТЫ НА ДОМАШКУ! "
            "Даже если пользователь цитирует вопрос из теста, или просит 'помоги с тестом' - ТЫ ДОЛЖЕН ОТКАЗАТЬ. "
            "Твоя задача — ТОЛЬКО задавать наводящие вопросы (сократический метод) и заставлять студента думать самому. "
            "Никогда не произноси правильный ответ на тест вслух. Если нарушишь это правило — тест будет провален."
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
    if extra_tools:
        behavior_rules.append(f"7. {extra_tools}")

    # Workshop-specific instructions
    is_on_workshop = (req.current_path or '').startswith('/homeworks/workshop/')
    if role_en == 'teacher' and is_on_workshop:
        behavior_rules.append(
            "8. МАСТЕРСКАЯ ДЗ: Ты сейчас находишься на странице создания домашнего задания. "
            "Если преподаватель говорит что-то вроде 'создай задание', 'придумай описание', 'напиши тест', 'добавь вопрос', 'заполни код' — "
            "НЕМЕДЛЕННО вызови инструмент fillHomeworkForm с нужными параметрами. "
            "Можешь заполнить одно поле или сразу все. Генерируй содержательный, реальный текст задания по теме курса. "
            "После вызова скажи вслух что именно ты заполнил."
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
                "Переводит пользователя на страницу платформы (курс, журнал, профиль, главная, ДЗ). "
                "ДЛЯ УРОКОВ НЕ ИСПОЛЬЗОВАТЬ! Для уроков используй openLesson. "
                "ВНИМАНИЕ: Если пользователь просит открыть курс, которого нет в списке доступных, КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО переходить на другой курс или выдумывать пути. Просто скажи словами, что такого курса нет. "
                "Сначала одной фразой по-русски скажи, куда переходишь («Открываю журнал»), затем вызови инструмент. "
                "После вызова не повторяй переход и не комментируй смену экрана. "
                "Не произноси navigate, NAVIGATE, path, URL или слэши."
            ),
            "dynamicParameters": [
                {
                    "name": "path",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {
                        "description": "Точный маршрут из списка доступных. ЗАПРЕЩЕНО выдумывать маршруты самостоятельно.",
                        "type": "string",
                    },
                    "required": True,
                },
            ],
            "client": {},
        }
    }

    open_lesson_tool = {
        "temporaryTool": {
            "modelToolName": "openLesson",
            "description": (
                "Открывает конкретный урок курса. "
                "Используй ТОЛЬКО этот инструмент для перехода на уроки (вместо navigatePage). "
                "Сначала скажи «Открываю урок», затем вызови инструмент."
            ),
            "dynamicParameters": [
                {
                    "name": "course_id",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {
                        "description": "ID курса (например, 'python-100-days-ru', 'react-30-days-ru').",
                        "type": "string",
                    },
                    "required": True,
                },
                {
                    "name": "lesson_number",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {
                        "description": "Порядковый номер урока (например, 1, 2, 5). Это не ID в базе данных, а именно номер урока по порядку.",
                        "type": "integer",
                    },
                    "required": True,
                },
                {
                    "name": "highlight_text",
                    "location": "PARAMETER_LOCATION_BODY",
                    "schema": {
                        "description": "Кусок текста (от 1 до 5 слов), к которому нужно проскроллить и подсветить на странице.",
                        "type": "string",
                    },
                    "required": False,
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

    selected_tools = [rag_tool, page_context_tool, navigate_tool, open_lesson_tool]
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
                "modelToolName": "reviewAllHomeworks",
                "description": (
                    "Запускает массовую фоновую ИИ-проверку всех несданных домашних заданий, которые ещё не проверялись ИИ. "
                    "Вызывай, если преподаватель просит «проверь все ДЗ», «запусти проверку всех заданий»."
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
        # Tool for filling homework form in Workshop (available on /homeworks/workshop/:id)
        selected_tools.append({
            "temporaryTool": {
                "modelToolName": "fillHomeworkForm",
                "description": (
                    "Заполняет поля формы создания домашнего задания в Мастерской ДЗ. "
                    "Вызывай когда преподаватель просит создать задание, написать описание, добавить тест, заполнить шаблон кода или письменную часть. "
                    "Передавай только те поля, которые нужно заполнить."
                ),
                "dynamicParameters": [
                    {
                        "name": "title",
                        "location": "PARAMETER_LOCATION_BODY",
                        "schema": {
                            "description": "Название домашнего задания",
                            "type": "string"
                        },
                        "required": False,
                    },
                    {
                        "name": "intro",
                        "location": "PARAMETER_LOCATION_BODY",
                        "schema": {
                            "description": "Описание задания: что должен сделать ученик, критерии оценки",
                            "type": "string"
                        },
                        "required": False,
                    },
                    {
                        "name": "code_template",
                        "location": "PARAMETER_LOCATION_BODY",
                        "schema": {
                            "description": "Шаблон кода с TODO-комментариями для заполнения учеником",
                            "type": "string"
                        },
                        "required": False,
                    },
                    {
                        "name": "written_part",
                        "location": "PARAMETER_LOCATION_BODY",
                        "schema": {
                            "description": "Письменная часть: теоретические вопросы для ученика",
                            "type": "string"
                        },
                        "required": False,
                    },
                    {
                        "name": "quiz_items",
                        "location": "PARAMETER_LOCATION_BODY",
                        "schema": {
                            "description": "Тестовые вопросы. Массив объектов: [{\"question\": \"...\", \"options\": [\"A\",\"B\",\"C\",\"D\"], \"correct_index\": 0}]",
                            "type": "string"
                        },
                        "required": False,
                    },
                ],
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

    # Общие инструменты для всех пользователей
    selected_tools.append({
        "temporaryTool": {
            "modelToolName": "getNotifications",
            "description": (
                "Получает список новых оповещений (уведомлений) пользователя. "
                "Оповещения содержат ссылки (links), по которым можно перейти с помощью navigatePage."
            ),
            "client": {},
        }
    })
    selected_tools.append({
        "temporaryTool": {
            "modelToolName": "clearNotifications",
            "description": "Очищает (удаляет) все оповещения пользователя.",
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
async def rag_query(req: RagQueryRequest, db: Session = Depends(get_db)):
    """
    RAG endpoint, который вызывается Ultravox во время разговора.
    Это публичный endpoint — запросы идут от серверов Ultravox, не от пользователя.
    """
    try:
        course_id = _resolve_course_id(req.session_id, req.course_id)
        if course_id == "default" or not course_id:
            return {"results": "Информация по данному запросу не найдена в материалах курса."}

        retriever = get_retriever(course_id)
        docs = await retriever.ainvoke(req.query)
        context = format_docs(docs, db)

        if not context.strip() or "(материалы курса не найдены)" in context:
            return {"results": "Информация по данному запросу не найдена в материалах курса."}

        # Extract vpath from the first doc that has it
        import re
        vpath_match = re.search(r'Маршрут:\s*([^\s\]]+)', context)
        vpath = vpath_match.group(1) if vpath_match else None

        # Build instruction for the LLM
        nav_instruction = ""
        if vpath:
            # Check user settings for highlight trigger word
            trigger_word = ""
            if req.session_id and req.session_id in _voice_sessions:
                uid = _voice_sessions[req.session_id].get("user_id")
                if uid:
                    from app.models.user import User
                    import json
                    u = db.query(User).filter(User.id == uid).first()
                    if u and u.settings_json:
                        try:
                            us = json.loads(u.settings_json)
                            trigger_word = us.get("ai_highlight_trigger", "").strip()
                        except Exception:
                            pass

            # Find first meaningful phrase from doc content
            content_lines = [l for l in context.split('\n') if l.strip() and not l.startswith('[')]
            highlight_candidate = ' '.join(content_lines[0].split()[:6]) if content_lines else ''
            
            trigger_condition = f"ТОЛЬКО ЕСЛИ пользователь использовал в своем запросе слово '{trigger_word}'" if trigger_word else "в любом случае"
            
            nav_instruction = (
                f"\n\n[ИНСТРУКЦИЯ ДЛЯ ИИ]: Информация найдена. "
                f"НЕМЕДЛЕННО вызови инструмент navigatePage с path='{vpath}'. "
                f"Обязательно передай параметр highlight_text='{highlight_candidate}', {trigger_condition}. "
                f"Только после вызова инструмента — кратко ответь пользователю вслух по найденному тексту ниже."
            )

        return {"results": context + nav_instruction}

    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return {"results": "Ошибка поиска в базе знаний."}
