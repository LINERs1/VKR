import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import courses, homework, homework_templates, auth, notifications, materials
from app.api import ai_integration
from app.config import settings
from app.database import Base, engine, SessionLocal
import app.models.course        # noqa: F401
import app.models.homework      # noqa: F401
import app.models.homework_template  # noqa: F401
import app.models.user          # noqa: F401
import app.models.notification  # noqa: F401
import app.models.course_material  # noqa: F401
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


def _migrate_sqlite_columns():
    stmts = [
        "ALTER TABLE homeworks ADD COLUMN content_json TEXT",
        "ALTER TABLE homeworks ADD COLUMN is_demo INTEGER DEFAULT 0",
        "ALTER TABLE homework_assignments ADD COLUMN student_quiz_json TEXT",
        "ALTER TABLE homework_assignments ADD COLUMN ai_review_json TEXT",
        "ALTER TABLE homework_assignments ADD COLUMN hint_count INTEGER DEFAULT 0",
        "ALTER TABLE homework_assignments ADD COLUMN last_hint_at TEXT",
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Platform Service started")
    logger.info(f"AI Service URL: {settings.AI_SERVICE_URL}")
    with SessionLocal() as db:
        from app.utils.seed import seed_database
        seed_database(db)
        try:
            from app.utils.seed_homework import seed_demo_homework
            seed_demo_homework(db)
        except Exception as e:
            logger.warning(f"seed_demo_homework skipped: {e}")
    yield
    logger.info("Platform Service stopped.")


app = FastAPI(
    title="Educational Platform API",
    description="Образовательная платформа с интеграцией голосового ИИ-ассистента",
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

app.include_router(auth.router,               prefix="/api/auth",     tags=["auth"])
app.include_router(courses.router,            prefix="/api",          tags=["courses"])
app.include_router(homework.router,           prefix="/api/homework", tags=["homework"])
app.include_router(homework_templates.router, prefix="/api/homework", tags=["homework-workshop"])
app.include_router(notifications.router,      prefix="/api/notifications", tags=["notifications"])
app.include_router(materials.router,          prefix="/api/materials", tags=["materials"])
app.include_router(ai_integration.router,     prefix="/api/ai",       tags=["ai-integration"])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "platform_service",
        "ai_service_url": settings.AI_SERVICE_URL,
    }

@app.get("/")
async def root():
    return RedirectResponse(url="/docs")
