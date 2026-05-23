import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.api import chat
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.ASSISTANT_NAME} AI Chat Prototype")
    logger.info(f"🤖 LLM:  {settings.LLM_PROVIDER} / {settings.LLM_MODEL}")
    logger.info(f"🌐 CORS: {settings.cors_origins}")
    
    # Auto-ingest documents from data/course_docs/
    from app.services.rag_service import ingest_documents
    docs_base = os.path.join(".", "data", "course_docs")
    for course_folder in ["course_1", "course_2"]:
        course_dir = os.path.join(docs_base, course_folder)
        if os.path.isdir(course_dir) and any(os.path.isfile(os.path.join(course_dir, f)) for f in os.listdir(course_dir)):
            try:
                result = ingest_documents(course_dir, course_folder)
                logger.info(f"Auto-ingest docs [{course_folder}]: {result}")
            except Exception as e:
                logger.warning(f"Auto-ingest docs [{course_folder}] failed: {e}")
    yield
    logger.info("Shutting down...")

app = FastAPI(
    title=f"{settings.ASSISTANT_NAME} Prototype API",
    description="Minimal AI chat prototype with strict RAG",
    version="3.0.0",
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

app.include_router(chat.router, prefix="/api", tags=["chat"])

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "assistant": settings.ASSISTANT_NAME,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.LLM_MODEL,
    }

import os
from pathlib import Path

def read_manual(course_folder):
    path = Path("data/course_docs") / course_folder / "manual.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Методичка не найдена."

MOCK_COURSES = [
    {
        "id": "course_1",
        "title": "Основы веб-разработки на Python и FastAPI",
        "description": "Изучите создание современных API",
        "icon": "🐍",
        "tags": ["Python", "FastAPI"],
        "lessons_count": 1,
        "duration": "10 мин",
        "students": 1200,
        "rating": 4.8,
        "instructor": "Иван Иванов",
        "lessons": [
            {"id": 1, "title": "Введение в FastAPI", "duration": "10 мин", "content": read_manual("course_1")}
        ]
    },
    {
        "id": "course_2",
        "title": "Основы фронтенд-разработки на Vue.js 3",
        "description": "Создание динамичных интерфейсов",
        "icon": "🟢",
        "tags": ["Vue.js", "Frontend"],
        "lessons_count": 1,
        "duration": "15 мин",
        "students": 900,
        "rating": 4.9,
        "instructor": "Анна Смирнова",
        "lessons": [
            {"id": 1, "title": "Composition API", "duration": "15 мин", "content": read_manual("course_2")}
        ]
    },
    {
        "id": "course_3",
        "title": "Машинное обучение для начинающих",
        "description": "Базовые концепции и алгоритмы",
        "icon": "🤖",
        "tags": ["ML", "AI"],
        "lessons_count": 0,
        "duration": "0 мин",
        "students": 1500,
        "rating": 4.7,
        "instructor": "Петр Петров",
        "lessons": []
    },
    {
        "id": "course_4",
        "title": "Введение в базы данных SQL",
        "description": "Проектирование и запросы",
        "icon": "💾",
        "tags": ["SQL", "DB"],
        "lessons_count": 0,
        "duration": "0 мин",
        "students": 800,
        "rating": 4.6,
        "instructor": "Сергей Сергеев",
        "lessons": []
    }
]

@app.get("/api/courses")
async def get_courses():
    return MOCK_COURSES

@app.get("/api/courses/{course_id}")
async def get_course(course_id: str):
    for c in MOCK_COURSES:
        if c["id"] == course_id:
            return c
    return MOCK_COURSES[0]

if os.path.exists('static'):
    app.mount('/', StaticFiles(directory='static', html=True), name='static')
