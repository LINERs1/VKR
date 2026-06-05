import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path("c:/Users/liner/Desktop/Diplom/backend")
sys.path.append(str(backend_dir))

from app.database import SessionLocal
from app.models.course import Course, Lesson
from app.models.navigation import NavNode, NavEdge
import app.models.user
import app.models.homework
import app.models.assistant_metric
import app.models.chat_message
import app.models.homework_template
import app.models.notification
import app.models.student_weak_topic

def main():
    db = SessionLocal()
    courses = db.query(Course).all()
    
    for course in courses:
        current_count = db.query(Lesson).filter(Lesson.course_id == course.id).count()
        print(f"Course {course.id} has {current_count} lessons.")
        
        # Add lessons up to 18
        new_lessons = []
        for i in range(current_count + 1, 19):
            lesson = Lesson(
                course_id=course.id,
                title=f"Тестовый урок {i}",
                duration="45 мин",
                content=f"**Это автоматически сгенерированный урок {i}** для проверки функций скролла и ИИ-навигации.\n\n" + 
                        ("Много текста для создания длинной страницы, чтобы мы могли протестировать скроллинг вниз. " * 100) + 
                        "\n\n### Подзаголовок\n\n" +
                        ("Здесь еще больше текста, который нужно скроллить, чтобы найти нужный фрагмент. " * 100)
            )
            db.add(lesson)
            new_lessons.append(lesson)
            
        db.commit()
        
        # Now add them to NavNode and NavEdge
        cid = f"/courses/{course.id}"
        course_node = db.query(NavNode).filter(NavNode.identifier == cid).first()
        
        if course_node:
            for l in new_lessons:
                lid = f"/courses/{course.id}?lesson={l.id}"
                node = NavNode(identifier=lid, title=f"Урок: {l.title}", depth=3, node_type="page")
                db.add(node)
                db.flush()
                
                db.add(NavEdge(
                    source_node_id=course_node.id,
                    target_node_id=node.id,
                    relationship_type="navigates_to"
                ))
                
                # Check HW / Get Hint edges
                check_node = db.query(NavNode).filter(NavNode.identifier == "ACTION:CHECK_HW").first()
                hint_node = db.query(NavNode).filter(NavNode.identifier == "ACTION:GET_HINT").first()
                
                if check_node:
                    db.add(NavEdge(source_node_id=node.id, target_node_id=check_node.id, relationship_type="can_execute"))
                if hint_node:
                    db.add(NavEdge(source_node_id=node.id, target_node_id=hint_node.id, relationship_type="can_execute"))
                    
        db.commit()
        print(f"Added {len(new_lessons)} lessons for {course.id}")
        
    db.close()

if __name__ == "__main__":
    main()
