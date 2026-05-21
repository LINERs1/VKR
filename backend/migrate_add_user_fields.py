"""Миграция: добавляет колонки email и full_name в таблицу users."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        # Получаем существующие колонки
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        print(f"Existing columns: {cols}")

        if "email" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN email TEXT"))
            print("+ Added column: email")
        else:
            print("- email already exists")

        if "full_name" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN full_name TEXT"))
            print("+ Added column: full_name")
        else:
            print("- full_name already exists")

        conn.commit()
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
