from fastapi import APIRouter, Query
from app.config import settings

router = APIRouter()


@router.get("/widget/config")
async def widget_config(
    course_id: str = Query(default=settings.DEFAULT_COURSE_ID),
):
    """
    Возвращает конфигурацию виджета для конкретного курса.
    Фронтенд запрашивает этот эндпоинт при инициализации.
    """
    return {
        "course_id": course_id,
        "assistant_name": settings.ASSISTANT_NAME,
        "course_name": settings.COURSE_NAME,
        "greeting": settings.ASSISTANT_GREETING,
        "tts_provider": settings.TTS_PROVIDER,
        "tts_enabled": True,
    }
