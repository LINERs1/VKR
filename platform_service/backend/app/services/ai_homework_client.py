"""Проверка ДЗ через ИИ-сервис (stateless API)."""

from app.models.homework import Homework, HomeworkAssignment
from app.utils.ai_client import ai_post


def request_homework_review(homework: Homework, assignment: HomeworkAssignment) -> dict:
    return ai_post(
        "/api/homework/check",
        {
            "assignment_id": assignment.id,
            "username": assignment.student.username,
            "homework_description": homework.description,
            "student_code": assignment.student_code or "",
            "student_text": assignment.student_text or "",
            "content_json": homework.content_json or "",
            "student_quiz": assignment.student_quiz or {},
            "is_demo": bool(homework.is_demo),
        },
        timeout=180,
    )
