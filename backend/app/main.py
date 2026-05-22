import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents, widget, courses, stt, auth, homework, homework_templates, ultravox, adaptive, analytics, notifications
from app.config import settings
from app.database import Base, engine, SessionLocal
import app.models.homework  # noqa: F401
import app.models.homework_template  # noqa: F401
import app.models.student_weak_topic  # noqa: F401
import app.models.chat_message  # noqa: F401
import app.models.assistant_metric  # noqa: F401
import app.models.user
import app.models.course
import app.models.notification  # noqa: F401
from sqlalchemy import text

# Initialize database
Base.metadata.create_all(bind=engine)


def _migrate_sqlite_columns():
    """Добавляет новые колонки в существующую SQLite без Alembic."""
    stmts = [
        "ALTER TABLE homeworks ADD COLUMN content_json TEXT",
        "ALTER TABLE homeworks ADD COLUMN is_demo INTEGER DEFAULT 0",
        "ALTER TABLE homework_assignments ADD COLUMN student_quiz_json TEXT",
        "ALTER TABLE homework_assignments ADD COLUMN ai_review_json TEXT",
        "ALTER TABLE users ADD COLUMN settings_json TEXT",
    ]
    with engine.connect() as conn:
        for stmt in stmts:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass


_migrate_sqlite_columns()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.ASSISTANT_NAME} backend")
    hw_model = settings.HOMEWORK_REVIEW_MODEL or settings.LLM_MODEL
    logger.info(f"🤖 LLM:  {settings.LLM_PROVIDER} / {settings.LLM_MODEL}")
    logger.info(f"📝 ДЗ:   {settings.LLM_PROVIDER} / {hw_model}")
    logger.info(f"🔊 TTS:  {settings.TTS_PROVIDER} / {settings.TTS_VOICE}")
    logger.info(f"🌐 CORS: {settings.cors_origins}")
    # Auto-seed database and ingest course materials on startup
    with SessionLocal() as db:
        from app.utils.seed import seed_database
        from app.utils.seed_homework import seed_demo_homework
        seed_database(db)
        seed_demo_homework(db)
        _auto_ingest_courses(db)
    yield
    logger.info("Shutting down...")


def _auto_ingest_courses(db):
    """Индексирует уроки из БД и файлы из data/course_docs/{course_id}/."""
    from pathlib import Path

    from app.models.course import Course
    from app.services.rag_service import ingest_documents, ingest_documents_from_db

    docs_base = Path("./data/course_docs")
    courses = db.query(Course).all()
    for course in courses:
        try:
            result = ingest_documents_from_db(course, db)
            logger.info(f"Auto-ingest DB [{course.id}]: {result}")
        except Exception as e:
            logger.warning(f"Auto-ingest DB [{course.id}] failed: {e}")

        course_dir = docs_base / course.id
        if course_dir.is_dir() and any(f.is_file() for f in course_dir.iterdir()):
            try:
                result = ingest_documents(str(course_dir), course.id)
                logger.info(f"Auto-ingest docs [{course.id}]: {result}")
            except Exception as e:
                logger.warning(f"Auto-ingest docs [{course.id}] failed: {e}")


app = FastAPI(
    title=f"{settings.ASSISTANT_NAME} API",
    description="Voice assistant with RAG for educational courses",
    version="2.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,      prefix="/api", tags=["chat"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(widget.router,    prefix="/api", tags=["widget"])
app.include_router(courses.router,   prefix="/api", tags=["courses"])
app.include_router(stt.router,       prefix="/api", tags=["stt"])
app.include_router(auth.router,      prefix="/api/auth", tags=["auth"])
app.include_router(homework_templates.router, prefix="/api/homework", tags=["homework-workshop"])
app.include_router(homework.router, prefix="/api/homework", tags=["homework"])
app.include_router(ultravox.router,  prefix="/api/ultravox", tags=["ultravox"])
app.include_router(adaptive.router, prefix="/api/adaptive", tags=["adaptive"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "assistant": settings.ASSISTANT_NAME,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "tts_provider": settings.TTS_PROVIDER,
        "tts_voice": settings.TTS_VOICE,
    }

from fastapi.staticfiles import StaticFiles
import os
if os.path.exists('static'):
    app.mount('/', StaticFiles(directory='static', html=True), name='static')
