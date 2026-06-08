from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    rows = conn.execute(text("SELECT node_type, identifier FROM nav_nodes WHERE node_type = 'action'")).fetchall()
    print([r for r in rows])
