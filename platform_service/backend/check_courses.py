from app.database import SessionLocal
from app.models.course import Course
from app.models.lesson import Lesson

db = SessionLocal()
courses = db.query(Course).all()
print("Курсы в БД:")
for c in courses:
    print(f" - {c.id}: {c.title} ({c.lessons_count} уроков)")

