"""Учёт ошибок в тестах и адаптивные подсказки по темам."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.mirror import CourseRef, LessonRef
from app.models.student_weak_topic import StudentWeakTopic
from app.schemas.homework_template import HomeworkTemplateContent, QuizItem
from app.services.homework_template_service import parse_content


def record_quiz_weak_topics(
    db: Session,
    *,
    student_id: int,
    course_id: str,
    content_json: str | None,
    student_quiz_json: str | None,
) -> None:
    """После сдачи ДЗ: увеличить счётчик по темам с неверными ответами."""
    if not content_json or not student_quiz_json:
        return
    import json

    try:
        answers = json.loads(student_quiz_json)
    except json.JSONDecodeError:
        return
    content = HomeworkTemplateContent(**parse_content(content_json))
    for i, q in enumerate(content.quiz_items):
        if not q.options:
            continue
        topic = (q.topic or "").strip()
        if not topic:
            continue
        key = str(i)
        picked = answers.get(key)
        if picked is None:
            picked = answers.get(i)
        if picked is None:
            continue
        try:
            picked_i = int(picked)
            correct = int(q.correct_index or 0)
        except (TypeError, ValueError):
            continue
        if picked_i == correct:
            continue
        _bump_weak(db, student_id, course_id, topic, q.lesson_id)


def _bump_weak(
    db: Session,
    student_id: int,
    course_id: str,
    topic: str,
    lesson_id: int | None,
) -> None:
    row = (
        db.query(StudentWeakTopic)
        .filter(
            StudentWeakTopic.student_id == student_id,
            StudentWeakTopic.course_id == course_id,
            StudentWeakTopic.topic == topic,
        )
        .first()
    )
    if row:
        row.wrong_count += 1
        row.last_wrong_at = datetime.utcnow()
        if lesson_id is not None:
            row.lesson_id = lesson_id
    else:
        db.add(
            StudentWeakTopic(
                student_id=student_id,
                course_id=course_id,
                topic=topic,
                lesson_id=lesson_id,
                wrong_count=1,
            )
        )


def get_weak_topics(
    db: Session,
    student_id: int,
    course_id: str | None = None,
    *,
    min_wrong: int = 1,
    limit: int = 10,
) -> list[dict]:
    q = db.query(StudentWeakTopic).filter(
        StudentWeakTopic.student_id == student_id,
        StudentWeakTopic.wrong_count >= min_wrong,
    )
    if course_id and course_id != "default":
        q = q.filter(StudentWeakTopic.course_id == course_id)
    rows = q.order_by(StudentWeakTopic.wrong_count.desc()).limit(limit).all()
    courses = {c.id: c for c in db.query(CourseRef).all()}
    lessons = {l.id: l for l in db.query(LessonRef).all()}
    out = []
    for r in rows:
        lesson = lessons.get(r.lesson_id) if r.lesson_id else None
        course = courses.get(r.course_id)
        out.append(
            {
                "topic": r.topic,
                "wrong_count": r.wrong_count,
                "course_id": r.course_id,
                "course_title": course.title if course else r.course_id,
                "lesson_id": r.lesson_id,
                "lesson_title": lesson.title if lesson else None,
                "last_wrong_at": r.last_wrong_at.isoformat() if r.last_wrong_at else None,
            }
        )
    return out


def build_weak_topics_prompt_block(
    db: Session,
    student_id: int,
    course_id: str | None,
) -> str:
    items = get_weak_topics(db, student_id, course_id, min_wrong=1, limit=5)
    if not items:
        return ""
    lines = ["СЛАБЫЕ ТЕМЫ УЧЕНИКА (ошибки в тестах ДЗ):"]
    for it in items:
        extra = ""
        if it.get("lesson_title"):
            extra = f", урок «{it['lesson_title']}»"
        lines.append(
            f"- «{it['topic']}»: ошибок {it['wrong_count']}{extra}. "
            f"При уместности мягко предложи повторить тему или открыть урок."
        )
    return "\n".join(lines)


def format_weak_topics_message(items: list[dict]) -> str:
    if not items:
        return ""
    parts = []
    for it in items[:3]:
        topic = it["topic"]
        n = it["wrong_count"]
        if n >= 2:
            parts.append(f"вы {n} раза ошибались в вопросах про «{topic}»")
        else:
            parts.append(f"была ошибка в теме «{topic}»")
    if not parts:
        return ""
    joined = ", ".join(parts)
    lesson = items[0]
    suffix = ""
    if lesson.get("lesson_id") and lesson.get("course_id"):
        suffix = f" Могу открыть урок «{lesson.get('lesson_title') or 'по теме'}»."
    return f"По тестам: {joined}.{suffix} Хотите, разберём подробнее?"
