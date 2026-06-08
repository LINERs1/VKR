"""Общие инструкции навигации для чата и Ultravox (на основе графа БД)."""
from typing import Any

def build_navigation_prompt(
    db_nav_routes: str,
    *,
    voice: bool = False,
) -> str:
    """Оборачивает список маршрутов из БД в инструкции для LLM."""
    lines = []

    if voice:
        lines.extend([
            "### НАВИГАЦИЯ (голос) — ОБЯЗАТЕЛЬНО",
            "Для любого перехода по сайту вызывай инструмент navigatePage(path=...).",
            "ЗАПРЕЩЕНО произносить вслух: navigate, NAVIGATE, path, URL, слэши, id курса, скобки, теги.",
            "ЗАПРЕЩЕНО писать или говорить [NAVIGATE:...] — только navigatePage.",
            "Сначала одной фразой по-русски («Открываю журнал»), затем navigatePage. После вызова не повторяй переход.",
            "В приветствии и без просьбы пользователя — navigatePage не вызывай.",
            "",
        ])
        lines.extend([
            "ПРАВИЛО ПЕРЕХОДА: Переходи на нужную страницу без дополнительных вопросов, сразу вызывая инструмент navigatePage. Не спрашивай разрешения.",
            "ПРАВИЛО ОТВЕТОВ: Если пользователь просто задает вопрос (например, «сколько уроков в курсе Python?»), ответь на него словами, посчитав уроки в списке ниже. НЕ вызывай navigatePage, если пользователь прямо не попросил открыть курс или перейти куда-то.",
            "НЕДОСТУПНЫЕ ДЕЙСТВИЯ: Если пользователь просит сделать то, чего нет в списке доступных маршрутов или инструментов (например, выйти из аккаунта, сменить тему, удалить профиль), честно ответь, что ты этого пока не умеешь. НИКУДА не переходи.",
            "СТРОГОЕ ПРАВИЛО: Если пользователь просит открыть урок, которого НЕТ в списке (например, 5-й урок, а в списке только 3), ты ОБЯЗАН отказать сразу. НЕ переходи на страницу курса в надежде найти его там. НЕ пытайся угадать путь. Просто скажи, что такого урока нет.",
            "ВНИМАНИЕ: Цифры внутри самих путей (например, ?lesson=4) — это внутренние ID базы данных, они НЕ СОВПАДАЮТ с порядковым номером урока! Ищи нужный урок ТОЛЬКО по тексту 'Урок 1', 'Урок 2' и т.д. слева от стрелочки.",
            "",
            "Используй ТОЛЬКО пути из списка ниже или ссылки из оповещений. Выдумывать пути КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО.",
        ])
    lines.append("")
    lines.append(db_nav_routes)

    return "\n".join(lines)


def build_db_navigation_routes_list(db: Any, role: str | None = None, voice: bool = False) -> str:
    """Генерация списка маршрутов на основе графа из БД (Матрицы инцидентности)."""
    from app.models.navigation import NavNode, NodeAccessRule
    
    query = db.query(NavNode).join(NodeAccessRule).filter(
        NodeAccessRule.allowed_role.in_([role, "all"]) if role else NodeAccessRule.allowed_role == "all"
    ).order_by(NavNode.depth, NavNode.id)
    
    nodes = query.all()
    
    nodes = query.all()
    
    lines = ["Список доступных маршрутов (из графа БД):"]
    
    # 1. Сначала обычные страницы
    pages = [n for n in nodes if n.node_type == "page"]
    
    course_lesson_counters = {}
    
    for p in pages:
        title = p.title
        identifier = p.identifier
        
        # Вычисляем порядковый номер урока в курсе
        if identifier.startswith("/courses/") and "?lesson=" in identifier:
            course_id = identifier.split("?")[0]
            if course_id not in course_lesson_counters:
                course_lesson_counters[course_id] = 1
            else:
                course_lesson_counters[course_id] += 1
            
            idx = course_lesson_counters[course_id]
            # Добавляем номер урока в название
            if title.startswith("Урок:"):
                title = title.replace("Урок:", f"Урок {idx}:", 1)
            elif not title.startswith("Урок "):
                title = f"Урок {idx}: {title}"
                
        desc = f" — {p.description}" if p.description else ""
        
        if voice:
            if identifier.startswith("/courses/") and "?lesson=" in identifier:
                # Use virtual path for lessons: vpath://course_id/lesson/idx
                course_id = identifier.split("?")[0].replace("/courses/", "")
                vpath = f"vpath://{course_id}/lesson/{idx}"
            else:
                # Use virtual path for normal pages
                vpath = f"vpath://page{identifier}"
            route_cmd = f"navigatePage(path=\"{vpath}\")"
        else:
            route_cmd = f"[NAVIGATE:{identifier}]"
            
        lines.append(f"  - {title}{desc} → {route_cmd}")
        
    lines.append("")
    
    # 2. Потом возможные действия
    actions = [n for n in nodes if n.node_type == "action"]
    if actions:
        lines.append("Доступные действия на платформе:")
        for a in actions:
            desc = f" — {a.description}" if a.description else ""
            lines.append(f"  - {a.title}{desc} → [{a.identifier}]")
            
    return "\n".join(lines)

