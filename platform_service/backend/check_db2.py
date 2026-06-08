from app.database import SessionLocal
from app.models.course import Lesson

db = SessionLocal()
lessons = db.query(Lesson).filter(Lesson.course_id == "python").all()
for l in lessons:
    print(f"Title: {l.title}")
