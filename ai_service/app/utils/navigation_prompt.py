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
            "ПРАВИЛО ПЕРЕХОДА: Переходи ТОЛЬКО если пользователь явно попросил открыть, перейти, показать или переключить страницу/урок (слова: открой, перейди, переведи, покажи, перелистай). Если пользователь просто задаёт вопрос — отвечай словами, НЕ переходи.",
            "ПРАВИЛО ПОСЛЕ ПЕРЕХОДА: Если ты уже вызвал navigatePage — считай, что переход совершён. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО после этого снова предлагать перейти на ту же страницу или спрашивать «перевести ли вас?». Просто продолжай разговор.",
            "ПРАВИЛО ОТВЕТОВ: Если пользователь задаёт вопрос о курсах (например, «какие есть курсы», «сколько уроков»), перечисли их устно. НЕ переходи никуда.",
            "ПРАВИЛО ДОМАШНИХ ЗАДАНИЙ: Если пользователь задает вопрос по выполнению домашнего задания или просит подсказку, ОБЯЗАТЕЛЬНО сначала используй инструмент queryKnowledgeBase для поиска информации в методичке курса. Опирайся на найденную теорию, но КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО давать прямые ответы на ДЗ или тесты. Используй наводящие вопросы (сократический метод).",
            "НЕДОСТУПНЫЕ ДЕЙСТВИЯ: Если пользователь просит сделать то, чего нет в списке доступных маршрутов или инструментов (например, выйти из аккаунта, сменить тему, удалить профиль), честно ответь, что ты этого пока не умеешь. НИКУДА не переходи.",
            "СТРОГОЕ ПРАВИЛО: Если пользователь просит открыть КУРС или УРОК, которого НЕТ в списке, ты ОБЯЗАН отказать сразу. НЕ подменяй курс на другой (например, не открывай алгоритмы, если просят выдуманный курс). НЕ пытайся угадать путь. Просто скажи словами, что такого курса или урока у тебя нет.",
            "ВНИМАНИЕ: Для открытия уроков используй ТОЛЬКО инструмент openLesson, передавая course_id и lesson_number (порядковый номер). Для остальных страниц используй navigatePage.",
            "Для «следующий урок», «предыдущий урок», «листай дальше» — используй openAdjacentLesson (delta=1 или -1), не угадывай номер урока.",
            "",
            "Используй ТОЛЬКО пути и инструменты из списка ниже или ссылки из оповещений. Выдумывать пути КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО.",
        ])
    lines.append("")
    lines.append(db_nav_routes)

    return "\n".join(lines)


def build_db_navigation_routes_list(db: Any, role: str | None = None, voice: bool = False, current_course_id: str | None = None, user: Any = None) -> str:
    """Генерация списка маршрутов на основе графа из БД (Матрицы инцидентности)."""
    from app.models.navigation import NavNode, NodeAccessRule
    
    query = db.query(NavNode).join(NodeAccessRule).filter(
        NodeAccessRule.allowed_role.in_([role, "all"]) if role else NodeAccessRule.allowed_role == "all"
    ).order_by(NavNode.depth, NavNode.id)
    
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
            course_id = identifier.split("?")[0].replace("/courses/", "")
            
            # Если мы находимся на конкретном курсе, скрываем уроки других курсов
            if current_course_id and current_course_id != "default" and course_id != current_course_id:
                continue
                
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
                
        # Strip external URLs in parentheses to prevent AI from refusing to use the navigate tool
        import re
        title = re.sub(r'\s*\([^)]+\.[a-z]{2,}[^)]*\)', '', title)
        
        desc = f" — {p.description}" if p.description else ""
        
        if voice:
            if "?lesson=" in identifier:
                # Extracts course_id and uses the sequential idx we just calculated
                route_cmd = f"openLesson(course_id=\"{course_id}\", lesson_number={idx})"
            else:
                route_cmd = f"navigatePage(path=\"{identifier}\")"
        else:
            route_cmd = f"[NAVIGATE:{identifier}]"
            
        lines.append(f"  - {title}{desc} → {route_cmd}")
        
    lines.append("")
    
    # 1.5 Домашние задания пользователя (если он студент)
    if user and role == "student":
        from app.models.homework import HomeworkAssignment
        assignments = db.query(HomeworkAssignment).filter(HomeworkAssignment.student_id == user.id).all()
        if assignments:
            lines.append("Доступные домашние задания:")
            for a in assignments:
                hw = a.homework
                if hw:
                    route_cmd = f"navigatePage(path=\"/homeworks/{hw.id}\")" if voice else f"[NAVIGATE:/homeworks/{hw.id}]"
                    lines.append(f"  - ДЗ: {hw.title} (по курсу {hw.course_id}) -> {route_cmd}")
            lines.append("")

    # 2. Потом возможные действия
    actions = [n for n in nodes if n.node_type == "action"]
    if actions:
        lines.append("Доступные действия на платформе:")
        for a in actions:
            desc = f" — {a.description}" if a.description else ""
            lines.append(f"  - {a.title}{desc} → [{a.identifier}]")
            
    return "\n".join(lines)

