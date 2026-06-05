from sqlalchemy.orm import Session
from app.models.course import Course, Lesson

COURSES_DATA = [
    {
        "id": "python",
        "title": "Python для начинающих",
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
                "content": "Python — высокоуровневый язык программирования, созданный в 1991 году. Он выделяется простым синтаксисом и огромным сообществом разработчиков.\n\n**Почему Python?**\n- Простой и читаемый синтаксис\n- Универсальность: веб, наука о данных, ИИ, автоматизация\n- Огромная экосистема библиотек\n\n**Первая программа:**\n```python\nprint(\"Hello, World!\")\n```\n\nФункция `print()` выводит текст в консоль. Это отправная точка любого Python-разработчика.\n\n**Комментарии:**\n```python\n# Это однострочный комментарий\n\"\"\"\nМногострочный комментарий\n\"\"\"\n```"
            },
            {
                "title": "Переменные и типы данных",
                "duration": "60 мин",
                "content": "В Python переменные объявляются без указания типа — тип определяется автоматически.\n\n**Основные типы:**\n```python\nname = \"Иван\"       # str — строка\nage = 20            # int — целое число\nheight = 1.75       # float — дробное число\nis_student = True   # bool — булево значение\n```\n\n**Коллекции:**\n```python\nfruits = [\"яблоко\", \"банан\"]   # list — список\ncoords = (55.75, 37.61)        # tuple — кортеж\nstudent = {\"name\": \"Иван\"}    # dict — словарь\nunique = {1, 2, 3}             # set — множество\n```\n\n**f-строки:**\n```python\nprint(f\"Меня зовут {name}, мне {age} лет\")\n```"
            },
            {
                "title": "Функции и ООП",
                "duration": "80 мин",
                "content": "Функции — именованные блоки кода, которые можно вызывать многократно.\n\n```python\ndef greet(name, greeting=\"Привет\"):\n    return f\"{greeting}, {name}!\"\n\ngreet(\"Иван\")  # \"Привет, Иван!\"\n```\n\n**Класс и объект:**\n```python\nclass Student:\n    def __init__(self, name, age):\n        self.name = name\n        self.age = age\n        self.grades = []\n\n    def add_grade(self, grade):\n        self.grades.append(grade)\n\n    def average(self):\n        return sum(self.grades) / len(self.grades)\n\n# Создание объекта\nivan = Student(\"Иван\", 20)\nivan.add_grade(5)\nivan.add_grade(4)\nprint(ivan.average())  # 4.5\n```"
            }
        ]
    },
    {
        "id": "ml",
        "title": "Основы машинного обучения",
        "description": "От линейной регрессии до нейронных сетей. Практический курс с примерами на Python и scikit-learn.",
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
                "content": "Машинное обучение (ML) — раздел ИИ, где алгоритмы учатся на данных без явного программирования правил.\n\n**Типы ML:**\n- **Обучение с учителем** — есть правильные ответы (классификация, регрессия)\n- **Обучение без учителя** — ответов нет (кластеризация)\n- **Обучение с подкреплением** — агент учится через награды\n\n**Ключевые понятия:**\n- **Признаки (features)** — входные данные\n- **Целевая переменная** — то, что предсказываем\n- **Переобучение** — модель выучила шум, плохо обобщает\n\n```python\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.model_selection import train_test_split\n\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)\nmodel = LinearRegression()\nmodel.fit(X_train, y_train)\n```"
            },
            {
                "title": "Деревья решений и нейросети",
                "duration": "90 мин",
                "content": "**Дерево решений** — алгоритм, который разделяет данные по условиям.\n\n```python\nfrom sklearn.ensemble import RandomForestClassifier\nmodel = RandomForestClassifier(n_estimators=100, max_depth=5)\nmodel.fit(X_train, y_train)\n```\n\n**Нейронная сеть:**\n- Входной слой — принимает признаки\n- Скрытые слои — обрабатывают информацию\n- Выходной слой — возвращает результат\n\n**Метрики качества:**\n- **Accuracy** — доля правильных предсказаний\n- **Precision / Recall** — точность и полнота\n- **F1-score** — гармоническое среднее Precision и Recall\n- **R²** — для регрессии (1.0 = идеально)"
            }
        ]
    },
    {
        "id": "webdev",
        "title": "Веб-разработка с нуля",
        "description": "HTML, CSS, JavaScript и современные фреймворки. Создавайте красивые и функциональные веб-приложения.",
        "icon": "🌐",
        "color": "#38bdf8",
        "tags": "Frontend,HTML/CSS,JavaScript",
        "lessons_count": 2,
        "duration": "28 часов",
        "students": 2104,
        "rating": 4.7,
        "instructor": "Алексей Новиков",
        "lessons": [
            {
                "title": "HTML и CSS",
                "duration": "60 мин",
                "content": "**HTML** — язык разметки для структуры страниц.\n\n```html\n<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n    <meta charset=\"UTF-8\">\n    <title>Моя страница</title>\n</head>\n<body>\n    <h1>Заголовок</h1>\n    <p>Абзац текста</p>\n</body>\n</html>\n```\n\n**CSS** — язык стилей.\n\n```css\n.container {\n    display: flex;\n    justify-content: center;\n    align-items: center;\n    gap: 10px;\n    background-color: #1a1a2e;\n    color: white;\n}\n\n@media (max-width: 768px) {\n    .container { flex-direction: column; }\n}\n```"
            },
            {
                "title": "JavaScript — основы",
                "duration": "75 мин",
                "content": "JavaScript делает страницы интерактивными.\n\n```javascript\n// Переменные\nlet name = \"Иван\";\nconst PI = 3.14;\n\n// Стрелочные функции\nconst greet = (name) => `Привет, ${name}!`;\n\n// Работа с DOM\nconst btn = document.querySelector('#myBtn');\nbtn.addEventListener('click', () => {\n    alert('Кнопка нажата!');\n});\n\n// Fetch API (асинхронные запросы)\nasync function getData() {\n    const res = await fetch('/api/users');\n    const data = await res.json();\n    return data;\n}\n\n// Методы массивов\nconst nums = [1, 2, 3, 4, 5];\nnums.filter(x => x > 2);     // [3, 4, 5]\nnums.map(x => x * 2);        // [2, 4, 6, 8, 10]\nnums.reduce((a, x) => a + x, 0); // 15\n```"
            }
        ]
    },
    {
        "id": "sql",
        "title": "SQL и базы данных",
        "description": "Реляционные базы данных от основ до оптимизации. PostgreSQL, JOIN-запросы, индексы и транзакции.",
        "icon": "🗃️",
        "color": "#fb923c",
        "tags": "Базы данных,SQL,Backend",
        "lessons_count": 1,
        "duration": "20 часов",
        "students": 756,
        "rating": 4.9,
        "instructor": "Дмитрий Захаров",
        "lessons": [
            {
                "title": "Основы SQL",
                "duration": "70 мин",
                "content": "**SQL** — язык для работы с реляционными базами данных.\n\n```sql\n-- Создание таблицы\nCREATE TABLE students (\n    id INTEGER PRIMARY KEY,\n    name VARCHAR(100) NOT NULL,\n    age INTEGER,\n    email VARCHAR(200) UNIQUE\n);\n\n-- Вставка данных\nINSERT INTO students (name, age, email)\nVALUES ('Иван', 20, 'ivan@example.com');\n\n-- Выборка с условием\nSELECT name, age FROM students\nWHERE age > 18\nORDER BY age DESC\nLIMIT 10;\n\n-- JOIN — объединение таблиц\nSELECT s.name, g.subject, g.grade\nFROM students s\nINNER JOIN grades g ON s.id = g.student_id;\n\n-- Агрегация\nSELECT department, COUNT(*), AVG(salary)\nFROM employees\nGROUP BY department\nHAVING COUNT(*) > 5;\n```\n\n**Транзакции:**\n```sql\nBEGIN;\nUPDATE accounts SET balance = balance - 1000 WHERE id = 1;\nUPDATE accounts SET balance = balance + 1000 WHERE id = 2;\nCOMMIT;\n```"
            }
        ]
    }
]

