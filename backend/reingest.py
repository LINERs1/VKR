import sys
from pathlib import Path

backend_dir = Path("c:/Users/liner/Desktop/Diplom/backend")
sys.path.append(str(backend_dir))

from app.database import SessionLocal
from app.models.course import Course
from app.services.rag_service import ingest_documents_from_db
import app.models.user
import app.models.homework
import app.models.assistant_metric
import app.models.chat_message
import app.models.homework_template
import app.models.notification
import app.models.student_weak_topic
import app.models.navigation

def main():
    db = SessionLocal()
    courses = db.query(Course).all()
    for course in courses:
        print(f"Ingesting DB for course {course.id}...")
        try:
            res = ingest_documents_from_db(course, db)
            print(f"Result: {res}")
        except Exception as e:
            print(f"Error: {e}")
    db.close()

if __name__ == "__main__":
    main()
