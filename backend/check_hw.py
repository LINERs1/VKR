import app.models.homework_template
import app.models.homework
from app.database import SessionLocal
from app.models.user import User
from app.models.homework_template import HomeworkTemplate
from app.models.homework import HomeworkAssignment
import json

db = SessionLocal()

# Check existing assignments for student id=1
existing = db.query(HomeworkAssignment).filter(HomeworkAssignment.student_id == 1).all()
print('Existing assignments for st:', len(existing))
for a in existing:
    tmpl = db.query(HomeworkTemplate).filter(HomeworkTemplate.id == a.homework_id).first()
    title = tmpl.title if tmpl else 'unknown'
    print(f'  id={a.id}, hw_id={a.homework_id}, title={title}, status={a.status}')

db.close()
