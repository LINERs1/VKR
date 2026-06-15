"""Сбор метрик для главы «Тестирование»."""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
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

    # BUG FIX: count ALL events by type, not just those with duration_ms
    by_type_count: dict[str, int] = defaultdict(int)
    by_type_ms: dict[str, list[float]] = defaultdict(list)
    nav_ok = nav_fail = 0

    for r in rows:
        by_type_count[r.event_type] += 1
        if r.duration_ms is not None:
            by_type_ms[r.event_type].append(float(r.duration_ms))
        if r.event_type == "voice_navigation":
            if r.success:
                nav_ok += 1
            else:
                nav_fail += 1

    def stats(event_type: str) -> dict:
        count = by_type_count.get(event_type, 0)
        vals = by_type_ms.get(event_type, [])
        return {
            "count": count,
            "avg_ms": round(sum(vals) / len(vals), 1) if vals else None,
            "min_ms": round(min(vals), 1) if vals else None,
            "max_ms": round(max(vals), 1) if vals else None,
        }

    return {
        "period_days": days,
        "total_events": len(rows),
        "chat_rag": stats("voice_rag"),
        "chat_llm": stats("voice_session"),
        "ai_homework_review": stats("ai_homework_review"),
        "homework_hint": stats("homework_hint"),
        "voice_navigation": {
            "success": nav_ok,
            "failed": nav_fail,
            "success_rate": round(nav_ok / (nav_ok + nav_fail), 2) if (nav_ok + nav_fail) else None,
        },
    }


def build_detailed_analytics(db: Session, *, days: int = 30) -> dict[str, Any]:
    """Детальная аналитика для дашборда: по дням, студентам, ДЗ."""
    since = datetime.utcnow() - timedelta(days=days)

    # ── 1. Метрики ИИ по дням ──────────────────────────────────────────────
    metrics_rows = (
        db.query(AssistantMetric)
        .filter(AssistantMetric.created_at >= since)
        .all()
    )

    # Count all events by type for summary
    by_type_count: dict[str, int] = defaultdict(int)
    for r in metrics_rows:
        by_type_count[r.event_type] += 1

    daily_events: dict[str, dict] = {}
    for r in metrics_rows:
        day = r.created_at.strftime("%Y-%m-%d") if r.created_at else None
        if not day:
            continue
        if day not in daily_events:
            daily_events[day] = {"date": day, "total": 0, "chat": 0, "voice": 0}
        daily_events[day]["total"] += 1
        if r.event_type in ("voice_rag", "voice_session"):
            daily_events[day]["chat"] += 1
        elif r.event_type == "voice_navigation":
            daily_events[day]["voice"] += 1

    # Fill all days in period (including zeros)
    all_days = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        all_days.append(daily_events.get(d, {"date": d, "total": 0, "chat": 0, "voice": 0}))

    # ── 2. Производительность LLM по дням ────────────────────────────────
    llm_daily: dict[str, list[float]] = defaultdict(list)
    rag_daily: dict[str, list[float]] = defaultdict(list)
    for r in metrics_rows:
        day = r.created_at.strftime("%Y-%m-%d") if r.created_at else None
        if not day or r.duration_ms is None:
            continue
        if r.event_type == "voice_session":
            llm_daily[day].append(float(r.duration_ms))
        elif r.event_type == "voice_rag":
            rag_daily[day].append(float(r.duration_ms))

    perf_by_day = []
    for d in all_days:
        day = d["date"]
        llm_vals = llm_daily.get(day, [])
        rag_vals = rag_daily.get(day, [])
        perf_by_day.append({
            "date": day,
            "llm_avg_ms": round(sum(llm_vals) / len(llm_vals)) if llm_vals else None,
            "rag_avg_ms": round(sum(rag_vals) / len(rag_vals)) if rag_vals else None,
        })


    # ── 5. Активность студентов ───────────────────────────────────────────
    student_activity = []
    try:
        result = db.execute(text(
            """
            SELECT user_id, COUNT(id) as msg_count, MAX(created_at) as last_active
            FROM assistant_metrics
            WHERE event_type IN ('voice_session', 'voice_navigation', 'voice_rag') AND created_at >= :since
            GROUP BY user_id
            ORDER BY msg_count DESC
            LIMIT 20
            """
        ), {"since": since.isoformat()})
        for row in result:
            user_id = row[0]
            student_activity.append({
                "username": f"Студент #{user_id}",
                "message_count": int(row[1] or 0),
                "last_active": str(row[2]) if row[2] else None,
            })
    except Exception:
        pass

    # ── 7. Навигация ──────────────────────────────────────────────────────
    nav_total = by_type_count.get("voice_navigation", 0)
    nav_ok = sum(1 for r in metrics_rows if r.event_type == "voice_navigation" and r.success)

    all_llm_vals = [float(r.duration_ms) for r in metrics_rows if r.event_type == "voice_session" and r.duration_ms is not None]
    avg_voice_session_ms = round(sum(all_llm_vals) / len(all_llm_vals)) if all_llm_vals else None

    return {
        "period_days": days,
        "summary": {
            "total_ai_events": len(metrics_rows),
            "total_chat_queries": by_type_count.get("voice_rag", 0),
            "total_voice_navigations": nav_total,
            "voice_success_rate": round(nav_ok / nav_total, 2) if nav_total else None,
            "avg_voice_session_ms": avg_voice_session_ms,
            "active_students": len([s for s in student_activity if s["message_count"] > 0]),
        },
        "daily_events": all_days,
        "perf_by_day": perf_by_day,
        "student_activity": student_activity,
        "weak_topics": [],
    }
