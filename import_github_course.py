import os
import requests
import zipfile
import io
import re
import sqlite3

DB_PATH = r"c:\Users\liner\Desktop\Diplom\backend\app.db"
AI_SERVICE_URL = "http://localhost:8000"

def import_python_course():
    print("Скачивание курса 30 Days of Python с GitHub...")
    url = "https://github.com/Asabeneh/30-Days-Of-Python/archive/refs/heads/master.zip"
    resp = requests.get(url)
    if resp.status_code != 200:
        print("Ошибка скачивания")
        return
    
    print("Распаковка и обработка...")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        # Ищем все .md файлы в папках дней
        day_files = [f for f in z.namelist() if re.search(r'\d+_Day_.*\.md$', f, re.IGNORECASE) and 'readme' not in f.lower()]
        
        # Сортируем по номеру дня
        def get_day(name):
            m = re.search(r'(\d+)_Day_', name)
            return int(m.group(1)) if m else 999
        
        day_files.sort(key=get_day)
        
        # Возьмем первые 15 дней для скорости
        day_files = day_files[:15] 
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        course_id = "python-30-days"
        title = "Python с нуля (Open-Source Курс)"
        desc = "Адаптация популярного курса '30 Days of Python'. Идеально для старта."
        
        cursor.execute("DELETE FROM lessons WHERE course_id=?", (course_id,))
        cursor.execute("DELETE FROM courses WHERE id=?", (course_id,))
        
        cursor.execute(
            "INSERT INTO courses (id, title, description, instructor, duration, icon, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (course_id, title, desc, "Asabeneh (GitHub)", "15 Уроков", "python", "python, backend")
        )
        
        try:
            requests.post(f"{AI_SERVICE_URL}/webhook/course", json={"id": course_id, "title": title}, timeout=5)
        except Exception as e:
            print("Webhook course error:", e)

        print(f"Курс {course_id} создан.")
        
        for index, f in enumerate(day_files):
            content = z.read(f).decode('utf-8')
            
            # Попробуем вытащить H1
            match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            lesson_title = match.group(1).strip() if match else f"Урок {index+1}"
            
            cursor.execute(
                "INSERT INTO lessons (course_id, title, content, duration) VALUES (?, ?, ?, ?)",
                (course_id, lesson_title, content, "20 мин")
            )
            lesson_id = cursor.lastrowid
            
            # Отправляем вебхук в ИИ сервис для загрузки в ChromaDB
            try:
                requests.post(f"{AI_SERVICE_URL}/webhook/lesson", json={
                    "id": lesson_id,
                    "course_id": course_id,
                    "title": lesson_title,
                    "content": content
                }, timeout=5)
            except Exception as e:
                pass
            
            print(f"Imported lesson: {lesson_title.encode('ascii', 'replace').decode('ascii')}")
            
        conn.commit()
        conn.close()
        print("Import completed! Check the admin panel.")

if __name__ == "__main__":
    import_python_course()
