import json
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import or_
from sqlalchemy.orm import Session  # noqa: F401 — used in type hints

from app.database import get_db, SessionLocal
from app.models.homework import Homework, HomeworkAssignment, HomeworkStatus
from app.models.user import User, UserRole
from app.models.notification import Notification
from app.schemas.homework import (
    HomeworkAiReviewResponse,
    HomeworkAssignmentResponse,
    HomeworkCreate,
    HomeworkGrade,
    HomeworkHintRequest,
    HomeworkHintResponse,
    HomeworkRemindersResponse,
    HomeworkResponse,
    HomeworkSubmit,
    JournalSummaryResponse,
)
from app.schemas.homework_template import HomeworkTemplateContent, QuizItem
from app.config import settings
from app.models.assistant_metric import AssistantMetric
from app.services.ai_homework_client import request_homework_review
from app.services.auth_service import get_current_user
from app.services.homework_hint_service import generate_homework_hint
from app.services.homework_journal_service import build_journal_summary, build_reminders
from app.services.homework_template_service import parse_content
from app.services.metrics_service import record_metric

router = APIRouter()


def _count_recent_ai_reviews(db: Session, teacher_id: int) -> int:
    since = datetime.utcnow() - timedelta(hours=1)
    return (
        db.query(AssistantMetric)
        .filter(
            AssistantMetric.user_id == teacher_id,
            AssistantMetric.event_type == "ai_homework_review",
            AssistantMetric.created_at >= since,
            AssistantMetric.success == 1,
        )
        .count()
    )


def _sanitize_content_for_student(content: HomeworkTemplateContent) -> HomeworkTemplateContent:
    return content.model_copy(
        update={
            "quiz_items": [
                QuizItem(
                    question=q.question,
                    options=q.options,
                    correct_index=None,
                    topic="",
                    lesson_id=None,
                )
                for q in content.quiz_items
            ]
        }
    )


def _attach_content(hw: Homework, *, for_student: bool = False) -> HomeworkResponse:
    # Set student_name BEFORE model_validate so Pydantic picks it up
    for a in hw.assignments:
        a.student_name = a.student.full_name or a.student.username
    resp = HomeworkResponse.model_validate(hw)
    if hw.content_json:
        parsed = HomeworkTemplateContent(**parse_content(hw.content_json))
        resp.content = _sanitize_content_for_student(parsed) if for_student else parsed
    return resp


def _can_teacher_access_homework(user: User, homework: Homework) -> bool:
    return homework.teacher_id == user.id or bool(getattr(homework, "is_demo", False))


