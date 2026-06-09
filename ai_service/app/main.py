import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import chat, documents, widget, stt, ultravox, adaptive, analytics, navigation
from app.api import webhooks, homework_check, embeddable, audit
from app.config import settings
from app.database import Base, engine, SessionLocal
import app.models.navigation      # noqa: F401
import app.models.assistant_metric  # noqa: F401
import app.models.audit_log       # noqa: F401
import app.models.chat_message    # noqa: F401
import app.models.student_weak_topic  # noqa: F401
import app.models.mirror           # noqa: F401  ← облегчённые Course и Lesson

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 AI Service запущен: {settings.ASSISTANT_NAME}")
    logger.info(f"🤖 LLM: {settings.LLM_PROVIDER} / {settings.LLM_MODEL}")
    logger.info(f"🔊 TTS: {settings.TTS_PROVIDER} / {settings.TTS_VOICE}")
    logger.info(f"🌐 Platform URL: {settings.PLATFORM_SERVICE_URL}")

    with SessionLocal() as db:
        from app.utils.seed import seed_database
        from app.services.platform_sync import check_course_sync
        seed_database(db)
        try:
            check_course_sync(db)
        except Exception as e:
            logger.warning("Course sync check failed: %s", e)

    yield
    logger.info("AI Service остановлен.")


app = FastAPI(
    title="EduAI Voice Assistant",
    description="Голосовой ИИ-ассистент для образовательных платформ",
    version="3.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ИИ-роуты
app.include_router(ultravox.router,  prefix="/api/ultravox",  tags=["ultravox"])
app.include_router(chat.router,      prefix="/api",           tags=["chat"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(documents.router, prefix="/api",           tags=["documents"])
app.include_router(adaptive.router,  prefix="/api/adaptive",  tags=["adaptive"])
app.include_router(stt.router,       prefix="/api",           tags=["stt"])
app.include_router(widget.router,    prefix="/api",           tags=["widget"])
app.include_router(navigation.router, prefix="/api/navigation", tags=["navigation"])
app.include_router(homework_check.router, prefix="/api/homework", tags=["homework"])
app.include_router(embeddable.router, prefix="/api/embeddable", tags=["embeddable"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])

# Webhook-приёмники от платформы
app.include_router(webhooks.router,  prefix="/webhook",       tags=["webhooks"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "ai_service",
        "assistant": settings.ASSISTANT_NAME,
        "llm": f"{settings.LLM_PROVIDER}/{settings.LLM_MODEL}",
    }

@app.get("/")
async def root():
    return RedirectResponse(url="/docs")