def seed_nav_graph(db: Session):
    from app.models.navigation import NavNode, NavEdge, NodeAccessRule
    from app.models.course import Course, Lesson

    if db.query(NavNode).first() is not None:
        return

    nodes_map = {}

    def add_node(identifier, title, depth, n_type="page", roles=["all"], desc=None):
        node = NavNode(identifier=identifier, title=title, depth=depth, node_type=n_type, description=desc)
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
                relationship_type=rel
            ))

    # 1. Base Pages
    add_node("/", "Главная", 1)
    add_node("/profile", "Профиль", 1, roles=["student", "teacher"])
    add_node("/journal", "Журнал успеваемости", 1, roles=["teacher"])
    add_node("/homeworks", "Домашние задания", 1)
    add_node("/analytics", "Аналитика", 1, roles=["teacher"])
    add_node("/homeworks/workshop", "Мастерская ДЗ", 2, roles=["teacher"])

    # 2. Actions
    add_node("ACTION:CHECK_HW", "Проверить код ДЗ", 0, n_type="action", roles=["student"])
    add_node("ACTION:GET_HINT", "Запросить подсказку", 0, n_type="action", roles=["student"])

    # 3. Dynamic content
    courses = db.query(Course).all()
    for c in courses:
        cid = f"/courses/{c.id}"
        add_node(cid, f"Курс: {c.title}", 2, desc=c.description[:80] if c.description else "")
        add_edge("/", cid) # Home -> Course

        lessons = db.query(Lesson).filter(Lesson.course_id == c.id).all()
        for l in lessons:
            lid = f"/courses/{c.id}?lesson={l.id}"
            add_node(lid, f"Урок: {l.title}", 3)
            add_edge(cid, lid) # Course -> Lesson
            
            # Link Lesson to actions (simulated incidence)
            add_edge(lid, "ACTION:CHECK_HW", "can_execute")
            add_edge(lid, "ACTION:GET_HINT", "can_execute")

    # Connect base pages to home
    for p in ["/profile", "/journal", "/homeworks", "/analytics"]:
        add_edge("/", p)
        add_edge(p, "/")

    db.commit()


def seed_database(db: Session):
    if db.query(Course).first() is None:
        for course_data in COURSES_DATA:
            lessons_data = course_data.pop("lessons")
            course = Course(**course_data)
            db.add(course)
            
            for lesson_data in lessons_data:
                lesson = Lesson(**lesson_data, course_id=course.id)
                db.add(lesson)
        db.commit()
    
    # Always try to seed nav graph (it checks if it exists internally)
    seed_nav_graph(db)

