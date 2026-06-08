"""Мастерская: шаблоны ДЗ (хранилище) и назначение ученикам."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.homework import Homework, HomeworkAssignment, HomeworkStatus
from app.models.homework_template import HomeworkTemplate
from app.models.user import User, UserRole
from app.api.homework import _attach_content
from app.schemas.homework import HomeworkResponse
from app.schemas.homework_template import (
    HomeworkTemplateAssign,
    HomeworkTemplateCreate,
    HomeworkTemplateListItem,
    HomeworkTemplateResponse,
    HomeworkTemplateUpdate,
)
from app.services.auth_service import get_current_user
from app.services.homework_template_service import (
    build_student_description,
    dump_content,
    parse_content,
)

router = APIRouter()


def _require_teacher(user: User) -> None:
    if user.role != UserRole.teacher.value:
        raise HTTPException(status_code=403, detail="Only teachers can use the workshop")


def _template_to_response(t: HomeworkTemplate) -> HomeworkTemplateResponse:
    from app.schemas.homework_template import HomeworkTemplateContent

    content = HomeworkTemplateContent(**parse_content(t.content_json))
    return HomeworkTemplateResponse(
        id=t.id,
        teacher_id=t.teacher_id,
        course_id=t.course_id,
        title=t.title,
        content=content,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _get_owned_template(template_id: int, teacher_id: int, db: Session) -> HomeworkTemplate:
    t = db.query(HomeworkTemplate).filter(HomeworkTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    if t.teacher_id != teacher_id:
        raise HTTPException(status_code=403, detail="Not your template")
    return t


@router.get("/templates", response_model=list[HomeworkTemplateListItem])
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_teacher(current_user)
    rows = (
        db.query(HomeworkTemplate)
        .filter(HomeworkTemplate.teacher_id == current_user.id)
        .order_by(HomeworkTemplate.updated_at.desc())
        .all()
    )
    return rows


@router.post("/templates", response_model=HomeworkTemplateResponse)
def create_template(
    body: HomeworkTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_teacher(current_user)
    t = HomeworkTemplate(
        teacher_id=current_user.id,
        course_id=body.course_id,
        title=body.title,
        content_json=dump_content(body.content.model_dump()),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _template_to_response(t)


@router.get("/templates/{template_id}", response_model=HomeworkTemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_teacher(current_user)
    t = _get_owned_template(template_id, current_user.id, db)
    return _template_to_response(t)


@router.put("/templates/{template_id}", response_model=HomeworkTemplateResponse)
def update_template(
    template_id: int,
    body: HomeworkTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_teacher(current_user)
    t = _get_owned_template(template_id, current_user.id, db)
    if body.course_id is not None:
        t.course_id = body.course_id
    if body.title is not None:
        t.title = body.title
    if body.content is not None:
        t.content_json = dump_content(body.content.model_dump())
    db.commit()
    db.refresh(t)
    return _template_to_response(t)


@router.delete("/templates/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_teacher(current_user)
    t = _get_owned_template(template_id, current_user.id, db)
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/templates/{template_id}/assign", response_model=HomeworkResponse)
def assign_template(
    template_id: int,
    body: HomeworkTemplateAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_teacher(current_user)
    if not body.student_ids:
        raise HTTPException(status_code=400, detail="Select at least one student")

    t = _get_owned_template(template_id, current_user.id, db)
    students = db.query(User).filter(
        User.id.in_(body.student_ids),
        User.role == UserRole.student.value,
    ).all()
    if len(students) != len(body.student_ids):
        raise HTTPException(status_code=400, detail="Invalid student ids")

    content = parse_content(t.content_json)
    description = build_student_description(content)
    content_json = dump_content(content)

    homework = Homework(
        course_id=t.course_id,
        teacher_id=current_user.id,
        title=t.title,
        description=description,
        content_json=content_json,
    )
    db.add(homework)
    db.flush()

    for sid in body.student_ids:
        db.add(
            HomeworkAssignment(
                homework_id=homework.id,
                student_id=sid,
                status=HomeworkStatus.pending.value,
            )
        )

    db.commit()
    db.refresh(homework)
    return _attach_content(homework)
