from typing import Optional
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.homework_review_service import review_assignment_raw
from app.services.platform_auth import verify_service_token
from app.services.audit_service import record_audit

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_service_token)])

class HomeworkCheckRequest(BaseModel):
    assignment_id: int
    username: str
    homework_description: str
    student_code: Optional[str] = None
    student_text: Optional[str] = None
    content_json: Optional[str] = None
    student_quiz: Optional[dict] = None
    is_demo: bool = False

@router.post("/check")
def check_homework(request: HomeworkCheckRequest, db: Session = Depends(get_db)):
    """
    Эндпоинт для проверки ДЗ.
    Платформа присылает данные, ИИ проверяет и возвращает оценку и фидбек.
    """
    logger.info(f"Получен запрос на проверку ДЗ (assignment_id={request.assignment_id})")

    try:
        result = review_assignment_raw(
            assignment_id=request.assignment_id,
            username=request.username,
            homework_description=request.homework_description,
            student_code=request.student_code or "",
            student_text=request.student_text or "",
            content_json=request.content_json or "",
            student_quiz=request.student_quiz or {},
            is_demo=request.is_demo,
        )
        record_audit(
            db,
            action="homework_check",
            resource=f"assignment:{request.assignment_id}",
            success=True,
            meta={"username": request.username, "grade": result.get("suggested_grade")},
        )
        return result
    except Exception as e:
        record_audit(
            db,
            action="homework_check",
            resource=f"assignment:{request.assignment_id}",
            success=False,
            meta={"error": str(e)[:200]},
        )
        raise
