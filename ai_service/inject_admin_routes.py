import os
import sys
from sqlalchemy.orm import Session

# Add the app directory to sys.path so we can import from app
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.database import engine, SessionLocal
from app.models.navigation import NavNode, NavEdge, NodeAccessRule

def main():
    db = SessionLocal()
    try:
        # Check if /admin exists
        if db.query(NavNode).filter(NavNode.identifier == "/admin").first():
            print("/admin already exists.")
            return

        routes = [
            {"path": "/admin", "title": "Админ-панель (Общая)", "depth": 1, "desc": "Главная страница панели управления."},
            {"path": "/admin?tab=courses", "title": "Админ-панель: Курсы", "depth": 2, "desc": "Управление курсами в админке."},
            {"path": "/admin?tab=materials", "title": "Админ-панель: Методички", "depth": 2, "desc": "Управление методическими материалами в админке."},
            {"path": "/admin?tab=ai_routes", "title": "Админ-панель: ИИ Маршруты", "depth": 2, "desc": "Управление путями графа навигации для искусственного интеллекта."}
        ]

        home = db.query(NavNode).filter(NavNode.identifier == "/").first()
        admin_node = None

        for r in routes:
            node = NavNode(
                identifier=r["path"],
                title=r["title"],
                description=r["desc"],
                depth=r["depth"],
                node_type="page"
            )
            db.add(node)
            db.flush()
            db.add(NodeAccessRule(nav_node_id=node.id, allowed_role="teacher"))
            db.flush()

            if r["path"] == "/admin":
                admin_node = node
                if home:
                    db.add(NavEdge(source_node_id=home.id, target_node_id=node.id))
                    db.add(NavEdge(source_node_id=node.id, target_node_id=home.id))
            else:
                db.add(NavEdge(source_node_id=admin_node.id, target_node_id=node.id))

        db.commit()
        print("Admin routes added successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
