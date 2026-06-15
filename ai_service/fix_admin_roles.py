import os
import sys
from sqlalchemy.orm import Session

sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.database import engine, SessionLocal
from app.models.navigation import NavNode, NodeAccessRule

def main():
    db = SessionLocal()
    try:
        nodes = db.query(NavNode).filter(NavNode.identifier.like("/admin%")).all()
        for node in nodes:
            rules = db.query(NodeAccessRule).filter(NodeAccessRule.nav_node_id == node.id).all()
            for rule in rules:
                rule.allowed_role = "admin"
        db.commit()
        print("Admin roles updated to 'admin' successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
