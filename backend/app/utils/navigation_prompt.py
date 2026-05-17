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
            "    Пример: «Я нашёл курс «Python для начинающих». Перевести вас на страницу этого курса?»",
            "  Шаг 2 (после «да», «давай», «ок»): коротко «Открываю курс «Python для начинающих»»",
            "    и в конце молча один тег: [NAVIGATE:/courses/python]",
            "",
            "При вопросе о подтверждении ВСЕГДА произноси:",
            "  — какой курс ты нашёл (полное название);",
            "  — куда собираешься перевести («на страницу курса …»).",
            "Не говори просто «на этот курс» без названия.",
            "",
            "Журнал / Профиль / Главная / Домашние задания — тег только при явной просьбе.",
            "Используй ТОЛЬКО id из списка ниже.",
        ])
    else:
        lines.append("### НАВИГАЦИЯ")
        lines.extend([
            "Переход на курс — два шага:",
            "  1) Назови полное название курса и спроси: «Перевести на страницу курса «…»?» — без тега.",
            "  2) После «да» — тег [NAVIGATE:/courses/id] в конце.",
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

    return "\n".join(lines)
