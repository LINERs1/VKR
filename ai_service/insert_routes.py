from app.database import SessionLocal
from app.models.navigation import NavNode, NodeAccessRule

db = SessionLocal()

node_data = [
    ("/builder/courses", "Конструктор курсов", ["teacher", "admin"])
]

for identifier, title, roles in node_data:
    node = db.query(NavNode).filter(NavNode.identifier == identifier).first()
    if not node:
        node = NavNode(identifier=identifier, title=title, depth=1, node_type="page")
        db.add(node)
        db.commit()
        db.refresh(node)
        for role in roles:
            db.add(NodeAccessRule(nav_node_id=node.id, allowed_role=role))
        db.commit()
        print(f"Added {identifier}")
    else:
        print(f"{identifier} already exists")

print("done")
