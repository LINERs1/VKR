"""
REST API навигации для embeddable-виджета.

Платформа передаёт свой список курсов — ИИ не привязан к конкретной LMS.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db

from app.services.highlight_service import validate_highlight
from app.services.audit_service import record_audit
from app.services.navigation_service import (
    CourseNavItem,
    build_breadcrumbs_text,
    resolve_adjacent_lesson,
    resolve_path_or_query,
    validate_navigate_path,
)
from app.services.platform_client import fetch_platform_courses

router = APIRouter()


class CourseInput(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    lessons: list[dict[str, Any]] = Field(default_factory=list)


class BreadcrumbInput(BaseModel):
    label: str
    path: str = ""


class ResolveRequest(BaseModel):
    path_or_query: str
    courses: Optional[list[CourseInput]] = None
    fetch_from_platform: bool = False


class AdjacentLessonRequest(BaseModel):
    course_id: str
    current_lesson_index: int = Field(ge=1, description="Порядковый номер урока (1-based)")
    delta: int = Field(description="+1 следующий, -1 предыдущий")
    courses: Optional[list[CourseInput]] = None
    fetch_from_platform: bool = False


async def _courses_from_request(
    courses: list[CourseInput] | None,
    fetch_from_platform: bool,
) -> list[CourseNavItem]:
    raw: list[dict[str, Any]] = []
    if courses:
        raw = [c.model_dump() for c in courses]
    elif fetch_from_platform:
        raw = await fetch_platform_courses()
    return [CourseNavItem.from_dict(c) for c in raw if c.get("id")]


def _resolve_response(res) -> dict[str, Any]:
    return {
        "status": res.status,
        "path": res.path,
        "course_id": res.course_id,
        "query": res.query,
        "matches": res.matches,
        "message": res.message,
    }


@router.post("/resolve")
async def resolve_navigation(req: ResolveRequest):
    """
    Резолвит путь или фразу («python за 100 дней») в маршрут платформы.
    status: ok | ambiguous | not_found | static
    """
    items = await _courses_from_request(req.courses, req.fetch_from_platform)
    res = resolve_path_or_query(req.path_or_query, items)
    return _resolve_response(res)


@router.post("/validate")
async def validate_navigation(req: ResolveRequest):
    """Проверка [NAVIGATE:...] из текстового чата перед action на виджете."""
    items = await _courses_from_request(req.courses, req.fetch_from_platform)
    res = validate_navigate_path(req.path_or_query, items)
    out = _resolve_response(res)
    if res.status == "ambiguous":
        out["action"] = "show_courses"
        out["query"] = req.path_or_query
    return out


@router.post("/adjacent-lesson")
async def adjacent_lesson(req: AdjacentLessonRequest):
    """Следующий / предыдущий урок в курсе."""
    items = await _courses_from_request(req.courses, req.fetch_from_platform)
    res = resolve_adjacent_lesson(
        req.course_id,
        req.current_lesson_index,
        req.delta,
        items,
    )
    out = _resolve_response(res)
    if res.status == "ok" and res.matches:
        m = res.matches[0]
        out["lesson_index"] = m.get("lesson_index")
        out["lesson_title"] = m.get("lesson_title")
    return out


@router.get("/sync-status")
async def navigation_sync_status():
    """Быстрая проверка доступности платформы и числа курсов."""
    courses = await fetch_platform_courses()
    return {
        "platform_reachable": bool(courses),
        "platform_course_count": len(courses),
        "course_ids": [c.get("id") for c in courses if c.get("id")],
    }


class ValidateHighlightRequest(BaseModel):
    highlight_text: str
    page_content: str = ""


@router.post("/validate-highlight")
async def validate_highlight_text(req: ValidateHighlightRequest, db: Session = Depends(get_db)):
    """Санитизация highlight_text и проверка наличия фрагмента в контенте страницы."""
    result = validate_highlight(req.highlight_text, req.page_content)
    record_audit(
        db,
        action="highlight_validate",
        resource=req.highlight_text[:80] if req.highlight_text else None,
        success=result["valid"],
        meta={"message": result.get("message"), "sanitized": result.get("sanitized")},
    )
    return result


@router.post("/breadcrumbs/format")
async def format_breadcrumbs(breadcrumbs: list[BreadcrumbInput]):
    """Форматирует хлебные крошки для промпта (отладка / виджет)."""
    text = build_breadcrumbs_text([b.model_dump() for b in breadcrumbs])
    return {"text": text}
