import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.rag_service import ingest_documents

logger = logging.getLogger(__name__)
router = APIRouter()

DOCS_BASE_DIR = Path("./data/course_docs")


def get_course_dir(course_id: str) -> Path:
    """Каждый курс хранит документы в своей папке."""
    course_dir = DOCS_BASE_DIR / course_id
    course_dir.mkdir(parents=True, exist_ok=True)
    return course_dir


@router.post("/ingest/upload")
async def upload_and_ingest(
    files: list[UploadFile] = File(...),
    course_id: str = Query(default=settings.DEFAULT_COURSE_ID),
):
    """Загружает файлы и индексирует их в ChromaDB для конкретного курса."""
    course_dir = get_course_dir(course_id)
    saved = []

    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in {".pdf", ".docx", ".txt", ".md"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
        dest = course_dir / file.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved.append(file.filename)
        logger.info(f"Saved: {file.filename} (course={course_id})")

    result = ingest_documents(str(course_dir), course_id)
    result["uploaded_files"] = saved
    result["course_id"] = course_id
    return JSONResponse(content=result)


@router.post("/ingest/directory")
async def ingest_from_directory(
    path: str | None = None,
    course_id: str = Query(default=settings.DEFAULT_COURSE_ID),
):
    """Индексирует все документы из папки курса на сервере."""
    if path is None:
        path = str(get_course_dir(course_id))
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")
    result = ingest_documents(path, course_id)
    result["course_id"] = course_id
    return JSONResponse(content=result)


@router.get("/ingest/status")
async def ingest_status(
    course_id: str = Query(default=settings.DEFAULT_COURSE_ID),
):
    """Возвращает список загруженных документов курса."""
    course_dir = get_course_dir(course_id)
    files = [f.name for f in course_dir.iterdir() if f.is_file()]
    return {"course_id": course_id, "directory": str(course_dir), "files": files, "count": len(files)}
