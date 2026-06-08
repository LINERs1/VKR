from app.database import SessionLocal
from app.models.user import User
from app.models.course import Course, Lesson
from app.models.homework import Homework
from app.models.course_material import CourseMaterial
from app.models.homework_template import HomeworkTemplate
from app.models.notification import Notification

db = SessionLocal()
lessons = db.query(Lesson).filter(Lesson.course_id == "python").all()
for l in lessons:
    print(f"Title: {l.title}")
