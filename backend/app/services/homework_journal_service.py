"""Сводки для журнала и голосового ассистента преподавателя."""

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.homework import Homework, HomeworkAssignment, HomeworkStatus
from app.models.user import User, UserRole


def build_journal_summary(db: Session, teacher_id: int) -> dict:
    homeworks = (
        db.query(Homework)
        .filter((Homework.teacher_id == teacher_id) | (Homework.is_demo.is_(True)))
        .all()
    )
    courses = {c.id: c for c in db.query(Course).all()}

    course_stats: dict[str, dict] = defaultdict(lambda: {"grades": [], "pending_review": 0, "not_submitted": 0})
    not_submitted: list[dict] = []
    pending_review: list[dict] = []
    student_stats: dict[int, dict] = {}

    for hw in homeworks:
        ctitle = courses.get(hw.course_id).title if hw.course_id in courses else hw.course_id
        for a in hw.assignments:
            sid = a.student_id
            if sid not in student_stats:
                student_stats[sid] = {
                    "student_id": sid,
                    "student_name": a.student.username if a.student else f"#{sid}",
                    "graded_count": 0,
                    "pending_count": 0,
                    "submitted_count": 0,
                    "grade_sum": 0,
                }
            st = student_stats[sid]

            if a.status == HomeworkStatus.graded.value and a.grade is not None:
                course_stats[hw.course_id]["grades"].append(a.grade)
                st["graded_count"] += 1
                st["grade_sum"] += a.grade
            elif a.status == HomeworkStatus.submitted.value:
                course_stats[hw.course_id]["pending_review"] += 1
                st["submitted_count"] += 1
                pending_review.append(
                    {
                        "homework_id": hw.id,
                        "assignment_id": a.id,
                        "homework_title": hw.title,
                        "course_id": hw.course_id,
                        "course_title": ctitle,
                        "student_id": sid,
                        "student_name": st["student_name"],
                    }
                )
            elif a.status == HomeworkStatus.pending.value:
                course_stats[hw.course_id]["not_submitted"] += 1
                st["pending_count"] += 1
                not_submitted.append(
                    {
                        "homework_id": hw.id,
                        "homework_title": hw.title,
                        "course_id": hw.course_id,
                        "course_title": ctitle,
                        "student_id": sid,
                        "student_name": st["student_name"],
                    }
                )

    courses_out = []
    for cid, data in course_stats.items():
        grades = data["grades"]
        courses_out.append(
            {
                "course_id": cid,
                "course_title": courses.get(cid).title if cid in courses else cid,
                "avg_grade": round(sum(grades) / len(grades), 1) if grades else None,
                "pending_review": data["pending_review"],
                "not_submitted": data["not_submitted"],
            }
        )
    courses_out.sort(key=lambda x: x["course_title"] or "")

    all_grades = [g for d in course_stats.values() for g in d["grades"]]
    students_out = []
    for st in student_stats.values():
        gc = st["graded_count"]
        students_out.append(
            {
                "student_id": st["student_id"],
                "student_name": st["student_name"],
                "avg_grade": round(st["grade_sum"] / gc, 1) if gc else None,
                "pending_count": st["pending_count"],
                "submitted_count": st["submitted_count"],
                "graded_count": gc,
            }
        )
    students_out.sort(key=lambda x: x["student_name"])

    return {
        "overall_avg": round(sum(all_grades) / len(all_grades), 1) if all_grades else None,
        "pending_review_count": len(pending_review),
        "not_submitted_count": len(not_submitted),
        "courses": courses_out,
        "students": students_out,
        "not_submitted": not_submitted[:30],
        "pending_review": pending_review[:30],
    }


def build_reminders(db: Session, user: User) -> dict:
    if user.role == UserRole.teacher.value:
        summary = build_journal_summary(db, user.id)
        return {
            "role": "teacher",
            "pending_review_count": summary["pending_review_count"],
            "not_submitted_count": summary["not_submitted_count"],
            "pending_review": summary["pending_review"][:10],
            "not_submitted": summary["not_submitted"][:10],
            "message": _teacher_reminder_message(summary),
        }

    assignments = (
        db.query(HomeworkAssignment)
        .filter(HomeworkAssignment.student_id == user.id)
        .all()
    )
    courses = {c.id: c for c in db.query(Course).all()}
    pending = []
    waiting = []
    recent_grades = []

    for a in assignments:
        hw = a.homework
        if not hw:
            continue
        item = {
            "homework_id": hw.id,
            "assignment_id": a.id,
            "title": hw.title,
            "course_id": hw.course_id,
            "course_title": courses.get(hw.course_id).title if hw.course_id in courses else hw.course_id,
            "status": a.status,
        }
        if a.status == HomeworkStatus.pending.value:
            pending.append(item)
        elif a.status == HomeworkStatus.submitted.value:
            waiting.append(item)
        elif a.status == HomeworkStatus.graded.value and a.grade is not None:
            recent_grades.append({**item, "grade": a.grade})

    recent_grades.sort(key=lambda x: x["homework_id"], reverse=True)

    from app.services.weak_topics_service import format_weak_topics_message, get_weak_topics

    weak = get_weak_topics(db, user.id, None, min_wrong=1, limit=5)
    adaptive_msg = format_weak_topics_message(weak)
    base_msg = _student_reminder_message(pending, waiting)
    if adaptive_msg:
        base_msg = f"{base_msg} {adaptive_msg}".strip()

    return {
        "role": "student",
        "pending_count": len(pending),
        "waiting_count": len(waiting),
        "pending": pending,
        "waiting": waiting,
        "recent_grades": recent_grades[:5],
        "weak_topics": weak,
        "adaptive_message": adaptive_msg,
        "message": base_msg,
    }


def _teacher_reminder_message(summary: dict) -> str:
    pr = summary["pending_review_count"]
    ns = summary["not_submitted_count"]
    parts = []
    if pr:
        parts.append(f"{pr} работ на проверке")
    if ns:
        parts.append(f"{ns} не сдано")
    if not parts:
        return "Все домашние задания сданы и проверены."
    return "Напоминание: " + ", ".join(parts) + "."


def _student_reminder_message(pending: list, waiting: list) -> str:
    parts = []
    if pending:
        parts.append(f"{len(pending)} заданий не сдано")
    if waiting:
        parts.append(f"{len(waiting)} на проверке у преподавателя")
    if not parts:
        return "Все домашние задания сданы. Отличная работа!"
    return "Напоминание: " + ", ".join(parts) + "."
