"""Сбор метрик для главы «Тестирование»."""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assistant_metric import AssistantMetric


def record_metric(
    db: Session,
    *,
    event_type: str,
    user_id: int | None = None,
    course_id: str | None = None,
    duration_ms: float | None = None,
    success: bool = True,
    meta: dict | None = None,
) -> None:
    db.add(
        AssistantMetric(
            user_id=user_id,
            event_type=event_type,
            course_id=course_id,
            duration_ms=duration_ms,
            success=1 if success else 0,
            meta_json=json.dumps(meta or {}, ensure_ascii=False) if meta else None,
        )
    )
    db.commit()


def build_analytics_summary(db: Session, *, days: int = 7) -> dict[str, Any]:
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(AssistantMetric)
        .filter(AssistantMetric.created_at >= since)
        .all()
    )
    by_type: dict[str, list[float]] = defaultdict(list)
    nav_ok = nav_fail = 0
    for r in rows:
        if r.duration_ms is not None:
            by_type[r.event_type].append(float(r.duration_ms))
        if r.event_type == "voice_navigation":
            if r.success:
                nav_ok += 1
            else:
                nav_fail += 1

    def stats(vals: list[float]) -> dict:
        if not vals:
            return {"count": 0, "avg_ms": None, "min_ms": None, "max_ms": None}
        return {
            "count": len(vals),
            "avg_ms": round(sum(vals) / len(vals), 1),
            "min_ms": round(min(vals), 1),
            "max_ms": round(max(vals), 1),
        }

    return {
        "period_days": days,
        "total_events": len(rows),
        "chat_rag": stats(by_type.get("chat_rag", [])),
        "chat_llm": stats(by_type.get("chat_llm", [])),
        "ai_homework_review": stats(by_type.get("ai_homework_review", [])),
        "homework_hint": stats(by_type.get("homework_hint", [])),
        "voice_navigation": {
            "success": nav_ok,
            "failed": nav_fail,
            "success_rate": round(nav_ok / (nav_ok + nav_fail), 2) if (nav_ok + nav_fail) else None,
        },
    }
