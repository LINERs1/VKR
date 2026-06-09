"""HTTP-клиент к образовательной платформе (любой LMS с REST API)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def fetch_platform_courses(timeout: float = 8.0) -> list[dict[str, Any]]:
    """GET /api/courses с платформы. Пустой список при недоступности."""
    url = f"{settings.PLATFORM_SERVICE_URL.rstrip('/')}/api/courses"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            logger.warning("Platform courses %s: HTTP %s", url, resp.status_code)
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("Platform courses unavailable (%s): %s", url, e)
        return []


def fetch_platform_courses_sync(timeout: float = 8.0) -> list[dict[str, Any]]:
    url = f"{settings.PLATFORM_SERVICE_URL.rstrip('/')}/api/courses"
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning("Platform courses sync failed: %s", e)
        return []
