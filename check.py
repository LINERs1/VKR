import sys
sys.path.append('C:/Users/liner/Desktop/Diplom/platform_service/backend')
from app.database import SessionLocal
from app.models.navigation import NavNode

db = SessionLocal()
nodes = db.query(NavNode).all()
print([n.identifier for n in nodes])
