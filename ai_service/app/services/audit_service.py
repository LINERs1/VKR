"""Audit log — кто, когда и какое действие ИИ выполнил."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    user_id: int | None = None,
    session_id: str | None = None,
    resource: str | None = None,
    success: bool = True,
    meta: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            session_id=session_id,
            action=action,
            resource=resource,
            success=1 if success else 0,
            meta_json=json.dumps(meta or {}, ensure_ascii=False) if meta else None,
        )
    )
    db.commit()


def query_audit_log(
    db: Session,
    *,
    days: int = 7,
    action: str | None = None,
    user_id: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(AuditLog).filter(AuditLog.created_at >= since)
    if action:
        q = q.filter(AuditLog.action == action)
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    rows = q.order_by(AuditLog.created_at.desc()).limit(limit).all()
    out: list[dict[str, Any]] = []
    for r in rows:
        meta = None
        if r.meta_json:
            try:
                meta = json.loads(r.meta_json)
            except json.JSONDecodeError:
                meta = {"raw": r.meta_json}
        out.append({
            "id": r.id,
            "user_id": r.user_id,
            "session_id": r.session_id,
            "action": r.action,
            "resource": r.resource,
            "success": bool(r.success),
            "meta": meta,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out
