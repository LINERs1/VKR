import sys
from pathlib import Path

backend_dir = Path("c:/Users/liner/Desktop/Diplom/backend")
sys.path.append(str(backend_dir))

from app.database import SessionLocal
from app.models.course import Course, Lesson
from app.models.navigation import NavNode, NavEdge
import app.models.homework
import app.models.user
import app.models.assistant_metric
import app.models.chat_message
import app.models.homework_template
import app.models.notification
import app.models.student_weak_topic

REALISTIC_LESSONS = {
    "python": [
        {"title": "Введение в Python", "duration": "45 мин"},
        {"title": "Переменные и типы данных", "duration": "60 мин"},
        {"title": "Функции и ООП", "duration": "80 мин"},
        {"title": "Работа с файлами и исключения", "duration": "70 мин"},
        {"title": "Основы веб-разработки на FastAPI", "duration": "90 мин"}
    ],
    "ml": [
        {"title": "Введение в машинное обучение", "duration": "60 мин"},
        {"title": "Деревья решений и случайный лес", "duration": "90 мин"},
        {"title": "Основы нейронных сетей", "duration": "120 мин"},
        {"title": "Глубокое обучение и PyTorch", "duration": "110 мин"},
        {"title": "Обработка естественного языка (NLP)", "duration": "100 мин"}
    ],
    "webdev": [
        {"title": "Основы HTML и семантика", "duration": "60 мин"},
        {"title": "Продвинутый CSS и Flexbox", "duration": "75 мин"},
        {"title": "JavaScript — основы и DOM", "duration": "90 мин"},
        {"title": "Асинхронный JS и API", "duration": "80 мин"},
        {"title": "Введение в Vue.js", "duration": "120 мин"}
    ],
    "sql": [
        {"title": "Введение в реляционные БД", "duration": "70 мин"},
        {"title": "Простые выборки SELECT и фильтрация", "duration": "60 мин"},
        {"title": "Связи таблиц и оператор JOIN", "duration": "80 мин"},
        {"title": "Агрегация данных и группировка", "duration": "70 мин"},
        {"title": "Индексы и транзакции", "duration": "90 мин"}
    ]
}

FILLER_TEXT = """

### Подробное описание

Это расширенный материал урока, предназначенный для глубокого погружения в тему. В реальном мире образовательные курсы включают не только базовые примеры, но и глубокую теоретическую базу, исторический контекст и множество примеров из практики. 

Понимание этой темы критически важно для успешного прохождения последующих уроков. Многие начинающие разработчики часто упускают эти нюансы, что приводит к сложноразрешимым ошибкам в архитектуре крупных приложений. Поэтому мы настоятельно рекомендуем внимательно изучить каждый абзац и повторить примеры локально на вашем компьютере.

**Почему это важно?**
1. Оптимизация производительности: правильное использование базовых конструкций позволяет коду работать в разы быстрее.
2. Поддержка и масштабируемость: чисто написанный код легко читать и модифицировать.
3. Безопасность: многие уязвимости возникают из-за незнания тонкостей работы языка.

### Практическое применение

На практике эти знания применяются практически в каждом проекте. Будь то разработка небольшого скрипта для автоматизации рутинных задач или создание огромного микросервисного ландшафта для банковской сферы. 

> Важно: всегда проверяйте краевые случаи. Ваш код должен уметь обрабатывать не только идеальные данные, но и неожиданный пользовательский ввод, обрывы сети и аппаратные сбои.

Давайте рассмотрим еще несколько примеров.

```python
# Пример из реального проекта
def process_data(data):
    if not data:
        return []
    result = []
    for item in data:
        if validate(item):
            result.append(transform(item))
    return result
```

Как видно из примера, мы сначала проверяем входные данные, затем валидируем каждый элемент и только потом применяем трансформацию. Этот подход называется «ранний возврат» (early return) и считается хорошей практикой в индустрии.

### Дополнительные материалы

Не забывайте обращаться к официальной документации. Это ваш главный друг и наставник в мире IT. Ни один курс, даже самый подробный, не сможет покрыть 100% всех возможных ситуаций, поэтому умение самостоятельно находить информацию — ключевой навык инженера.

"""

def main():
    db = SessionLocal()
    
    # Сначала удалим тестовые уроки
    test_lessons = db.query(Lesson).filter(Lesson.title.like("%Тестовый урок%")).all()
    for l in test_lessons:
        # Удаляем из NavNode и NavEdge
        lid = f"/courses/{l.course_id}?lesson={l.id}"
        node = db.query(NavNode).filter_by(identifier=lid).first()
        if node:
            db.query(NavEdge).filter((NavEdge.source_node_id == node.id) | (NavEdge.target_node_id == node.id)).delete()
            db.delete(node)
        db.delete(l)
    db.commit()
    print(f"Deleted {len(test_lessons)} test lessons.")

    courses = db.query(Course).all()
    
    for course in courses:
        expected = REALISTIC_LESSONS.get(course.id, [])
        existing = db.query(Lesson).filter(Lesson.course_id == course.id).order_by(Lesson.id).all()
        
        # Обновляем существующие и добавляем новые, чтобы было ровно 5
        for i in range(5):
            if i < len(expected):
                title = expected[i]["title"]
                duration = expected[i]["duration"]
                
                if i < len(existing):
                    lesson = existing[i]
                    lesson.title = title
                    lesson.duration = duration
                    # Добавляем филлер к оригинальному контенту
                    if "Практическое применение" not in lesson.content:
                        lesson.content += FILLER_TEXT
                else:
                    # Создаем новый
                    lesson = Lesson(
                        course_id=course.id,
                        title=title,
                        duration=duration,
                        content=f"Этот урок посвящен теме «{title}». Здесь мы разберем основные концепции и закрепим их на практике." + FILLER_TEXT
                    )
                    db.add(lesson)
                    db.flush()
                    
                    # Создаем NavNode
                    course_node = db.query(NavNode).filter_by(identifier=f"/courses/{course.id}").first()
                    if course_node:
                        lid = f"/courses/{course.id}?lesson={lesson.id}"
                        node = NavNode(identifier=lid, title=f"Урок: {lesson.title}", depth=3, node_type="page")
                        db.add(node)
                        db.flush()
                        
                        db.add(NavEdge(source_node_id=course_node.id, target_node_id=node.id, relationship_type="navigates_to"))
                        
                        check = db.query(NavNode).filter_by(identifier="ACTION:CHECK_HW").first()
                        hint = db.query(NavNode).filter_by(identifier="ACTION:GET_HINT").first()
                        if check:
                            db.add(NavEdge(source_node_id=node.id, target_node_id=check.id, relationship_type="can_execute"))
                        if hint:
                            db.add(NavEdge(source_node_id=node.id, target_node_id=hint.id, relationship_type="can_execute"))
                            
        # Удаляем лишние уроки, если их больше 5 (не тестовые, просто лишние)
        for i in range(5, len(existing)):
            lesson = existing[i]
            lid = f"/courses/{lesson.course_id}?lesson={lesson.id}"
            node = db.query(NavNode).filter_by(identifier=lid).first()
            if node:
                db.query(NavEdge).filter((NavEdge.source_node_id == node.id) | (NavEdge.target_node_id == node.id)).delete()
                db.delete(node)
            db.delete(lesson)
            
        course.lessons_count = 5
    
    db.commit()
    db.close()
    print("Fixed lessons: exactly 5 realistic lessons per course.")

if __name__ == "__main__":
    main()
