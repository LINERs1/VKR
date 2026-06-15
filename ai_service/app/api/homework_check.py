from typing import Optional
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.services.homework_review_service import review_assignment_raw
from app.services.platform_auth import verify_service_token

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
def check_homework(request: HomeworkCheckRequest):
    """
    Эндпоинт для проверки ДЗ.
    Платформа присылает данные, ИИ проверяет и возвращает оценку и фидбек.
    """
    logger.info(f"Получен запрос на проверку ДЗ (assignment_id={request.assignment_id})")
    
    result = review_assignment_raw(
        assignment_id=request.assignment_id,
        username=request.username,
        homework_description=request.homework_description,
        student_code=request.student_code or "",
        student_text=request.student_text or "",
        content_json=request.content_json or "",
        student_quiz=request.student_quiz or {},
        is_demo=request.is_demo
    )
    
    return result
