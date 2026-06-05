import sys
from pathlib import Path

backend_dir = Path("c:/Users/liner/Desktop/Diplom/backend")
sys.path.append(str(backend_dir))

from app.database import SessionLocal
from app.models.navigation import NavNode, NodeAccessRule
from app.models.course import Lesson, Course
import app.models.homework
import app.models.user
import app.models.assistant_metric
import app.models.chat_message
import app.models.homework_template
import app.models.notification
import app.models.student_weak_topic

def main():
    db = SessionLocal()
    
    # Ищем все узлы страниц
    nodes = db.query(NavNode).all()
    for node in nodes:
        # Проверяем, есть ли хотя бы одно правило
        rule = db.query(NodeAccessRule).filter_by(nav_node_id=node.id).first()
        if not rule:
            print(f"Adding rule for {node.identifier}")
            new_rule = NodeAccessRule(nav_node_id=node.id, allowed_role="all")
            db.add(new_rule)
            
    db.commit()
    db.close()
    print("Fixed missing NodeAccessRules.")

if __name__ == "__main__":
    main()
