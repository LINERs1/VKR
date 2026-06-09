"""
REST API для запросов от ИИ-ассистента к платформе.

ИИ-сервис делает HTTP GET/PATCH запросы сюда когда ему нужны данные:
- GET  /api/ai/homeworks/{id}      — получить условие ДЗ
- GET  /api/ai/assignments/{id}    — получить код студента
- PATCH /api/ai/assignments/{id}   — сохранить оценку от ИИ
- GET  /api/ai/users/{id}          — получить роль и имя пользователя

Также содержит webhook-отправщики: при изменении данных платформа
сама уведомляет ИИ-сервис.
"""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.course import Course, Lesson
from app.models.homework import Homework, HomeworkAssignment
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# URL ИИ-сервиса (читается из env)
def _ai_url() -> str:
    try:
        from app.config import settings
        return settings.AI_SERVICE_URL
    except Exception:
        return "http://localhost:8000"


# ─── REST API для ИИ ─────────────────────────────────────────────────────────

@router.get("/homeworks/{homework_id}")
def get_homework(homework_id: int, db: Session = Depends(get_db)):
    """ИИ запрашивает условие домашнего задания."""
    hw = db.query(Homework).filter(Homework.id == homework_id).first()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    return {
        "id": hw.id,
        "title": hw.title,
        "description": hw.description,
        "course_id": hw.course_id,
    }


@router.get("/assignments/{assignment_id}")
def get_assignment(assignment_id: int, db: Session = Depends(get_db)):
    """ИИ запрашивает работу студента (код, статус) для проверки."""
    assignment = db.query(HomeworkAssignment).filter(
        HomeworkAssignment.id == assignment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    hw = db.query(Homework).filter(Homework.id == assignment.homework_id).first()
    student = db.query(User).filter(User.id == assignment.student_id).first()

    return {
        "id": assignment.id,
        "homework_id": assignment.homework_id,
        "homework_title": hw.title if hw else "",
        "homework_description": hw.description if hw else "",
        "student_id": assignment.student_id,
        "student_name": student.name if student else "",
        "student_code": assignment.student_code or "",
        "status": assignment.status,
    }


class GradePayload(BaseModel):
    grade: Optional[int] = None
    teacher_feedback: Optional[str] = None
    ai_review_json: Optional[str] = None
    status: Optional[str] = "graded"


@router.patch("/assignments/{assignment_id}")
def update_assignment_grade(
    assignment_id: int,
    payload: GradePayload,
    db: Session = Depends(get_db),
):
    """ИИ сохраняет оценку и фидбек после проверки работы."""
    assignment = db.query(HomeworkAssignment).filter(
        HomeworkAssignment.id == assignment_id
    ).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if payload.grade is not None:
        assignment.grade = payload.grade
    if payload.teacher_feedback is not None:
        assignment.teacher_feedback = payload.teacher_feedback
    if payload.ai_review_json is not None:
        assignment.ai_review_json = payload.ai_review_json
    if payload.status:
        assignment.status = payload.status

    db.commit()
    logger.info(f"✅ ИИ выставил оценку {payload.grade} за работу {assignment_id}")
    return {"status": "ok", "assignment_id": assignment_id, "grade": payload.grade}


@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """ИИ запрашивает имя и роль пользователя."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "email": user.email,
    }


# ─── Webhook-отправщики к ИИ-сервису ─────────────────────────────────────────

def _service_headers() -> dict[str, str]:
    from app.config import settings
    headers = {"Content-Type": "application/json"}
    if settings.SERVICE_API_KEY:
        headers["X-Service-Token"] = settings.SERVICE_API_KEY
    return headers


async def _notify_ai(method: str, path: str, data: dict = None):
    """Отправляет HTTP-запрос на ИИ-сервис."""
    url = f"{_ai_url()}{path}"
    headers = _service_headers()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if method == "POST":
                await client.post(url, json=data, headers=headers)
            elif method == "DELETE":
                await client.delete(url, headers=headers)
        logger.info(f"📡 Webhook → ИИ: {method} {path}")
    except Exception as e:
        logger.warning(f"⚠️ Webhook к ИИ не доставлен ({path}): {e}")


# Вызывается из api/courses.py при создании курса
async def notify_course_created(course_id: str, title: str):
    await _notify_ai("POST", "/webhook/course", {"id": course_id, "title": title})


# Вызывается из api/courses.py при удалении курса
async def notify_course_deleted(course_id: str):
    await _notify_ai("DELETE", f"/webhook/course/{course_id}")


# Вызывается из api/courses.py при создании урока
async def notify_lesson_created(lesson_id: int, course_id: str, title: str, content: str = ""):
    await _notify_ai("POST", "/webhook/lesson", {
        "id": lesson_id,
        "course_id": course_id,
        "title": title,
        "content": content,
    })


# Вызывается из api/courses.py при удалении урока
async def notify_lesson_deleted(lesson_id: int):
    await _notify_ai("DELETE", f"/webhook/lesson/{lesson_id}")
