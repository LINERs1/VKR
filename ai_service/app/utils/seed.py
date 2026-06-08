"""
seed.py для ai_service.

Создаёт начальные данные:
- CourseRef / LessonRef — облегчённые зеркала (только id + title)
- NavNode / NavEdge / NodeAccessRule — граф навигации

Полные данные (тексты уроков, описания курсов) хранятся на платформе.
ИИ-сервис получает их через Webhooks или REST-запросы к платформе.
"""
from sqlalchemy.orm import Session

from app.models.mirror import CourseRef, LessonRef

# Начальные зеркала курсов и уроков (только id и title)
COURSES_SEED = [
    {
        "id": "algorithms",
        "title": "Основы алгоритмизации и программирования",
        "lessons": [
            {"id": 1, "title": "Введение в Python"},
            {"id": 2, "title": "Переменные и типы данных"},
            {"id": 3, "title": "Функции и ООП"},
        ],
    },
    {
        "id": "ml",
        "title": "Основы машинного обучения",
        "lessons": [
            {"id": 4, "title": "Введение в машинное обучение"},
            {"id": 5, "title": "Деревья решений и нейросети"},
        ],
    },
    {
        "id": "webdev",
        "title": "Веб-разработка с нуля",
        "lessons": [
            {"id": 6, "title": "HTML и CSS"},
            {"id": 7, "title": "JavaScript — основы"},
        ],
    },
    {
        "id": "sql",
        "title": "SQL и базы данных",
        "lessons": [
            {"id": 8, "title": "Основы SQL"},
        ],
    },
]


def seed_mirror(db: Session):
    """Создаёт CourseRef и LessonRef если их ещё нет."""
    if db.query(CourseRef).first() is not None:
        return

    for course_data in COURSES_SEED:
        course_ref = CourseRef(id=course_data["id"], title=course_data["title"])
        db.add(course_ref)
        db.flush()

        for lesson_data in course_data["lessons"]:
            lesson_ref = LessonRef(
                id=lesson_data["id"],
                course_id=course_data["id"],
                title=lesson_data["title"],
            )
            db.add(lesson_ref)

    db.commit()


def seed_nav_graph(db: Session):
    """Создаёт граф навигации из NavNode/NavEdge на основе зеркал."""
    from app.models.navigation import NavNode, NavEdge, NodeAccessRule

    if db.query(NavNode).first() is not None:
        return

    nodes_map = {}

    def add_node(identifier, title, depth, n_type="page", roles=None, desc=None):
        if roles is None:
            roles = ["all"]
        node = NavNode(
            identifier=identifier,
            title=title,
            depth=depth,
            node_type=n_type,
            description=desc,
        )
        db.add(node)
        db.flush()
        for r in roles:
            db.add(NodeAccessRule(nav_node_id=node.id, allowed_role=r))
        nodes_map[identifier] = node
        return node

    def add_edge(from_id, to_id, rel="navigates_to"):
        if from_id in nodes_map and to_id in nodes_map:
            db.add(NavEdge(
                source_node_id=nodes_map[from_id].id,
                target_node_id=nodes_map[to_id].id,
                relationship_type=rel,
            ))

    # Базовые страницы
    add_node("/", "Главная", 1)
    add_node("/profile", "Профиль", 1, roles=["student", "teacher"])
    add_node("/journal", "Журнал успеваемости", 1, roles=["teacher"])
    add_node("/homeworks", "Домашние задания", 1)
    add_node("/analytics", "Аналитика", 1, roles=["teacher"])
    add_node("/homeworks/workshop", "Мастерская ДЗ", 2, roles=["teacher"])

    # Действия
    add_node("ACTION:CHECK_HW", "Проверить код ДЗ", 0, n_type="action", roles=["student"])
    add_node("ACTION:GET_HINT", "Запросить подсказку", 0, n_type="action", roles=["student"])

    # Курсы и уроки из зеркал
    courses = db.query(CourseRef).all()
    for c in courses:
        cid = f"/courses/{c.id}"
        add_node(cid, f"Курс: {c.title}", 2)
        add_edge("/", cid)

        lessons = db.query(LessonRef).filter(LessonRef.course_id == c.id).all()
        for idx, l in enumerate(lessons, start=1):
            lid = f"/courses/{c.id}?lesson={l.id}"
            add_node(lid, f"Урок {idx}: {l.title}", 3)
            add_edge(cid, lid)
            add_edge(lid, "ACTION:CHECK_HW", "can_execute")
            add_edge(lid, "ACTION:GET_HINT", "can_execute")

    # Связи базовых страниц с главной
    for p in ["/profile", "/journal", "/homeworks", "/analytics"]:
        add_edge("/", p)
        add_edge(p, "/")

    db.commit()


def seed_database(db: Session):
    """Точка входа: создаёт зеркала и граф навигации."""
    seed_mirror(db)
    seed_nav_graph(db)
