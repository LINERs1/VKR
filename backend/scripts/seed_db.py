import sys
import os
import random
import json
from datetime import datetime, timedelta

# Добавляем корень проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.homework import Homework, HomeworkAssignment, HomeworkStatus
from app.models.assistant_metric import AssistantMetric
import bcrypt

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def seed_data():
    db = SessionLocal()
    try:
        print("Начинаем генерацию тестовых данных...")

        # 1. Создаем преподавателя (если нет)
        teacher = db.query(User).filter(User.username == "teacher").first()
        if not teacher:
            teacher = User(
                username="teacher",
                password_hash=get_password_hash("teacher"),
                role=UserRole.teacher.value,
                email="teacher@eduai.com",
                full_name="Иван Петров (Преподаватель)"
            )
            db.add(teacher)
            db.commit()
            db.refresh(teacher)
        
        # 2. Создаем 10 студентов
        students = []
        for i in range(1, 11):
            username = f"student{i}"
            student = db.query(User).filter(User.username == username).first()
            if not student:
                student = User(
                    username=username,
                    password_hash=get_password_hash("student"),
                    role=UserRole.student.value,
                    email=f"student{i}@eduai.com",
                    full_name=f"Студент {i} Тестовый"
                )
                db.add(student)
                db.commit()
                db.refresh(student)
            students.append(student)
        
        # 3. Создаем тестовые домашние задания (если их нет)
        hw_titles = ["Основы Python", "Циклы и условия", "Функции", "ООП в Python", "Работа с файлами"]
        courses = ["python", "python", "python", "python", "ml"]
        homeworks = []
        
        for i, title in enumerate(hw_titles):
            hw = db.query(Homework).filter(Homework.title == title).first()
            if not hw:
                hw = Homework(
                    course_id=courses[i],
                    teacher_id=teacher.id,
                    title=title,
                    description=f"Практическое задание по теме: {title}",
                    content_json=json.dumps({
                        "intro": "Внимательно прочитайте задание и напишите код.",
                        "code_template": "def solve():\n    pass",
                        "code_filename": "main.py"
                    }),
                    is_demo=False
                )
                db.add(hw)
                db.commit()
                db.refresh(hw)
            homeworks.append(hw)

        # 4. Назначаем домашние задания студентам и проставляем оценки
        # Чтобы графики были красивые, сделаем разные статусы и оценки
        print("Генерация решений и оценок...")
        for hw in homeworks:
            for student in students:
                assignment = db.query(HomeworkAssignment).filter(
                    HomeworkAssignment.homework_id == hw.id,
                    HomeworkAssignment.student_id == student.id
                ).first()
                
                if not assignment:
                    # Случайный статус
                    rand_val = random.random()
                    if rand_val < 0.2:
                        status = HomeworkStatus.pending.value
                        grade = None
                        feedback = None
                    elif rand_val < 0.4:
                        status = HomeworkStatus.submitted.value
                        grade = None
                        feedback = None
                    else:
                        status = HomeworkStatus.graded.value
                        # Оценки с распределением ближе к 4 и 5
                        grade = random.choices([2, 3, 4, 5], weights=[5, 15, 40, 40])[0]
                        feedback = f"Отличная работа! Оценка {grade}." if grade >= 4 else f"Нужно доработать. Оценка {grade}."
                    
                    assignment = HomeworkAssignment(
                        homework_id=hw.id,
                        student_id=student.id,
                        status=status,
                        student_code="def solve():\n    return 'Done'" if status != "pending" else None,
                        grade=grade,
                        teacher_feedback=feedback
                    )
                    db.add(assignment)
                    # Также добавим дату (опционально, если бы в модели была, но в HomeworkAssignment нет поля даты)
        db.commit()

        # 5. Генерация метрик (Analytics) за последние 30 дней
        print("Генерация метрик (Analytics)...")
        # Удаляем старые метрики для чистоты (опционально)
        # db.query(AssistantMetric).delete()
        
        event_types = ["voice_rag", "voice_session", "voice_navigation"]
        now = datetime.utcnow()
        
        for _ in range(300):  # 300 случайных событий
            days_ago = random.randint(0, 29)
            created_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))
            
            e_type = random.choices(event_types, weights=[40, 40, 20])[0]
            student = random.choice(students)
            
            metric = AssistantMetric(
                user_id=student.id,
                event_type=e_type,
                course_id=random.choice(courses),
                duration_ms=random.randint(200, 1500) if e_type != "voice_navigation" else None,
                success=1 if random.random() > 0.1 else 0, # 90% success
                meta_json="{}"
            )
            db.add(metric)
            # SQLAlchemy automatically sets created_at to now on insert by default. 
            # We need to manually set it after flush if the model has a default.
            # In AssistantMetric, created_at has server_default=func.now().
            # To override it, we can insert and then update.
            db.flush()
            metric.created_at = created_at
            
        db.commit()
        
        print("Данные успешно сгенерированы! База готова к защите.")

    except Exception as e:
        print(f"Ошибка: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
