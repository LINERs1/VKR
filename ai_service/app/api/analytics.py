from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any

from app.database import get_db
from app.schemas.analytics import (
    AnalyticsEventIn,
    AnalyticsSummaryResponse,
    DetailedAnalyticsResponse,
)
from app.services.auth_service import get_current_user, get_current_user_optional, DummyUser
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
    current_user: Any = Depends(get_current_user_optional),
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
    current_user: DummyUser = Depends(get_current_user),
):
    if current_user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Only teachers can view analytics")
    data = build_analytics_summary(db, days=days)
    return AnalyticsSummaryResponse(**data)


@router.get("/detailed")
def analytics_detailed(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: DummyUser = Depends(get_current_user),
):
    if current_user.role not in ("teacher", "admin"):
        raise HTTPException(status_code=403, detail="Only teachers can view analytics")
    return build_detailed_analytics(db, days=days)
