import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents, widget, courses
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.ASSISTANT_NAME} backend")
    logger.info(f"🤖 LLM:  {settings.LLM_PROVIDER} / {settings.LLM_MODEL}")
    logger.info(f"🔊 TTS:  {settings.TTS_PROVIDER} / {settings.TTS_VOICE}")
    logger.info(f"🌐 CORS: {settings.cors_origins}")
    # Auto-ingest demo course materials on startup
    _auto_ingest_courses()
    yield
    logger.info("Shutting down...")


def _auto_ingest_courses():
    """Automatically index demo course materials if files exist."""
    from pathlib import Path
    from app.services.rag_service import ingest_documents
    course_ids = ["python", "ml", "webdev", "sql"]
    for course_id in course_ids:
        course_dir = Path(f"./data/course_docs/{course_id}")
        if course_dir.exists() and any(course_dir.iterdir()):
            try:
                result = ingest_documents(str(course_dir), course_id)
                logger.info(f"Auto-ingest [{course_id}]: {result}")
            except Exception as e:
                logger.warning(f"Auto-ingest [{course_id}] failed: {e}")


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
