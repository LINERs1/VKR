import logging
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from app.services.rag_service import ingest_documents

logger = logging.getLogger(__name__)
router = APIRouter()

DOCS_DIR = Path("./data/course_docs")
DOCS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/ingest/upload")
async def upload_and_ingest(files: list[UploadFile] = File(...)):
    """Upload document files and index them into ChromaDB."""
    saved = []
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in {".pdf", ".docx", ".txt", ".md"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
        dest = DOCS_DIR / file.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved.append(file.filename)
        logger.info(f"Saved: {file.filename}")

    result = ingest_documents(str(DOCS_DIR))
    result["uploaded_files"] = saved
    return JSONResponse(content=result)


@router.post("/ingest/directory")
async def ingest_from_directory(path: str = str(DOCS_DIR)):
    """Index all documents from a server-side directory path."""
    if not Path(path).exists():
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")
    result = ingest_documents(path)
    return JSONResponse(content=result)


@router.get("/ingest/status")
async def ingest_status():
    """Return list of uploaded documents."""
    files = [f.name for f in DOCS_DIR.iterdir() if f.is_file()]
    return {"directory": str(DOCS_DIR), "files": files, "count": len(files)}
