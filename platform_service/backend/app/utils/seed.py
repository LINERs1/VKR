"""
seed.py для platform_service.

Создаёт начальные курсы, уроки, пользователей.
Навигационный граф (NavNode/NavEdge) — только в ai_service.
"""
from sqlalchemy.orm import Session

from app.models.course import Course, Lesson
from app.models.user import User, UserRole

COURSES_DATA = [
    {
        "id": "algorithms",
        "title": "Основы алгоритмизации и программирования",
        "description": "Освойте программирование с нуля: переменные, функции, ООП и работа с файлами.",
        "icon": "🐍",
        "color": "#22d3a5",
        "tags": "Программирование,Начинающий",
        "lessons_count": 3,
        "duration": "24 часа",
        "students": 1247,
        "rating": 4.9,
        "instructor": "Михаил Ковалёв",
        "lessons": [
            {
                "title": "Введение в Python",
                "duration": "45 мин",
                "content": "Python — высокоуровневый язык программирования, созданный в 1991 году.\n\n**Почему Python?**\n- Простой синтаксис\n- Универсальность\n- Огромная экосистема\n\n```python\nprint('Hello, World!')\n```",
            },
            {
                "title": "Переменные и типы данных",
                "duration": "60 мин",
                "content": "В Python переменные объявляются без указания типа.\n\n```python\nname = 'Иван'\nage = 20\nheight = 1.75\n```",
            },
            {
                "title": "Функции и ООП",
                "duration": "80 мин",
                "content": "Функции — именованные блоки кода.\n\n```python\ndef greet(name):\n    return f'Привет, {name}!'\n```",
            },
        ],
    },
    {
        "id": "ml",
        "title": "Основы машинного обучения",
        "description": "От линейной регрессии до нейронных сетей.",
        "icon": "🤖",
        "color": "#a78bfa",
        "tags": "Data Science,ИИ,Python",
        "lessons_count": 2,
        "duration": "32 часа",
        "students": 893,
        "rating": 4.8,
        "instructor": "Елена Смирнова",
        "lessons": [
            {
                "title": "Введение в машинное обучение",
                "duration": "60 мин",
                "content": "Машинное обучение — раздел ИИ, где алгоритмы учатся на данных.",
            },
            {
                "title": "Деревья решений и нейросети",
                "duration": "90 мин",
                "content": "Деревья решений и основы нейронных сетей.",
            },
        ],
    },
    {
        "id": "webdev",
        "title": "Веб-разработка с нуля",
        "description": "HTML, CSS, JavaScript и современные фреймворки.",
        "icon": "🌐",
        "color": "#38bdf8",
        "tags": "Frontend,HTML/CSS,JavaScript",
        "lessons_count": 2,
        "duration": "28 часов",
        "students": 2104,
        "rating": 4.7,
        "instructor": "Алексей Новиков",
        "lessons": [
            {"title": "HTML и CSS", "duration": "60 мин", "content": "HTML — язык разметки, CSS — язык стилей."},
            {"title": "JavaScript — основы", "duration": "75 мин", "content": "JavaScript делает страницы интерактивными."},
        ],
    },
    {
        "id": "sql",
        "title": "SQL и базы данных",
        "description": "Реляционные базы данных от основ до оптимизации.",
        "icon": "🗃️",
        "color": "#fb923c",
        "tags": "Базы данных,SQL,Backend",
        "lessons_count": 1,
        "duration": "20 часов",
        "students": 756,
        "rating": 4.9,
        "instructor": "Дмитрий Захаров",
        "lessons": [
            {"title": "Основы SQL", "duration": "70 мин", "content": "SQL — язык для работы с реляционными БД."},
        ],
    },
]

USERS_DATA = [
    {
        "username": "student1",
        "full_name": "Иван Петров",
        "email": "student1@example.com",
        "role": UserRole.student,
        "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/UpfVTiQUm",  # "password"
    },
    {
        "username": "teacher1",
        "full_name": "Мария Иванова",
        "email": "teacher1@example.com",
        "role": UserRole.teacher,
        "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/UpfVTiQUm",
    },
    {
        "username": "admin1",
        "full_name": "Администратор системы",
        "email": "admin1@example.com",
        "role": UserRole.admin,
        "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/UpfVTiQUm",  # "password"
    },
]


def seed_database(db: Session):
    """Создаёт начальные курсы, уроки и пользователей."""
    if db.query(Course).first() is None:
        for course_data in COURSES_DATA:
            lessons_data = course_data.pop("lessons")
            course = Course(**course_data)
            db.add(course)
            db.flush()
            for lesson_data in lessons_data:
                lesson = Lesson(**lesson_data, course_id=course.id)
                db.add(lesson)
        db.commit()

    if db.query(User).first() is None:
        for u in USERS_DATA:
            db.add(User(**u))
        db.commit()
