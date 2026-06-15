"""Сверка графа навигации ИИ с курсами на платформе при старте."""
from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.services.platform_client import fetch_platform_courses_sync

logger = logging.getLogger(__name__)

_COURSE_NODE_RE = re.compile(r"^/courses/([^/?#]+)$")


def check_course_sync(db: Session) -> dict:
    """
    Сравнивает NavNode (/courses/{id}) с GET /api/courses платформы.
    Логирует расхождения — типичная причина «ИИ знает курс, платформа — нет».
    """
    from app.models.navigation import NavNode

    platform_courses = fetch_platform_courses_sync()
    platform_ids = {str(c.get("id")) for c in platform_courses if c.get("id")}

    nav_nodes = db.query(NavNode).filter(
        NavNode.identifier.like("/courses/%"),
        ~NavNode.identifier.like("/courses/%?%"),
    ).all()
    nav_ids = set()
    for node in nav_nodes:
        m = _COURSE_NODE_RE.match(node.identifier or "")
        if m:
            nav_ids.add(m.group(1))

    only_nav = sorted(nav_ids - platform_ids)
    only_platform = sorted(platform_ids - nav_ids)

    if only_nav:
        logger.warning(
            "⚠️ Nav sync: в графе ИИ есть курсы, которых нет на платформе: %s",
            ", ".join(only_nav),
        )
    if only_platform:
        logger.warning(
            "⚠️ Nav sync: на платформе есть курсы без NavNode в ИИ (нужен webhook): %s",
            ", ".join(only_platform),
        )
        auto_pull_missing_courses(db, platform_courses, only_platform)
    if not only_nav and not only_platform and platform_ids:
        logger.info("✅ Nav sync: %d курсов совпадают между ИИ и платформой", len(platform_ids))
    elif not platform_ids:
        logger.warning("⚠️ Nav sync: платформа недоступна или курсов нет — проверка пропущена")

    return {
        "platform_count": len(platform_ids),
        "nav_count": len(nav_ids),
        "only_in_ai_nav": only_nav,
        "only_on_platform": only_platform,
        "in_sync": not only_nav and not only_platform,
    }


def auto_pull_missing_courses(db: Session, platform_courses: list[dict], missing_ids: list[str]):
    """Автоматически вытягивает тексты недостающих курсов и сохраняет их в ИИ-сервис."""
    from app.models.navigation import NavNode
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from app.services.rag_service import get_vector_store

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    added_courses_count = 0
    added_chunks_count = 0

    for course in platform_courses:
        course_id = str(course.get("id"))
        if course_id not in missing_ids:
            continue
            
        logger.info(f"Начинаю автоматическую загрузку курса: {course.get('title')}")
        
        # 1. Добавляем узел навигации в SQL базу ИИ-сервиса (чтобы ИИ знал этот путь)
        nav_path = f"/courses/{course_id}"
        existing_nav = db.query(NavNode).filter(NavNode.identifier == nav_path).first()
        if not existing_nav:
            new_nav = NavNode(
                identifier=nav_path,
                title=course.get("title") or f"Курс {course_id}",
                description=course.get("description") or "",
                node_type="course",
            )
            db.add(new_nav)
            db.flush() # Получаем ID для нового узла

            # Создаем связь (ребро) от Главной страницы к новому курсу
            home_node = db.query(NavNode).filter(NavNode.identifier == "/").first()
            if home_node:
                from app.models.navigation import NavEdge
                db.add(NavEdge(source_node_id=home_node.id, target_node_id=new_nav.id))
                db.add(NavEdge(source_node_id=new_nav.id, target_node_id=home_node.id))

            db.commit()

        # 2. Обрабатываем уроки и добавляем тексты в векторную базу (ChromaDB)
        lessons = course.get("lessons") or []
        docs = []
        for lesson in lessons:
            content = lesson.get("content")
            if not content:
                continue
                
            # Создаем документ для векторной БД
            doc = Document(
                page_content=content,
                metadata={
                    "source": "lesson",
                    "course_id": course_id,
                    "lesson_id": str(lesson.get("id")),
                    "title": lesson.get("title") or ""
                }
            )
            docs.append(doc)

        if docs:
            # Нарезаем уроки на чанки
            chunks = text_splitter.split_documents(docs)
            # Сохраняем в векторное хранилище конкретного курса
            store = get_vector_store(course_id)
            store.add_documents(chunks)
            added_chunks_count += len(chunks)
            
        added_courses_count += 1

    if added_courses_count > 0:
        logger.info(f"✅ Авто-загрузка завершена: добавлено курсов: {added_courses_count}, чанков текста: {added_chunks_count}")
