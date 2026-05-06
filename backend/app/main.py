import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, documents
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.ASSISTANT_NAME} backend")
    logger.info(f"🤖 LLM: {settings.LLM_PROVIDER} / {settings.LLM_MODEL}")
    logger.info(f"🔊 TTS: {'ElevenLabs' if settings.ELEVENLABS_API_KEY else 'Browser (no API key)'}")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title=f"{settings.ASSISTANT_NAME} API",
    description="Voice assistant with RAG for educational courses",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(documents.router, prefix="/api", tags=["documents"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "assistant": settings.ASSISTANT_NAME,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
        "tts": "elevenlabs" if settings.ELEVENLABS_API_KEY else "browser",
    }
