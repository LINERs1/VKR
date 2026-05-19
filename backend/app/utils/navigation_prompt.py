"""Общие инструкции навигации для чата и Ultravox."""
from typing import Any, Dict, List

STATIC_ROUTES = [
    ("/", "Главная"),
    ("/journal", "Журнал успеваемости"),
    ("/profile", "Профиль"),
    ("/homeworks", "Домашние задания"),
]

_FALLBACK_COURSES = [
    {"id": "python", "title": "Python для начинающих", "icon": "🐍"},
    {"id": "ml", "title": "Основы машинного обучения", "icon": "🤖"},
    {"id": "webdev", "title": "Веб-разработка с нуля", "icon": "🌐"},
    {"id": "sql", "title": "SQL и базы данных", "icon": "🗃️"},
]


def _static_routes_for_role(role: str | None) -> List[tuple[str, str]]:
    routes = list(STATIC_ROUTES)
    if role == "student":
        routes = [(p, t) for p, t in routes if p != "/journal"]
    return routes


def build_navigation_prompt(
    available_courses: List[Dict[str, Any]],
    *,
    voice: bool = False,
    role: str | None = None,
) -> str:
    courses = available_courses or _FALLBACK_COURSES
    lines: List[str] = []

    if voice:
        lines.extend([
            "### НАВИГАЦИЯ (голос) — ОБЯЗАТЕЛЬНО",
            "Для любого перехода по сайту вызывай инструмент navigatePage(path=...).",
            "ЗАПРЕЩЕНО произносить вслух: navigate, NAVIGATE, path, URL, слэши, id курса, скобки, теги.",
            "ЗАПРЕЩЕНО писать или говорить [NAVIGATE:...] — только navigatePage.",
            "Сначала одной фразой по-русски («Открываю журнал»), затем navigatePage. После вызова не повторяй переход.",
            "В приветствии и без просьбы пользователя — navigatePage не вызывай.",
            "",
            "Переход на КУРС — два шага:",
            "  Шаг 1: назови полное название курса и спроси подтверждение (без navigatePage).",
            "  Шаг 2 (после «да», «давай», «ок»): navigatePage(path=\"/courses/{course_id}\") "
            "и коротко «Открываю курс …».",
            "",
            "Переход на УРОК: navigatePage(path=\"/courses/{course_id}?lesson={lesson_id}\").",
            "Сначала курс, затем урок. Назови полное название урока из списка.",
            "",
            "Журнал / Профиль / Главная / Домашние задания — navigatePage сразу при явной просьбе.",
            "Используй ТОЛЬКО пути из списка ниже.",
        ])
    lines.append("")
    route_fmt = "navigatePage(path=\"{path}\")" if voice else "[NAVIGATE:{path}]"
    lines.append("Доступные маршруты:")
    for path, title in _static_routes_for_role(role):
        lines.append(f"  - {title} → {route_fmt.format(path=path)}")

    lines.append("")
    lines.append("Курсы (точный id в пути):")
    for c in courses:
        cid = c.get("id", "")
        title = c.get("title", "")
        desc = (c.get("description") or "")[:80]
        icon = c.get("icon", "")
        extra = f" — {desc}" if desc else ""
        lines.append(
            f"  - {icon} «{title}» (id: {cid}){extra} → "
            f"{route_fmt.format(path=f'/courses/{cid}')}"
        )
        lessons = c.get("lessons") or []
        if lessons:
            lines.append(f"    Уроки курса «{title}»:")
            for les in lessons:
                lid = les.get("id")
                lt = les.get("title", "")
                lines.append(
                    f"      · «{lt}» (lesson_id: {lid}) → "
                    f"{route_fmt.format(path=f'/courses/{cid}?lesson={lid}')}"
                )

    return "\n".join(lines)


def build_navigation_routes_list(
    available_courses: List[Dict[str, Any]],
    *,
    role: str | None = None,
) -> str:
    """Только список маршрутов (правила навигации — в основном промпте чата)."""
    courses = available_courses or _FALLBACK_COURSES
    lines = ["Список доступных маршрутов и курсов:"]
    for path, title in _static_routes_for_role(role):
        lines.append(f"  - {title} → [NAVIGATE:{path}]")
    lines.append("")
    lines.append("Курсы:")
    for c in courses:
        cid = c.get("id", "")
        title = c.get("title", "")
        icon = c.get("icon", "")
        lines.append(f"  - {icon} «{title}» → [NAVIGATE:/courses/{cid}]")
        for les in c.get("lessons") or []:
            lines.append(
                f"      · «{les.get('title', '')}» → [NAVIGATE:/courses/{cid}?lesson={les.get('id')}]"
            )
    return "\n".join(lines)
