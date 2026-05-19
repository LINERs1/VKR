import json
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.homework import Homework, HomeworkAssignment, HomeworkStatus
from app.models.user import User, UserRole
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
from app.services.auth_service import get_current_user
from app.services.homework_hint_service import generate_homework_hint
from app.services.homework_journal_service import build_journal_summary, build_reminders
from app.services.homework_review_service import review_assignment
from app.services.homework_template_service import parse_content
from app.services.weak_topics_service import record_quiz_weak_topics
from app.services.metrics_service import record_metric

router = APIRouter()


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
    resp = HomeworkResponse.model_validate(hw)
    if hw.content_json:
        parsed = HomeworkTemplateContent(**parse_content(hw.content_json))
        resp.content = _sanitize_content_for_student(parsed) if for_student else parsed
    for a in hw.assignments:
        a.student_name = a.student.username
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

    record_quiz_weak_topics(
        db,
        student_id=current_user.id,
        course_id=assignment.homework.course_id,
        content_json=assignment.homework.content_json,
        student_quiz_json=assignment.student_quiz_json,
    )

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

    t0 = time.perf_counter()
    try:
        result = review_assignment(assignment.homework, assignment)
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
            detail=f"ИИ недоступен: {e}. Убедитесь, что Ollama запущена.",
        ) from e

    return HomeworkAiReviewResponse(**result)
