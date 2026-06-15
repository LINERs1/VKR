"""Разрешения embeddable-виджета: role + явный permissions[]."""

from __future__ import annotations

from app.schemas.embeddable import ALL_PERMISSIONS, ROLE_DEFAULT_PERMISSIONS

TOOL_PERMISSION: dict[str, str] = {
    "navigatePage": "navigate",
    "openLesson": "navigate",
    "openAdjacentLesson": "navigate",
    "queryKnowledgeBase": "rag",
    "getPageContext": "navigate",
    "getHomeworkHint": "homework_hint",
    "reviewHomework": "homework_review",
    "reviewAllHomeworks": "homework_mass_review",
    "fillHomeworkForm": "homework_form",
}


def resolve_permissions(role: str | None, explicit: list[str] | None = None) -> set[str]:
    role_norm = (role or "student").lower()
    base = ROLE_DEFAULT_PERMISSIONS.get(role_norm, ROLE_DEFAULT_PERMISSIONS["student"])
    if not explicit:
        return set(base)
    allowed = {p for p in explicit if p in ALL_PERMISSIONS}
    return allowed & base if role_norm == "student" else allowed or set(base)


def filter_tools_by_permissions(tools: list[dict], granted: set[str]) -> list[dict]:
    out: list[dict] = []
    for tool in tools:
        name = (tool.get("temporaryTool") or {}).get("modelToolName", "")
        perm = TOOL_PERMISSION.get(name)
        if perm is None or perm in granted:
            out.append(tool)
    return out
