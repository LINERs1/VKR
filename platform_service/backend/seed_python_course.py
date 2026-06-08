from app.database import SessionLocal
from app.models.user import User
from app.models.course import Course, Lesson
from app.models.homework import Homework

db = SessionLocal()

course_id = 'python'
course = db.query(Course).filter(Course.id == course_id).first()

if not course:
    print(f"Курс {course_id} не найден. Создаем...")
    course = Course(
        id=course_id,
        title="Основы алгоритмизации и программирования",
        description="Курс на основе загруженной методички. Включает базовые алгоритмы, структуры данных и введение в Python.",
        icon="python",
        color="#3b82f6",
        tags="python, algorithms, basics",
        lessons_count=15,
        duration="40 часов",
        students=1,
        rating=5.0,
        instructor="AI Assistant"
    )
    db.add(course)
    db.commit()
    db.refresh(course)
else:
    print(f"Курс {course_id} уже существует, обновляем...")
    course.title = "Основы алгоритмизации и программирования"
    course.lessons_count = 15
    db.commit()

# Проверяем уроки
existing_lessons = db.query(Lesson).filter(Lesson.course_id == course_id).count()
if existing_lessons < 15:
    print("Добавляем уроки...")
    # Удалим старые если есть
    db.query(Lesson).filter(Lesson.course_id == course_id).delete()
    db.commit()
    
    titles = [
        "Введение в алгоритмизацию",
        "Типы алгоритмов: линейные, разветвляющиеся, циклические",
        "Представление алгоритмов (блок-схемы)",
        "Основы языков программирования (Python)",
        "Переменные и типы данных",
        "Операторы ввода-вывода",
        "Арифметические и логические операции",
        "Условный оператор (if-else)",
        "Циклы с условием (while)",
        "Циклы со счетчиком (for)",
        "Одномерные массивы (списки)",
        "Сортировка массивов",
        "Двумерные массивы (матрицы)",
        "Подпрограммы: функции и процедуры",
        "Работа с файлами"
    ]
    
    for i, title in enumerate(titles):
        lesson = Lesson(
            course_id=course_id,
            title=f"Урок {i+1}. {title}",
            duration="1 ч 30 мин",
            content=f"Здесь будет текстовый контент для урока '{title}'. Основной материал ИИ будет брать из загруженной методички."
        )
        db.add(lesson)
    db.commit()
    print("15 уроков успешно добавлены!")
else:
    print("Уроки уже существуют.")

db.close()
