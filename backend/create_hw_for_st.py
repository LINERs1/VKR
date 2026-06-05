"""
Creates a proper Python homework assignment for student 'st' using the Homework + HomeworkAssignment models.
Topic: Lists and loops in Python.
"""
import sys
sys.path.insert(0, '.')

# Import all models to resolve relationships
from app.models.course import Course
from app.models.user import User
from app.models.homework import Homework, HomeworkAssignment
from app.database import SessionLocal
import json

db = SessionLocal()

# Find student and teacher
student = db.query(User).filter(User.username == 'st').first()
teacher = db.query(User).filter(User.role == 'teacher').first()
print(f'Student: id={student.id} username={student.username}')
print(f'Teacher: id={teacher.id} username={teacher.username}')

# Build homework content JSON (used by AI for hints/review)
content = {
    "intro": (
        "В этом задании ты будешь работать со списками и циклами в Python.\n\n"
        "Задача:\n"
        "1. Напиши функцию get_even_numbers(numbers), которая принимает список чисел и возвращает "
        "новый список, содержащий только чётные числа.\n"
        "2. Напиши функцию calculate_average(numbers), которая принимает список чисел и возвращает "
        "их среднее арифметическое. Если список пустой — вернуть 0.\n"
        "3. Напиши функцию reverse_words(sentence), которая принимает строку-предложение и возвращает "
        "строку, где слова идут в обратном порядке.\n\n"
        "Критерии оценки:\n"
        "- Код работает корректно для всех тестовых случаев — 3 балла\n"
        "- Используются списковые включения (list comprehension) — +1 балл\n"
        "- Код читаем, есть комментарии — +1 балл"
    ),
    "code_filename": "solution.py",
    "code_template": (
        "def get_even_numbers(numbers):\n"
        "    \"\"\"\n"
        "    Возвращает список только чётных чисел из входного списка.\n"
        "    Примеры:\n"
        "    >>> get_even_numbers([1, 2, 3, 4, 5, 6])  ->  [2, 4, 6]\n"
        "    >>> get_even_numbers([1, 3, 5])  ->  []\n"
        "    \"\"\"\n"
        "    # TODO: реализуй функцию\n"
        "    pass\n"
        "\n\n"
        "def calculate_average(numbers):\n"
        "    \"\"\"\n"
        "    Возвращает среднее арифметическое списка чисел.\n"
        "    Если список пустой — возвращает 0.\n"
        "    Примеры:\n"
        "    >>> calculate_average([1, 2, 3, 4, 5])  ->  3.0\n"
        "    >>> calculate_average([])  ->  0\n"
        "    \"\"\"\n"
        "    # TODO: реализуй функцию\n"
        "    pass\n"
        "\n\n"
        "def reverse_words(sentence):\n"
        "    \"\"\"\n"
        "    Возвращает строку с словами в обратном порядке.\n"
        "    Примеры:\n"
        "    >>> reverse_words('Привет мир Python')  ->  'Python мир Привет'\n"
        "    \"\"\"\n"
        "    # TODO: реализуй функцию\n"
        "    pass\n"
    ),
    "quiz_items": [
        {
            "question": "Какой метод используется для добавления элемента в конец списка?",
            "options": [".add()", ".append()", ".insert()", ".push()"],
            "correct_index": 1,
            "topic": "списки",
            "lesson_id": None
        },
        {
            "question": "Что вернёт выражение [x*2 for x in range(3)]?",
            "options": ["[1, 2, 3]", "[0, 2, 4]", "[2, 4, 6]", "[0, 1, 2]"],
            "correct_index": 1,
            "topic": "списковые включения",
            "lesson_id": None
        },
        {
            "question": "Как получить длину списка lst?",
            "options": ["lst.length()", "length(lst)", "len(lst)", "lst.size()"],
            "correct_index": 2,
            "topic": "списки",
            "lesson_id": None
        }
    ],
    "written_part": (
        "Ответь на следующие вопросы своими словами (2-4 предложения на каждый):\n\n"
        "1. Что такое список (list) в Python? Чем он отличается от кортежа (tuple)?\n\n"
        "2. Объясни, что такое списковое включение (list comprehension) и приведи пример его использования.\n\n"
        "3. Когда лучше использовать цикл for, а когда while? Приведи пример каждого."
    ),
    "reference_code": (
        "def get_even_numbers(numbers):\n"
        "    return [x for x in numbers if x % 2 == 0]\n"
        "\n"
        "def calculate_average(numbers):\n"
        "    if not numbers:\n"
        "        return 0\n"
        "    return sum(numbers) / len(numbers)\n"
        "\n"
        "def reverse_words(sentence):\n"
        "    return ' '.join(sentence.split()[::-1])\n"
    )
}

description = (
    "Практическое задание по работе со списками и циклами. "
    "Нужно реализовать три функции: фильтрацию чётных чисел, "
    "вычисление среднего и разворот слов в строке."
)

# Create Homework
hw = Homework(
    course_id='python',
    teacher_id=teacher.id,
    title='Списки и циклы в Python',
    description=description,
    content_json=json.dumps(content, ensure_ascii=False),
    is_demo=False,
)
db.add(hw)
db.flush()
print(f'Created Homework id={hw.id}')

# Create assignment for student st
assignment = HomeworkAssignment(
    homework_id=hw.id,
    student_id=student.id,
    status='active',
    student_code=None,
    student_text=None,
    student_quiz_json=None,
    grade=None,
    ai_review_json=None,
    teacher_feedback=None,
)
db.add(assignment)
db.commit()
print(f'Created HomeworkAssignment id={assignment.id} for student {student.username}')
print('Done! Navigate to /homeworks to see the assignment.')
db.close()