@router.post("", response_model=HomeworkResponse)
def create_homework(
    hw_in: HomeworkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can create homeworks")

    students = db.query(User).filter(
        User.id.in_(hw_in.student_ids), User.role == UserRole.student.value
    ).all()
    if len(students) != len(hw_in.student_ids):
        raise HTTPException(status_code=400, detail="One or more students not found or invalid role")

    homework = Homework(
        course_id=hw_in.course_id,
        teacher_id=current_user.id,
        title=hw_in.title,
        description=hw_in.description,
    )
    db.add(homework)
    db.flush()

    for student_id in hw_in.student_ids:
        assignment = HomeworkAssignment(
            homework_id=homework.id,
            student_id=student_id,
            status=HomeworkStatus.pending.value,
        )
        db.add(assignment)

    db.commit()
    db.refresh(homework)
    return _attach_content(homework)


@router.get("", response_model=list[HomeworkResponse])
def get_homeworks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.teacher.value:
        homeworks = (
            db.query(Homework)
            .filter(or_(Homework.teacher_id == current_user.id, Homework.is_demo.is_(True)))
            .order_by(Homework.id.desc())
            .all()
        )
        return [_attach_content(hw) for hw in homeworks]
    assignments = (
        db.query(HomeworkAssignment).filter(HomeworkAssignment.student_id == current_user.id).all()
    )
    homeworks = [a.homework for a in assignments]
    return [_attach_content(hw, for_student=True) for hw in homeworks]


@router.get("/journal/summary", response_model=JournalSummaryResponse)
def journal_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can view journal summary")
    return build_journal_summary(db, current_user.id)


@router.get("/reminders", response_model=HomeworkRemindersResponse)
def homework_reminders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return build_reminders(db, current_user)


@router.get("/{homework_id}", response_model=HomeworkResponse)
def get_homework(homework_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    homework = db.query(Homework).filter(Homework.id == homework_id).first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")

    if current_user.role == UserRole.student.value:
        assignment = next((a for a in homework.assignments if a.student_id == current_user.id), None)
        if not assignment:
            raise HTTPException(status_code=403, detail="Not assigned to you")
        return _attach_content(homework, for_student=True)
    if current_user.role == UserRole.teacher.value:
        if not _can_teacher_access_homework(current_user, homework):
            raise HTTPException(status_code=403, detail="Not your homework")

    return _attach_content(homework)


def _validate_and_dump_quiz(
    homework: Homework, submission: HomeworkSubmit
) -> str | None:
    if not homework.content_json:
        if submission.student_quiz:
            return json.dumps(submission.student_quiz, ensure_ascii=False)
        return None
    content = HomeworkTemplateContent(**parse_content(homework.content_json))
    items = content.quiz_items
    if not items:
        return (
            json.dumps(submission.student_quiz, ensure_ascii=False)
            if submission.student_quiz
            else None
        )
    sq = submission.student_quiz or {}
    for i, q in enumerate(items):
        if not q.options:
            continue
        key = str(i)
        if key not in sq:
            raise HTTPException(status_code=400, detail=f"Не выбран ответ на вопрос {i + 1}")
        try:
            picked = int(sq[key])
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail="Некорректные ответы теста") from e
        n_opts = len(q.options)
        if not (0 <= picked < n_opts):
            raise HTTPException(status_code=400, detail=f"Некорректный вариант в вопросе {i + 1}")
    filtered: dict[str, int] = {}
    for i, q in enumerate(items):
        if not q.options:
            continue
        key = str(i)
        if key in sq:
            filtered[key] = int(sq[key])
    return json.dumps(filtered, ensure_ascii=False)


@router.put("/assignments/{assignment_id}/submit", response_model=HomeworkAssignmentResponse)
def submit_homework(
    assignment_id: int,
    submission: HomeworkSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.student.value:
        raise HTTPException(status_code=403, detail="Only students can submit homework")

    assignment = db.query(HomeworkAssignment).filter(HomeworkAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your assignment")

    assignment.student_code = submission.student_code
    assignment.student_text = submission.student_text
    assignment.student_quiz_json = _validate_and_dump_quiz(assignment.homework, submission)
    assignment.status = HomeworkStatus.submitted.value

    db.add(Notification(
        user_id=assignment.homework.teacher_id,
        title="Сдано задание",
        message=f"Студент {current_user.username} сдал ДЗ «{assignment.homework.title}».",
        link=f"/homeworks/{assignment.homework_id}?student={current_user.id}"
    ))

    db.commit()
    db.refresh(assignment)
    assignment.student_name = assignment.student.username
    return assignment


@router.post("/assignments/{assignment_id}/hint", response_model=HomeworkHintResponse)
def homework_hint(
    assignment_id: int,
    body: HomeworkHintRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.student.value:
        raise HTTPException(status_code=403, detail="Only students can request hints")

    assignment = db.query(HomeworkAssignment).filter(HomeworkAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your assignment")
    if assignment.status != HomeworkStatus.pending.value:
        raise HTTPException(status_code=400, detail="Подсказки доступны только до сдачи работы")

    hint_count = assignment.hint_count or 0
    if hint_count >= settings.HOMEWORK_HINT_MAX:
        raise HTTPException(
            status_code=429,
            detail=f"Лимит подсказок ({settings.HOMEWORK_HINT_MAX}) исчерпан для этого задания",
        )
    if assignment.last_hint_at:
        try:
            last_hint = datetime.fromisoformat(assignment.last_hint_at)
            elapsed = (datetime.utcnow() - last_hint).total_seconds()
            if elapsed < settings.HOMEWORK_HINT_COOLDOWN_SEC:
                wait = int(settings.HOMEWORK_HINT_COOLDOWN_SEC - elapsed)
                raise HTTPException(
                    status_code=429,
                    detail=f"Подождите {wait} сек. перед следующей подсказкой",
                )
        except ValueError:
            pass

    t0 = time.perf_counter()
    try:
        hint = generate_homework_hint(
            assignment.homework,
            assignment,
            draft_code=body.student_code if body else None,
            draft_text=body.student_text if body else None,
            draft_quiz=body.student_quiz if body else None,
        )
        record_metric(
            db,
            event_type="homework_hint",
            user_id=current_user.id,
            course_id=assignment.homework.course_id,
            duration_ms=(time.perf_counter() - t0) * 1000,
            success=True,
        )
    except Exception as e:
        record_metric(
            db,
            event_type="homework_hint",
            user_id=current_user.id,
            course_id=assignment.homework.course_id,
            duration_ms=(time.perf_counter() - t0) * 1000,
            success=False,
            meta={"error": str(e)[:200]},
        )
        raise HTTPException(
            status_code=503,
            detail=f"ИИ недоступен: {e}. Убедитесь, что Ollama запущена.",
        ) from e

    assignment.hint_count = hint_count + 1
    assignment.last_hint_at = datetime.utcnow().isoformat()
    db.commit()
    return HomeworkHintResponse(hint=hint)


@router.put("/assignments/{assignment_id}/grade", response_model=HomeworkAssignmentResponse)
def grade_homework(
    assignment_id: int,
    grading: HomeworkGrade,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can grade homework")

    assignment = db.query(HomeworkAssignment).filter(HomeworkAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if not _can_teacher_access_homework(current_user, assignment.homework):
        raise HTTPException(status_code=403, detail="Not your assignment to grade")

    assignment.teacher_feedback = grading.teacher_feedback
    assignment.grade = grading.grade
    assignment.status = HomeworkStatus.graded.value

    db.add(Notification(
        user_id=assignment.student_id,
        title="Оценка за ДЗ",
        message=f"Преподаватель выставил оценку {grading.grade} за ДЗ «{assignment.homework.title}».",
        link=f"/homeworks/{assignment.homework_id}"
    ))

    db.commit()
    db.refresh(assignment)
    assignment.student_name = assignment.student.username
    return assignment


@router.post("/assignments/{assignment_id}/ai-review", response_model=HomeworkAiReviewResponse)
def ai_review_homework(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can request AI review")

    assignment = db.query(HomeworkAssignment).filter(HomeworkAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if not _can_teacher_access_homework(current_user, assignment.homework):
        raise HTTPException(status_code=403, detail="Not your assignment")
    if assignment.status not in (HomeworkStatus.submitted.value, HomeworkStatus.graded.value):
        raise HTTPException(status_code=400, detail="Nothing submitted yet")

    if assignment.ai_review_json and assignment.status == HomeworkStatus.submitted.value:
        return HomeworkAiReviewResponse(**json.loads(assignment.ai_review_json))

    if _count_recent_ai_reviews(db, current_user.id) >= settings.HOMEWORK_AI_REVIEW_MAX_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail=f"Лимит ИИ-проверок ({settings.HOMEWORK_AI_REVIEW_MAX_PER_HOUR} в час) исчерпан",
        )

    t0 = time.perf_counter()
    try:
        result = request_homework_review(assignment.homework, assignment)
        record_metric(
            db,
            event_type="ai_homework_review",
            user_id=current_user.id,
            course_id=assignment.homework.course_id,
            duration_ms=(time.perf_counter() - t0) * 1000,
            success=True,
        )
    except Exception as e:
        record_metric(
            db,
            event_type="ai_homework_review",
            user_id=current_user.id,
            course_id=assignment.homework.course_id,
            duration_ms=(time.perf_counter() - t0) * 1000,
            success=False,
            meta={"error": str(e)[:200]},
        )
        raise HTTPException(
            status_code=503,
            detail=f"ИИ-сервис недоступен: {e}",
        ) from e

    assignment.ai_review_json = json.dumps(result, ensure_ascii=False)
    db.add(Notification(
        user_id=current_user.id,
        title="ИИ-проверка завершена",
        message=f"Проверка ответа студента {assignment.student.username} по ДЗ «{assignment.homework.title}» завершена.",
        link=f"/homeworks/{assignment.homework_id}?student={assignment.student_id}"
    ))
    db.commit()

    return HomeworkAiReviewResponse(**result)


def mass_review_task(assignment_ids: list[int], teacher_id: int):
    # Process assignments one by one
    db = SessionLocal()
    try:
        for assignment_id in assignment_ids:
            assignment = db.query(HomeworkAssignment).filter(HomeworkAssignment.id == assignment_id).first()
            if not assignment or assignment.status not in (HomeworkStatus.submitted.value, HomeworkStatus.graded.value) or assignment.ai_review_json:
                continue

            t0 = time.perf_counter()
            try:
                result = request_homework_review(assignment.homework, assignment)
                record_metric(
                    db,
                    event_type="ai_homework_review",
                    user_id=teacher_id,
                    course_id=assignment.homework.course_id,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    success=True,
                )
                assignment.ai_review_json = json.dumps(result, ensure_ascii=False)
                student_name = assignment.student.full_name or assignment.student.username
                db.add(Notification(
                    user_id=teacher_id,
                    title="ИИ-проверка завершена",
                    message=f"Проверена работа студента {student_name} по заданию «{assignment.homework.title}».",
                    link=f"/homeworks/{assignment.homework_id}?student={assignment.student_id}",
                ))
                db.commit()
            except Exception as e:
                db.rollback()
                record_metric(
                    db,
                    event_type="ai_homework_review",
                    user_id=teacher_id,
                    course_id=assignment.homework.course_id,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    success=False,
                    meta={"error": str(e)[:200]},
                )
    finally:
        db.close()

@router.post("/assignments/review-all")
def review_all_homeworks(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can request mass AI review")

    teacher_homeworks = db.query(Homework).filter(
        or_(Homework.teacher_id == current_user.id, getattr(Homework, "is_demo", False) == True)
    ).all()
    if not teacher_homeworks:
        return {"started": 0}
        
    hw_ids = [hw.id for hw in teacher_homeworks]

    assignments = db.query(HomeworkAssignment).filter(
        HomeworkAssignment.homework_id.in_(hw_ids),
        HomeworkAssignment.status == HomeworkStatus.submitted.value,
        HomeworkAssignment.ai_review_json.is_(None)
    ).all()

    if not assignments:
        return {"started": 0}

    assignment_ids = [a.id for a in assignments]
    background_tasks.add_task(mass_review_task, assignment_ids, current_user.id)
    return {"started": len(assignment_ids)}
