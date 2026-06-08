import sqlite3
import requests

AI_SERVICE_URL = "http://localhost:8000"
DB_PATH = r"c:\Users\liner\Desktop\Diplom\platform_service\backend\app.db"

def sync_course_to_ai():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Sync course
    course = c.execute("SELECT id, title FROM courses WHERE id='python-100-days-ru'").fetchone()
    if course:
        print(f"Syncing course {course[0]}...")
        requests.post(f"{AI_SERVICE_URL}/webhook/course", json={
            "id": course[0],
            "title": course[1]
        })
        
    # 2. Sync lessons
    lessons = c.execute("SELECT id, course_id, title, content FROM lessons WHERE course_id='python-100-days-ru'").fetchall()
    for l in lessons:
        print(f"Syncing lesson {l[0]} ({l[2]})...")
        requests.post(f"{AI_SERVICE_URL}/webhook/lesson", json={
            "id": l[0],
            "course_id": l[1],
            "title": l[2],
            "content": l[3]
        })
        
    conn.close()
    print("Done syncing to AI service!")

if __name__ == '__main__':
    sync_course_to_ai()
