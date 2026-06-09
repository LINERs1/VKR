"""Проверка service-to-service токена от образовательной платформы."""

import logging

from fastapi import Header, HTTPException

from app.config import settings

logger = logging.getLogger(__name__)


def verify_service_token(
    x_service_token: str | None = Header(None, alias="X-Service-Token"),
    authorization: str | None = Header(None),
) -> None:
    expected = settings.SERVICE_API_KEY
    if not expected:
        logger.warning("SERVICE_API_KEY не задан — сервисные эндпоинты без защиты")
        return

    token = x_service_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing service token")
