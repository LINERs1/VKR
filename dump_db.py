import sqlite3
import json

conn = sqlite3.connect('C:/Users/liner/Desktop/Diplom/ai_service/app.db')
cursor = conn.execute("SELECT title, identifier FROM nav_nodes WHERE node_type='page'")
rows = cursor.fetchall()
with open('db_dump.json', 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)
