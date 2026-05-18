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


def build_navigation_prompt(
    available_courses: List[Dict[str, Any]],
    *,
    voice: bool = False,
) -> str:
    courses = available_courses or _FALLBACK_COURSES
    lines: List[str] = []

    if voice:
        lines.extend([
            "### НАВИГАЦИЯ (голос) — ОБЯЗАТЕЛЬНО",
            "Тег [NAVIGATE:путь] — служебная метка ТОЛЬКО в самом конце ответа. Её НЕ произносят вслух.",
            "СТРОГО ЗАПРЕЩЕНО говорить вслух: navigate, NAVIGATE, courses, URL, слэши, id, скобки, английский.",
            "В приветствии и без просьбы пользователя — НЕ ставь [NAVIGATE:...].",
            "",
            "Переход на КУРС — ровно два шага:",
            "  Шаг 1 (БЕЗ тега): назови полное название курса из списка и спроси подтверждение.",
            "  Шаг 2 (после «да», «давай», «ок»): коротко «Открываю курс …»",
            "    и в конце молча один тег: [NAVIGATE:/courses/python]",
            "",
            "Переход на УРОК внутри курса:",
            "  Формат тега: [NAVIGATE:/courses/{course_id}?lesson={lesson_id}]",
            "  Пример: [NAVIGATE:/courses/python?lesson=2]",
            "  Сначала открой курс (или убедись, что пользователь уже на нём), затем урок.",
            "  Назови полное название урока из списка ниже.",
            "",
            "Журнал / Профиль / Главная / Домашние задания — тег сразу при явной просьбе.",
            "Используй ТОЛЬКО id из списка ниже.",
        ])
    lines.append("")
    lines.append("Доступные маршруты:")
    for path, title in STATIC_ROUTES:
        lines.append(f"  - {title} → [NAVIGATE:{path}]")

    lines.append("")
    lines.append("Курсы (точный id в теге):")
    for c in courses:
        cid = c.get("id", "")
        title = c.get("title", "")
        desc = (c.get("description") or "")[:80]
        icon = c.get("icon", "")
        extra = f" — {desc}" if desc else ""
        lines.append(f"  - {icon} «{title}» (id: {cid}){extra} → [NAVIGATE:/courses/{cid}]")
        lessons = c.get("lessons") or []
        if lessons:
            lines.append(f"    Уроки курса «{title}»:")
            for les in lessons:
                lid = les.get("id")
                lt = les.get("title", "")
                lines.append(
                    f"      · «{lt}» (lesson_id: {lid}) → [NAVIGATE:/courses/{cid}?lesson={lid}]"
                )

    return "\n".join(lines)


def build_navigation_routes_list(available_courses: List[Dict[str, Any]]) -> str:
    """Только список маршрутов (правила навигации — в основном промпте чата)."""
    courses = available_courses or _FALLBACK_COURSES
    lines = ["Список доступных маршрутов и курсов:"]
    for path, title in STATIC_ROUTES:
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
