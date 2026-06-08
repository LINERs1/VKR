"""Демо-домашнее задание для проверки ИИ (код + тесты + письменная часть)."""

import logging
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.homework import Homework, HomeworkAssignment, HomeworkStatus
from app.models.user import User, UserRole
from app.services.auth_service import get_password_hash

logger = logging.getLogger(__name__)

DEMO_HW_TITLE = "Калькулятор среднего балла (демо ИИ-проверки)"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "homework" / "demo_grade_average"

# Ответ «ученика» с намеренными ошибками — для теста подсветки
DEMO_STUDENT_CODE = '''def average(grades):
    return sum(grades) / len(grades)


class Student:
    def __init__(self, name, grades):
        self.name = name
        self.grades = grades

    def average_grade(self):
        return sum(self.grades) / len(self.grade)

    def is_passing(self):
        return self.average_grade() >= 5
'''

DEMO_STUDENT_TEXT = """1. Средний балл — это сумма всех оценок, делённая на их количество.

2. Класс Student хранит имя ученика и список оценок в атрибуте grades.

3. Метод is_passing возвращает True, если средний балл больше или равен 4.0 (четвёрке).

4. Пустой список оценок обрабатывается возвратом нуля из функции average.
"""


@lru_cache(maxsize=1)
def _build_description() -> str:
    tests_src = (DATA_DIR / "test_calculator.py").read_text(encoding="utf-8")
    ref_src = (DATA_DIR / "calculator.py").read_text(encoding="utf-8")

    return f"""# Домашнее задание: калькулятор среднего балла

Тема курса **Python для начинающих** (функции и ООП).

---

## Часть 1. Код (обязательно)

Реализуйте в файле `calculator.py`:

1. Функцию `average(grades)` — среднее арифметическое списка чисел.
   - При **пустом** списке — `ValueError` с понятным сообщением.

2. Класс `Student` с полями `name`, `grades` и методами:
   - `average_grade()` — средний балл;
   - `is_passing(threshold=4.0)` — `True`, если средний ≥ порога.

**Шаблон для старта:**

```python
def average(grades):
    # ваш код
    pass

class Student:
    def __init__(self, name, grades):
        pass

    def average_grade(self):
        pass

    def is_passing(self, threshold=4.0):
        pass
```

---

## Часть 2. Автотесты

Скопируйте тесты в `test_calculator.py` и убедитесь, что **`pytest` проходит все тесты**:

```python
{tests_src}
```

Запуск: `pytest test_calculator.py -v`

---

## Часть 3. Письменная часть (обязательно)

Ответьте **своими словами** (5–8 предложений):

1. Как считается средний балл?
2. Зачем нужен класс `Student` в этом задании?
3. Что должен возвращать `is_passing` и при каком пороге?
4. Как обработать пустой список оценок и почему это важно?

---

## Для преподавателя (не показывать ученику)

Эталонное решение лежит в `backend/data/homework/demo_grade_average/calculator.py`.

При проверке через **ИИ Ассистента** (роль преподавателя) попросите: «Проверь код и текст, выдели ошибки красным».
ИИ оборачивает ошибочные фрагменты в:
`<span style='color:#ef4444;font-weight:bold'>...</span>`

---

<details>
<summary>Эталон (только для преподавателя)</summary>

```python
{ref_src}
```
</details>
"""


def _sync_demo_assignments(db: Session, homework: Homework) -> None:
    students = db.query(User).filter(User.role == UserRole.student.value).all()
    existing_ids = {a.student_id for a in homework.assignments}
    for student in students:
        if student.id in existing_ids:
            continue
        db.add(
            HomeworkAssignment(
                homework_id=homework.id,
                student_id=student.id,
                status=HomeworkStatus.pending.value,
            )
        )


def seed_demo_homework(db: Session) -> None:
    for h in db.query(Homework).filter(Homework.title == DEMO_HW_TITLE).all():
        h.is_demo = True
    db.flush()

    teacher = db.query(User).filter(User.role == UserRole.teacher.value).first()
    if not teacher:
        teacher = User(
            username="teacher",
            password_hash=get_password_hash("teacher"),
            role=UserRole.teacher.value,
        )
        db.add(teacher)
        db.flush()
        logger.info("Created demo teacher: teacher / teacher")

    students = db.query(User).filter(User.role == UserRole.student.value).all()
    if not students:
        student = User(
            username="student",
            password_hash=get_password_hash("student"),
            role=UserRole.student.value,
        )
        db.add(student)
        db.flush()
        students = [student]
        logger.info("Created demo student: student / student")

    existing = db.query(Homework).filter(Homework.title == DEMO_HW_TITLE).first()
    if existing:
        existing.is_demo = True
        existing.teacher_id = teacher.id
        _sync_demo_assignments(db, existing)
        db.commit()
        logger.info("Demo homework updated (is_demo, assignments): id=%s", existing.id)
        return

    homework = Homework(
        course_id="python",
        teacher_id=teacher.id,
        title=DEMO_HW_TITLE,
        description=_build_description(),
        is_demo=True,
    )
    db.add(homework)
    db.flush()

    for i, student in enumerate(students):
        assignment = HomeworkAssignment(
            homework_id=homework.id,
            student_id=student.id,
            status=HomeworkStatus.pending.value,
        )
        if i == 0:
            assignment.student_code = DEMO_STUDENT_CODE
            assignment.student_text = DEMO_STUDENT_TEXT
            assignment.status = HomeworkStatus.submitted.value
        db.add(assignment)

    db.commit()
    logger.info("Demo homework created: id=%s, assignments=%s", homework.id, len(students))
