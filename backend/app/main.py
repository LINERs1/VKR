import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents, widget, courses, stt, auth, homework, ultravox
from app.config import settings
from app.database import Base, engine, SessionLocal
import app.models.homework # Ensure models are loaded
import app.models.user
import app.models.course

# Initialize database
Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.ASSISTANT_NAME} backend")
    logger.info(f"🤖 LLM:  {settings.LLM_PROVIDER} / {settings.LLM_MODEL}")
    logger.info(f"🔊 TTS:  {settings.TTS_PROVIDER} / {settings.TTS_VOICE}")
    logger.info(f"🌐 CORS: {settings.cors_origins}")
    # Auto-seed database and ingest course materials on startup
    with SessionLocal() as db:
        from app.utils.seed import seed_database
        seed_database(db)
        _auto_ingest_courses_from_db(db)
    yield
    logger.info("Shutting down...")


def _auto_ingest_courses_from_db(db):
    """Automatically index course materials from SQLite database."""
    from app.services.rag_service import ingest_documents_from_db
    from app.models.course import Course
    
    courses = db.query(Course).all()
    for course in courses:
        try:
            result = ingest_documents_from_db(course, db)
            logger.info(f"Auto-ingest [{course.id}]: {result}")
        except Exception as e:
            logger.warning(f"Auto-ingest [{course.id}] failed: {e}")


app = FastAPI(
    title=f"{settings.ASSISTANT_NAME} API",
    description="Voice assistant with RAG for educational courses",
    version="2.0.0",
    lifespan=lifespan,
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
app.include_router(homework.router,  prefix="/api/homework", tags=["homework"])
app.include_router(ultravox.router,  prefix="/api/ultravox", tags=["ultravox"])


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
