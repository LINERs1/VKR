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
    from app.models.navigation import NavNode, NavEdge
    from app.models.mirror import CourseRef, LessonRef
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from app.services.rag_service import get_vector_store
    from app.api.webhooks import _create_nav_node, _link_nodes

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    added_courses_count = 0
    added_chunks_count = 0

    # Предзагрузим действия (actions) для связей уроков
    action_hw = db.query(NavNode).filter(NavNode.identifier == "ACTION:CHECK_HW").first()
    action_hint = db.query(NavNode).filter(NavNode.identifier == "ACTION:GET_HINT").first()

    for course in platform_courses:
        course_id = str(course.get("id"))
        if course_id not in missing_ids:
            continue
            
        logger.info(f"Начинаю автоматическую загрузку курса: {course.get('title')}")
        
        # 0. Идемпотентное создание зеркала курса (CourseRef)
        course_ref = db.query(CourseRef).filter(CourseRef.id == course_id).first()
        if not course_ref:
            course_ref = CourseRef(id=course_id, title=course.get("title") or f"Курс {course_id}")
            db.add(course_ref)
        else:
            course_ref.title = course.get("title") or f"Курс {course_id}"

        # 1. Добавляем узел навигации для Курса с помощью хелпера
        nav_path = f"/courses/{course_id}"
        course_nav = _create_nav_node(
            db=db,
            identifier=nav_path,
            title=course.get("title") or f"Курс {course_id}",
            depth=2,
            node_type="page"
        )

        # Создаем связи от Главной страницы к новому курсу
        home_node = db.query(NavNode).filter(NavNode.identifier == "/").first()
        if home_node:
            _link_nodes(db, home_node.id, course_nav.id)
            _link_nodes(db, course_nav.id, home_node.id)

        # 2. Обрабатываем уроки
        lessons = course.get("lessons") or []
        docs = []
        for idx, lesson in enumerate(lessons, start=1):
            lesson_id = int(lesson.get("id"))  # Кастуем к int
            lesson_title = lesson.get("title") or ""
            
            # 2.1 Идемпотентное создание зеркала урока (LessonRef)
            lesson_ref = db.query(LessonRef).filter(LessonRef.id == lesson_id).first()
            if not lesson_ref:
                lesson_ref = LessonRef(id=lesson_id, course_id=course_id, title=lesson_title)
                db.add(lesson_ref)
            else:
                lesson_ref.title = lesson_title

            # 2.2 Создание узла навигации для Урока с помощью хелпера
            lesson_nav_path = f"/courses/{course_id}?lesson={lesson_id}"
            lesson_nav = _create_nav_node(
                db=db,
                identifier=lesson_nav_path,
                title=f"Урок {idx}: {lesson_title}",
                depth=3,
                node_type="page"
            )

            # Связь от курса к уроку — обычная навигация
            _link_nodes(db, course_nav.id, lesson_nav.id)

            # Связи от урока к действиям (can_execute).
            # _link_nodes здесь не подходит: он жёстко ставит "navigates_to",
            # а для action-узлов нужно "can_execute". Прокладываем вручную с
            # идемпотентной проверкой (фильтруем именно по can_execute, чтобы
            # не словить левое navigates_to ребро, если оно когда-то создалось).
            for action_node in (action_hw, action_hint):
                if action_node is None:
                    continue
                exists = db.query(NavEdge).filter(
                    NavEdge.source_node_id == lesson_nav.id,
                    NavEdge.target_node_id == action_node.id,
                    NavEdge.relationship_type == "can_execute",
                ).first()
                if not exists:
                    db.add(NavEdge(
                        source_node_id=lesson_nav.id,
                        target_node_id=action_node.id,
                        relationship_type="can_execute",
                    ))

            # 2.3 Собираем тексты для ChromaDB
            content = lesson.get("content")
            if content:
                doc = Document(
                    page_content=content,
                    metadata={
                        "source": "lesson",
                        "course_id": course_id,
                        "lesson_id": str(lesson_id),
                        "title": lesson_title
                    }
                )
                docs.append(doc)

        db.commit()

        if docs:
            chunks = text_splitter.split_documents(docs)
            store = get_vector_store(course_id)
            store.add_documents(chunks)
            added_chunks_count += len(chunks)
            
        added_courses_count += 1

    if added_courses_count > 0:
        logger.info(f"✅ Авто-загрузка завершена: добавлено курсов: {added_courses_count}, чанков текста: {added_chunks_count}")
