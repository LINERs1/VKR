"""
REST API навигации для embeddable-виджета.

Платформа передаёт свой список курсов — ИИ не привязан к конкретной LMS.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.navigation import NavNode, NavEdge

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


class CustomNodeInput(BaseModel):
    identifier: str
    title: str
    description: Optional[str] = ""
    allowed_roles: list[str] = ["student", "teacher", "admin"]


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
async def resolve_navigation(req: ResolveRequest, db: Session = Depends(get_db)):
    """
    Резолвит путь или фразу («python за 100 дней») в маршрут платформы.
    status: ok | ambiguous | not_found | static
    """
    items = await _courses_from_request(req.courses, req.fetch_from_platform)
    custom_nodes = {n.identifier for n in db.query(NavNode).filter(NavNode.node_type == "page").all()}
    res = resolve_path_or_query(req.path_or_query, items, custom_paths=custom_nodes)
    return _resolve_response(res)


@router.post("/validate")
async def validate_navigation(req: ResolveRequest, db: Session = Depends(get_db)):
    """Проверка [NAVIGATE:...] из текстового чата перед action на виджете."""
    items = await _courses_from_request(req.courses, req.fetch_from_platform)
    custom_nodes = {n.identifier for n in db.query(NavNode).filter(NavNode.node_type == "page").all()}
    res = validate_navigate_path(req.path_or_query, items, custom_paths=custom_nodes)
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


@router.post("/breadcrumbs/format")
async def format_breadcrumbs(breadcrumbs: list[BreadcrumbInput]):
    """Форматирует хлебные крошки для промпта (отладка / виджет)."""
    text = build_breadcrumbs_text([b.model_dump() for b in breadcrumbs])
    return {"text": text}


@router.get("/custom-nodes")
def get_custom_nodes(response: Response, db: Session = Depends(get_db)):
    """Получает список кастомных статических страниц (node_type='page')."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    nodes = db.query(NavNode).filter(NavNode.node_type == "page").all()
    return [{
        "id": n.id,
        "identifier": n.identifier,
        "title": n.title,
        "description": n.description,
        "allowed_roles": [r.allowed_role for r in n.access_rules] if n.access_rules else ["student", "teacher", "admin"]
    } for n in nodes if not str(n.identifier).startswith("/courses/")]

@router.get("/dynamic-nodes")
def get_dynamic_nodes(response: Response, db: Session = Depends(get_db)):
    """Получает список динамических узлов графа (курсы, уроки, действия)."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    nodes = db.query(NavNode).all()
    return [{
        "id": n.id,
        "identifier": n.identifier,
        "title": n.title,
        "description": n.description,
        "type": "action" if n.node_type == "action" else ("lesson" if "?lesson=" in str(n.identifier) else "course")
    } for n in nodes if str(n.identifier).startswith("/courses/") or n.node_type == "action"]


@router.post("/custom-nodes")
def create_custom_node(node_in: CustomNodeInput, db: Session = Depends(get_db)):
    """Создает новый кастомный маршрут и привязывает его к Главной (/)."""
    existing = db.query(NavNode).filter(NavNode.identifier == node_in.identifier).first()
    if existing:
        raise HTTPException(status_code=400, detail="Маршрут с таким URL уже существует")

    new_node = NavNode(
        identifier=node_in.identifier,
        title=node_in.title,
        description=node_in.description,
        node_type="page"
    )
    db.add(new_node)
    db.flush()
    
    # Добавляем права доступа
    from app.models.navigation import NodeAccessRule
    for role in node_in.allowed_roles:
        db.add(NodeAccessRule(nav_node_id=new_node.id, allowed_role=role))
    db.flush()

    home_node = db.query(NavNode).filter(NavNode.identifier == "/").first()
    if home_node:
        db.add(NavEdge(source_node_id=home_node.id, target_node_id=new_node.id))
        db.add(NavEdge(source_node_id=new_node.id, target_node_id=home_node.id))

    db.commit()
    return {"status": "ok", "id": new_node.id}


@router.delete("/custom-nodes/{node_id}")
def delete_custom_node(node_id: int, db: Session = Depends(get_db)):
    """Удаляет маршрут по ID."""
    node = db.query(NavNode).filter(NavNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    if node.identifier == "/":
        raise HTTPException(status_code=400, detail="Нельзя удалить главную страницу")
        
    db.delete(node)
    db.commit()
    return {"status": "ok"}


@router.put("/custom-nodes/{node_id}")
def update_custom_node(node_id: int, node_in: CustomNodeInput, db: Session = Depends(get_db)):
    """Редактирует существующий кастомный маршрут."""
    node = db.query(NavNode).filter(NavNode.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Маршрут не найден")
    
    if node.identifier == "/" and node_in.identifier != "/":
        raise HTTPException(status_code=400, detail="Нельзя изменить URL главной страницы")

    # Проверка уникальности нового identifier, если он изменился
    if node.identifier != node_in.identifier:
        existing = db.query(NavNode).filter(NavNode.identifier == node_in.identifier).first()
        if existing:
            raise HTTPException(status_code=400, detail="Маршрут с таким URL уже существует")

    node.identifier = node_in.identifier
    node.title = node_in.title
    node.description = node_in.description
    
    from app.models.navigation import NodeAccessRule
    # Удаляем старые правила и создаем новые
    db.query(NodeAccessRule).filter(NodeAccessRule.nav_node_id == node.id).delete()
    for role in node_in.allowed_roles:
        db.add(NodeAccessRule(nav_node_id=node.id, allowed_role=role))

    db.commit()
    return {"status": "ok"}
