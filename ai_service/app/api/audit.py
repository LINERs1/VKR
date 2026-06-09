"""Audit log API — журнал действий ИИ."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.services.audit_service import query_audit_log
from app.services.auth_service import get_current_user

router = APIRouter()


@router.get("/events")
def list_audit_events(
    days: int = Query(default=7, ge=1, le=90),
    action: str | None = None,
    user_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.teacher.value, UserRole.admin.value):
        raise HTTPException(status_code=403, detail="Only teachers can view audit log")
    events = query_audit_log(db, days=days, action=action, user_id=user_id, limit=limit)
    return {"period_days": days, "count": len(events), "events": events}
