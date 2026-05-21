from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.adaptive import (
    AnalyticsEventIn,
    AnalyticsSummaryResponse,
    DetailedAnalyticsResponse,
)
from app.services.auth_service import get_current_user, get_current_user_optional
from app.services.metrics_service import (
    build_analytics_summary,
    build_detailed_analytics,
    record_metric,
)

router = APIRouter()


@router.post("/event")
def post_analytics_event(
    body: AnalyticsEventIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    record_metric(
        db,
        event_type=body.event_type,
        user_id=current_user.id if current_user else None,
        course_id=body.course_id,
        duration_ms=body.duration_ms,
        success=body.success,
        meta=body.meta,
    )
    return {"ok": True}


@router.get("/summary", response_model=AnalyticsSummaryResponse)
def analytics_summary(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can view analytics")
    data = build_analytics_summary(db, days=days)
    return AnalyticsSummaryResponse(**data)


@router.get("/detailed")
def analytics_detailed(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can view analytics")
    return build_detailed_analytics(db, days=days)
