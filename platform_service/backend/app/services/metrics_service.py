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
        "chat_rag": stats("chat_rag"),
        "chat_llm": stats("chat_llm"),
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
        if r.event_type in ("chat_rag", "chat_llm"):
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
        if r.event_type == "chat_llm":
            llm_daily[day].append(float(r.duration_ms))
        elif r.event_type == "chat_rag":
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

    # ── 3. Статистика ДЗ (общая) ──────────────────────────────────────────
    hw_stats = {
        "total": 0, "submitted": 0, "graded": 0,
        "avg_grade": None, "grade_distribution": {}
    }
    try:
        result = db.execute(text(
            "SELECT status, grade FROM homework_assignments WHERE created_at >= :since"
        ), {"since": since.isoformat()})
        grades = []
        grade_dist: dict[str, int] = defaultdict(int)
        for row in result:
            hw_stats["total"] += 1
            status = row[0]
            grade = row[1]
            if status in ("submitted", "graded"):
                hw_stats["submitted"] += 1
            if status == "graded":
                hw_stats["graded"] += 1
                if grade is not None:
                    grades.append(float(grade))
                    grade_dist[str(int(grade))] += 1
        if grades:
            hw_stats["avg_grade"] = round(sum(grades) / len(grades), 2)
        hw_stats["grade_distribution"] = dict(grade_dist)
    except Exception:
        pass

    # ── 4. ДЗ по дням ────────────────────────────────────────────────────
    hw_daily: dict[str, dict] = {}
    try:
        result = db.execute(text(
            "SELECT date(created_at), status FROM homework_assignments WHERE created_at >= :since"
        ), {"since": since.isoformat()})
        for row in result:
            day = str(row[0])
            if day not in hw_daily:
                hw_daily[day] = {"date": day, "submitted": 0, "graded": 0}
            if row[1] in ("submitted", "graded"):
                hw_daily[day]["submitted"] += 1
            if row[1] == "graded":
                hw_daily[day]["graded"] += 1
    except Exception:
        pass

    hw_by_day = []
    for d in all_days:
        day = d["date"]
        hw_by_day.append(hw_daily.get(day, {"date": day, "submitted": 0, "graded": 0}))

    # ── 5. Активность студентов ───────────────────────────────────────────
    student_activity = []
    try:
        result = db.execute(text(
            """
            SELECT u.username, COUNT(m.id) as msg_count, MAX(m.created_at) as last_active
            FROM users u
            LEFT JOIN chat_messages m ON m.user_id = u.id AND m.created_at >= :since
            WHERE u.role = 'student'
            GROUP BY u.id, u.username
            ORDER BY msg_count DESC
            LIMIT 20
            """
        ), {"since": since.isoformat()})
        for row in result:
            student_activity.append({
                "username": row[0],
                "message_count": int(row[1] or 0),
                "last_active": str(row[2]) if row[2] else None,
            })
    except Exception:
        pass

    # ── 6. Топ слабых тем ─────────────────────────────────────────────────
    weak_topics = []
    try:
        result = db.execute(text(
            """
            SELECT topic, SUM(wrong_count) as total_wrong, COUNT(DISTINCT user_id) as students_count
            FROM student_weak_topics
            GROUP BY topic
            ORDER BY total_wrong DESC
            LIMIT 10
            """
        ))
        for row in result:
            weak_topics.append({
                "topic": row[0],
                "total_wrong": int(row[1] or 0),
                "students_count": int(row[2] or 0),
            })
    except Exception:
        pass

    # ── 7. Навигация ──────────────────────────────────────────────────────
    nav_total = by_type_count.get("voice_navigation", 0)
    nav_ok = sum(1 for r in metrics_rows if r.event_type == "voice_navigation" and r.success)

    return {
        "period_days": days,
        "summary": {
            "total_ai_events": len(metrics_rows),
            "total_chat_queries": by_type_count.get("chat_rag", 0),
            "total_voice_navigations": nav_total,
            "voice_success_rate": round(nav_ok / nav_total, 2) if nav_total else None,
            "total_hw_submitted": hw_stats["submitted"],
            "total_hw_graded": hw_stats["graded"],
            "avg_grade": hw_stats["avg_grade"],
            "active_students": len([s for s in student_activity if s["message_count"] > 0]),
        },
        "daily_events": all_days,
        "perf_by_day": perf_by_day,
        "homework": hw_stats,
        "hw_by_day": hw_by_day,
        "student_activity": student_activity,
        "weak_topics": weak_topics,
    }
