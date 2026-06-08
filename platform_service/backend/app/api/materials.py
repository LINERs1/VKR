import os
import uuid
import json
import requests
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.course_material import CourseMaterial
from pydantic import BaseModel
from typing import List
from datetime import datetime
from langchain_community.document_loaders import PyPDFLoader

router = APIRouter()
logger = logging.getLogger(__name__)

# TODO: Move to config
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8000")
UPLOAD_DIR = "uploads/materials"

os.makedirs(UPLOAD_DIR, exist_ok=True)

class MaterialResponse(BaseModel):
    id: str
    course_id: str
    title: str
    file_path: str
    source_type: str
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[MaterialResponse])
def get_materials(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    materials = db.query(CourseMaterial).filter(CourseMaterial.course_id == course_id).all()
    return materials

@router.post("", response_model=MaterialResponse)
def upload_material(
    course_id: str = Form(...),
    source_type: str = Form("methodology"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Проверка на лимит (максимум 10 методичек на курс)
    existing_count = db.query(CourseMaterial).filter(CourseMaterial.course_id == course_id).count()
    if existing_count >= 10:
        raise HTTPException(status_code=400, detail="Достигнут лимит: максимум 10 методичек для одного курса.")

    # Проверка на дубликаты файлов
    existing_material = db.query(CourseMaterial).filter(CourseMaterial.course_id == course_id, CourseMaterial.title == file.filename).first()
    if existing_material:
        raise HTTPException(status_code=400, detail="Файл с таким именем уже загружен для этого курса.")

    material_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    save_path = os.path.join(UPLOAD_DIR, f"{material_id}{file_extension}")

    try:
        with open(save_path, "wb") as f:
            f.write(file.file.read())
        
        # Extract text using PyPDFLoader
        loader = PyPDFLoader(save_path)
        pages = loader.load()
        text = "\n".join([page.page_content for page in pages])
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from PDF (might be scanned images).")

        # Save to DB
        material = CourseMaterial(
            id=material_id,
            course_id=course_id,
            title=file.filename,
            file_path=save_path,
            source_type=source_type
        )
        db.add(material)
        db.commit()
        db.refresh(material)

        # Send webhook to AI Service
        payload = {
            "id": material.id,
            "course_id": material.course_id,
            "title": material.title,
            "content": text,
            "source_type": material.source_type
        }
        try:
            requests.post(f"{AI_SERVICE_URL}/webhook/content", json=payload, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send webhook to AI service: {e}")
            # We don't fail the upload, but log it. In production, we'd retry.

        return material

    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{material_id}")
def delete_material(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    material = db.query(CourseMaterial).filter(CourseMaterial.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    # Send delete webhook to AI Service
    try:
        requests.delete(f"{AI_SERVICE_URL}/webhook/content/{material.source_type}/{material.course_id}/{material.id}", timeout=5)
    except Exception as e:
        logger.error(f"Failed to send delete webhook to AI service: {e}")

    # Delete file
    if os.path.exists(material.file_path):
        os.remove(material.file_path)

    # Delete from DB
    db.delete(material)
    db.commit()

    return {"status": "ok", "deleted": material_id}
