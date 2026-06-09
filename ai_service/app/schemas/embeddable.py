"""Контракт embeddable-интеграции: платформа → ИИ-сервис."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# Допустимые права (permissions)
PERMISSION_NAVIGATE = "navigate"
PERMISSION_RAG = "rag"
PERMISSION_HOMEWORK_HINT = "homework_hint"
PERMISSION_HOMEWORK_REVIEW = "homework_review"
PERMISSION_HOMEWORK_MASS_REVIEW = "homework_mass_review"
PERMISSION_JOURNAL_SUMMARY = "journal_summary"
PERMISSION_HOMEWORK_FORM = "homework_form"
PERMISSION_NOTIFICATIONS = "notifications"

ALL_PERMISSIONS = frozenset({
    PERMISSION_NAVIGATE,
    PERMISSION_RAG,
    PERMISSION_HOMEWORK_HINT,
    PERMISSION_HOMEWORK_REVIEW,
    PERMISSION_HOMEWORK_MASS_REVIEW,
    PERMISSION_JOURNAL_SUMMARY,
    PERMISSION_HOMEWORK_FORM,
    PERMISSION_NOTIFICATIONS,
})

ROLE_DEFAULT_PERMISSIONS: dict[str, frozenset[str]] = {
    "student": frozenset({
        PERMISSION_NAVIGATE,
        PERMISSION_RAG,
        PERMISSION_HOMEWORK_HINT,
        PERMISSION_NOTIFICATIONS,
    }),
    "teacher": frozenset(ALL_PERMISSIONS),
    "admin": frozenset(ALL_PERMISSIONS),
}


class LessonItem(BaseModel):
    id: int | str
    title: str = ""
    order_index: int = 0


class CourseItem(BaseModel):
    id: str
    title: str = ""
    description: str = ""
    icon: str = ""
    lessons: list[LessonItem] = Field(default_factory=list)


class BreadcrumbItem(BaseModel):
    label: str
    path: str = ""


class PlatformUserContext(BaseModel):
    """Контекст пользователя от хост-платформы."""

    platform_user_id: str | int | None = None
    username: str = ""
    role: str = "student"
    permissions: list[str] = Field(default_factory=list)


class PlatformPageContext(BaseModel):
    current_path: str = "/"
    current_page: str = ""
    page_content: str = ""
    course_id: str = "default"
    course_name: str = ""
    breadcrumbs: list[BreadcrumbItem] = Field(default_factory=list)
    lesson_id: str | None = None
    lesson_title: str | None = None
    lesson_index: int | None = None
    total_lessons: int | None = None


class VoiceCallRequest(BaseModel):
    """POST /api/ultravox/call — запуск голосовой сессии."""

    session_id: str | None = None
    user: PlatformUserContext | None = None
    page: PlatformPageContext | None = None
    courses: list[CourseItem] = Field(default_factory=list)
    voice_id: str | None = None


class VoiceCallResponse(BaseModel):
    joinUrl: str
    callId: str | None = None
    sessionId: str
    granted_permissions: list[str] = Field(default_factory=list)


class VoiceContextUpdateRequest(BaseModel):
    """POST /api/ultravox/context — обновление экрана во время звонка."""

    session_id: str
    user: PlatformUserContext | None = None
    page: PlatformPageContext | None = None
    homework: dict[str, Any] | None = None


class NavigationResolveRequest(BaseModel):
    """POST /api/navigation/resolve."""

    path_or_query: str
    courses: list[CourseItem] = Field(default_factory=list)
    fetch_from_platform: bool = False


class NavigationResolveResponse(BaseModel):
    status: str  # ok | ambiguous | not_found | static
    path: str | None = None
    course_id: str | None = None
    query: dict[str, str] = Field(default_factory=dict)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    message: str = ""


class HomeworkCheckRequest(BaseModel):
    """POST /api/homework/check — только service-to-service от платформы."""

    assignment_id: int
    username: str
    homework_description: str
    student_code: str | None = None
    student_text: str | None = None
    content_json: str | None = None
    student_quiz: dict | None = None
    is_demo: bool = False


class HomeworkCheckResponse(BaseModel):
    teacher_feedback: str
    suggested_grade: int | None = None
    error_fragments: list[str] = Field(default_factory=list)


class WebhookCoursePayload(BaseModel):
    id: str
    title: str


class WebhookLessonPayload(BaseModel):
    id: int
    course_id: str
    title: str
    content: str | None = None
