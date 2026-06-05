from app.models.homework import Homework, HomeworkAssignment
from app.models.homework_template import HomeworkTemplate
from app.models.course import Course, Lesson
from app.models.navigation import NavNode
from app.database import SessionLocal
db = SessionLocal()
nodes = db.query(NavNode).order_by(NavNode.depth).limit(15).all()
for n in nodes:
    print(f'depth={n.depth} | identifier={n.identifier} | title={n.title}')
db.close()
