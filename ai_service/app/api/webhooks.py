"""
Webhook-приёмники — принимают уведомления от образовательной платформы.

Платформа сама присылает POST/DELETE запросы сюда при:
- создании/обновлении/удалении курсов и уроков
- добавлении методических указаний и справочников

ИИ-сервис в ответ:
1. Обновляет зеркальные таблицы (CourseRef, LessonRef)
2. Создаёт/удаляет узлы графа навигации (NavNode, NavEdge)
3. Индексирует/удаляет контент в ChromaDB
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mirror import CourseRef, LessonRef
from app.models.navigation import NavNode, NavEdge, NodeAccessRule

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Pydantic схемы входящих вебхуков ───────────────────────────────────────

class CourseWebhook(BaseModel):
    id: str
    title: str

class LessonWebhook(BaseModel):
    id: int
    course_id: str
    title: str
    content: Optional[str] = None   # Текст урока для ChromaDB

class ContentWebhook(BaseModel):
    """Для методических указаний и справочников."""
    id: str
    course_id: str
    title: str
    content: str
    source_type: str  # "methodology" или "reference"


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def _create_nav_node(db: Session, identifier: str, title: str, depth: int, node_type: str = "page") -> NavNode:
    """Создаёт NavNode если не существует."""
    node = db.query(NavNode).filter(NavNode.identifier == identifier).first()
    if not node:
        node = NavNode(
            identifier=identifier,
            title=title,
            node_type=node_type,
            depth=depth,
        )
        db.add(node)
        db.flush()

        # Правило доступа — для всех ролей
        for role in ["student", "teacher"]:
            rule = NodeAccessRule(nav_node_id=node.id, allowed_role=role)
            db.add(rule)

    return node


def _link_nodes(db: Session, source_id: int, target_id: int):
    """Создаёт ребро навигации если не существует."""
    edge = db.query(NavEdge).filter(
        NavEdge.source_node_id == source_id,
        NavEdge.target_node_id == target_id,
    ).first()
    if not edge:
        edge = NavEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            relationship_type="navigates_to",
            weight=1,
        )
        db.add(edge)


def _ingest_to_chroma(content: str, doc_id: str, course_id: str, source_type: str):
    """Индексирует текст в ChromaDB."""
    try:
        from app.services.rag_service import ingest_text
        ingest_text(
            text=content,
            source_name=doc_id,
            course_id=course_id,
            extra_metadata={"source_type": source_type},
        )
    except Exception as e:
        logger.warning(f"ChromaDB ingest failed for {doc_id}: {e}")


def _delete_from_chroma(doc_id: str, course_id: str):
    """Удаляет документ из ChromaDB."""
    try:
        from app.services.rag_service import delete_document
        delete_document(source_name=doc_id, course_id=course_id)
    except Exception as e:
        logger.warning(f"ChromaDB delete failed for {doc_id}: {e}")


# ─── Курсы ───────────────────────────────────────────────────────────────────

@router.post("/course")
def webhook_course_created(data: CourseWebhook, db: Session = Depends(get_db)):
    """Платформа создала/обновила курс."""
    # 1. Обновить зеркало
    ref = db.query(CourseRef).filter(CourseRef.id == data.id).first()
    if not ref:
        ref = CourseRef(id=data.id, title=data.title)
        db.add(ref)
    else:
        ref.title = data.title

    # 2. Создать NavNode для страницы курса
    identifier = f"/courses/{data.id}"
    node = _create_nav_node(db, identifier, f"Курс: {data.title}", depth=2)

    # 3. Связать с Главной страницей (depth=1, identifier="/")
    home = db.query(NavNode).filter(NavNode.identifier == "/").first()
    if home:
        _link_nodes(db, home.id, node.id)

    db.commit()
    logger.info(f"✅ Webhook course_created: {data.id} → NavNode {identifier}")
    return {"status": "ok", "nav_node": identifier}


@router.delete("/course/{course_id}")
def webhook_course_deleted(course_id: str, db: Session = Depends(get_db)):
    """Платформа удалила курс."""
    # Удалить зеркало (каскадно удалит LessonRef)
    ref = db.query(CourseRef).filter(CourseRef.id == course_id).first()
    if ref:
        db.delete(ref)

    # Удалить все NavNode этого курса (они сами каскадно удалят NavEdge)
    nodes = db.query(NavNode).filter(
        NavNode.identifier.like(f"/courses/{course_id}%")
    ).all()
    for node in nodes:
        _delete_from_chroma(f"lesson_{course_id}_{node.identifier.split('lesson=')[-1]}", course_id)
        db.delete(node)

    db.commit()
    logger.info(f"🗑️ Webhook course_deleted: {course_id}")
    return {"status": "ok", "deleted_course": course_id}


# ─── Уроки ───────────────────────────────────────────────────────────────────

@router.post("/lesson")
def webhook_lesson_created(data: LessonWebhook, db: Session = Depends(get_db)):
    """Платформа создала/обновила урок."""
    # 1. Обновить зеркало
    ref = db.query(LessonRef).filter(LessonRef.id == data.id).first()
    if not ref:
        ref = LessonRef(id=data.id, course_id=data.course_id, title=data.title)
        db.add(ref)
    else:
        ref.title = data.title

    # 2. Посчитать порядковый номер урока в курсе
    lesson_count = db.query(LessonRef).filter(
        LessonRef.course_id == data.course_id,
        LessonRef.id <= data.id,
    ).count()

    # 3. Создать NavNode для страницы урока
    identifier = f"/courses/{data.course_id}?lesson={data.id}"
    node = _create_nav_node(
        db,
        identifier,
        f"Урок {lesson_count}: {data.title}",
        depth=3,
    )

    # 4. Связать с NavNode курса
    course_node = db.query(NavNode).filter(
        NavNode.identifier == f"/courses/{data.course_id}"
    ).first()
    if course_node:
        _link_nodes(db, course_node.id, node.id)

    # 5. Индексировать контент в ChromaDB
    if data.content:
        _ingest_to_chroma(
            content=data.content,
            doc_id=f"lesson_{data.course_id}_{data.id}",
            course_id=data.course_id,
            source_type="lesson",
        )

    db.commit()
    logger.info(f"✅ Webhook lesson_created: {data.id} → NavNode {identifier}")
    return {"status": "ok", "nav_node": identifier}


@router.delete("/lesson/{lesson_id}")
def webhook_lesson_deleted(lesson_id: int, db: Session = Depends(get_db)):
    """Платформа удалила урок."""
    ref = db.query(LessonRef).filter(LessonRef.id == lesson_id).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Lesson not found in mirror")

    course_id = ref.course_id

    # Удалить NavNode (каскадно удалит NavEdge)
    identifier = f"/courses/{course_id}?lesson={lesson_id}"
    node = db.query(NavNode).filter(NavNode.identifier == identifier).first()
    if node:
        db.delete(node)

    # Удалить из ChromaDB
    _delete_from_chroma(f"lesson_{course_id}_{lesson_id}", course_id)

    db.delete(ref)
    db.commit()
    logger.info(f"🗑️ Webhook lesson_deleted: {lesson_id}")
    return {"status": "ok", "deleted_lesson": lesson_id}


# ─── Методические материалы и справочники ────────────────────────────────────

@router.post("/content")
def webhook_content_created(data: ContentWebhook, db: Session = Depends(get_db)):
    """
    Платформа создала/обновила методическое указание или справочник.
    Они не создают NavNode — только индексируются в ChromaDB для RAG-поиска.
    """
    if data.source_type not in ("methodology", "reference"):
        raise HTTPException(status_code=400, detail="source_type must be 'methodology' or 'reference'")

    doc_id = f"{data.source_type}_{data.course_id}_{data.id}"
    _ingest_to_chroma(
        content=data.content,
        doc_id=doc_id,
        course_id=data.course_id,
        source_type=data.source_type,
    )

    logger.info(f"✅ Webhook content_created: {doc_id} → ChromaDB")
    return {"status": "ok", "indexed": doc_id}


@router.delete("/content/{source_type}/{course_id}/{content_id}")
def webhook_content_deleted(source_type: str, course_id: str, content_id: str):
    """Платформа удалила методическое указание или справочник."""
    doc_id = f"{source_type}_{course_id}_{content_id}"
    _delete_from_chroma(doc_id, course_id)
    logger.info(f"Webhook content_deleted: {doc_id}")
    return {"status": "ok", "deleted": doc_id}
