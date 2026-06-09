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
