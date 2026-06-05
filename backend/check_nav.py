import sys
from pathlib import Path

backend_dir = Path("c:/Users/liner/Desktop/Diplom/backend")
sys.path.append(str(backend_dir))

from app.database import SessionLocal
from app.models.navigation import NavNode
import app.models.user

db = SessionLocal()
nodes = db.query(NavNode).filter(NavNode.identifier.like("/courses/ml?%")).all()
for n in nodes:
    print(n.id, n.identifier, n.title)
db.close()
