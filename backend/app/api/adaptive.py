from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.adaptive import WeakTopicsResponse, WeakTopicItem
from app.services.auth_service import get_current_user
from app.services.weak_topics_service import format_weak_topics_message, get_weak_topics

router = APIRouter()


@router.get("/weak-topics", response_model=WeakTopicsResponse)
def list_weak_topics(
    course_id: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.student.value:
        return WeakTopicsResponse(items=[], message="")
    items = get_weak_topics(db, current_user.id, course_id)
    return WeakTopicsResponse(
        items=[WeakTopicItem(**x) for x in items],
        message=format_weak_topics_message(items),
    )
