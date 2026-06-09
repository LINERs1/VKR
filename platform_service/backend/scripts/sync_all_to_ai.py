#!/usr/bin/env python3
"""
Первичная синхронизация всех курсов и уроков платформы → ИИ-сервис.

Запуск (из platform_service/backend):
    python scripts/sync_all_to_ai.py

Нужно: ai_service запущен, SERVICE_API_KEY одинаковый в обоих .env (или пустой в dev).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.course import Course, Lesson
from app.models.homework import Homework  # noqa: F401
from app.models.user import User  # noqa: F401
from app.utils.ai_client import send_webhook


def sync_all() -> None:
    with SessionLocal() as db:
        courses = db.query(Course).all()
        if not courses:
            print("На платформе нет курсов — сначала выполните seed или создайте курсы.")
            return

        for course in courses:
            print(f"-> course {course.id}: {course.title}")
            send_webhook("/webhook/course", {"id": course.id, "title": course.title})

            lessons: list[Lesson] = (
                db.query(Lesson)
                .filter(Lesson.course_id == course.id)
                .order_by(Lesson.id)
                .all()
            )
            for lesson in lessons:
                print(f"   -> lesson {lesson.id}: {lesson.title[:60]}")
                send_webhook(
                    "/webhook/lesson",
                    {
                        "id": lesson.id,
                        "course_id": lesson.course_id,
                        "title": lesson.title,
                        "content": lesson.content or "",
                    },
                    timeout=30,
                )

        print(f"\nDone: {len(courses)} courses synced.")


if __name__ == "__main__":
    sync_all()
