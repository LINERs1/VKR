"""HTTP-клиент для вызовов ИИ-сервиса с service token."""

import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)


def _service_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.SERVICE_API_KEY:
        headers["X-Service-Token"] = settings.SERVICE_API_KEY
    return headers


def ai_post(path: str, payload: dict, *, timeout: float = 30) -> dict:
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}{path}"
    resp = requests.post(url, json=payload, headers=_service_headers(), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def ai_delete(path: str, *, timeout: float = 10) -> None:
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}{path}"
    resp = requests.delete(url, headers=_service_headers(), timeout=timeout)
    resp.raise_for_status()


def send_webhook(path: str, payload: dict, *, timeout: float = 10) -> None:
    try:
        ai_post(path, payload, timeout=timeout)
    except Exception as e:
        logger.error("AI webhook %s failed: %s", path, e)
