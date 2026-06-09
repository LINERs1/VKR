"""Embeddable API: контракт интеграции для внешних LMS."""

from fastapi import APIRouter

from app.schemas.embeddable import (
    ALL_PERMISSIONS,
    ROLE_DEFAULT_PERMISSIONS,
    CourseItem,
    HomeworkCheckRequest,
    HomeworkCheckResponse,
    NavigationResolveRequest,
    NavigationResolveResponse,
    VoiceCallRequest,
    VoiceCallResponse,
    VoiceContextUpdateRequest,
    WebhookCoursePayload,
    WebhookLessonPayload,
)

router = APIRouter()


@router.get("/contract")
async def embeddable_contract():
    """
    Машиночитаемое описание контракта интеграции.
    Платформа может использовать для генерации клиента или валидации.
    """
    return {
        "version": "1.0",
        "permissions": sorted(ALL_PERMISSIONS),
        "role_defaults": {k: sorted(v) for k, v in ROLE_DEFAULT_PERMISSIONS.items()},
        "endpoints": {
            "voice_call": {
                "method": "POST",
                "path": "/api/ultravox/call",
                "auth": "Bearer JWT",
                "request_schema": VoiceCallRequest.model_json_schema(),
                "response_schema": VoiceCallResponse.model_json_schema(),
            },
            "voice_context": {
                "method": "POST",
                "path": "/api/ultravox/context",
                "auth": "Bearer JWT",
                "request_schema": VoiceContextUpdateRequest.model_json_schema(),
                "response_schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}},
            },
            "navigation_resolve": {
                "method": "POST",
                "path": "/api/navigation/resolve",
                "auth": "Bearer JWT (optional)",
                "request_schema": NavigationResolveRequest.model_json_schema(),
                "response_schema": NavigationResolveResponse.model_json_schema(),
            },
            "homework_check": {
                "method": "POST",
                "path": "/api/homework/check",
                "auth": "X-Service-Token",
                "request_schema": HomeworkCheckRequest.model_json_schema(),
                "response_schema": HomeworkCheckResponse.model_json_schema(),
            },
            "webhook_course": {
                "method": "POST",
                "path": "/webhook/course",
                "auth": "X-Service-Token",
                "request_schema": WebhookCoursePayload.model_json_schema(),
            },
            "webhook_lesson": {
                "method": "POST",
                "path": "/webhook/lesson",
                "auth": "X-Service-Token",
                "request_schema": WebhookLessonPayload.model_json_schema(),
            },
        },
        "example_course": CourseItem(
            id="python-100-days-ru",
            title="Python за 100 дней",
            lessons=[{"id": 1, "title": "День 1", "order_index": 1}],
        ).model_dump(),
    }
