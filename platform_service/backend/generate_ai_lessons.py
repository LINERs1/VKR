import re
import requests
import json
from langchain_community.document_loaders import PyPDFLoader
from app.database import SessionLocal
from app.models.user import User
from app.models.course import Course, Lesson
from app.models.homework import Homework
from app.models.course_material import CourseMaterial
from app.models.homework_template import HomeworkTemplate
from app.models.notification import Notification

pdf_path = r'C:\Users\liner\Desktop\Diplom\mr-osnovy-algoritmizatsii-i-programm.pdf'

def chat_with_ollama(prompt):
    url = "http://localhost:11434/api/generate"
    data = {
        "model": "qwen2.5",
        "prompt": prompt,
        "stream": False
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json().get("response", "")
    return "Error generating content."

def generate_lessons():
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    # Skip the first 3 pages (TOC)
    text = '\n'.join([page.page_content for page in pages[3:]])

    pattern = re.compile(r'(ПРАКТИЧЕСКАЯ РАБОТА №\s*\d+)')
    parts = pattern.split(text)

    lessons_to_generate = []
    
    count = 0
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            if count >= 3:
                break
            title = parts[i].strip()
            content = parts[i+1].strip() if i+1 < len(parts) else ""
            
            lines = content.split('\n')
            subtitle = ""
            if len(lines) > 0 and len(lines[0].strip()) > 0:
                subtitle = lines[0].strip()
            
            full_title = f"{title}. {subtitle}" if subtitle else title
            lessons_to_generate.append({
                "title": full_title[:200],
                "raw_content": content[:1500] 
            })
            count += 1

    db = SessionLocal()
    course_id = 'python'

    if lessons_to_generate:
        print("Starting AI generation for 3 lessons...")
        db.query(Lesson).filter(Lesson.course_id == course_id).delete()
        db.commit()
        
        for lesson_data in lessons_to_generate:
            print(f"Generating: {lesson_data['title']}...")
            prompt = f"Ты - профессиональный ИТ-преподаватель. Напиши красивый, понятный и подробный образовательный урок (в формате Markdown) на основе следующего сухого методического материала. Включи приветствие, теоретическую часть с объяснениями, выдели важные термины жирным, и добавь примеры с комментариями.\n\nТема: {lesson_data['title']}\n\nМатериал: {lesson_data['raw_content']}"
            
            ai_content = chat_with_ollama(prompt)
            
            lesson = Lesson(
                course_id=course_id,
                title=lesson_data["title"],
                duration="2 часа",
                content=ai_content
            )
            db.add(lesson)
            db.commit()
            print(f"Done: {lesson_data['title']}")
        
        course = db.query(Course).filter(Course.id == course_id).first()
        if course:
            course.lessons_count = 3
            db.commit()
            
        print("Успешно создано 3 AI-урока.")
    else:
        print("Не удалось распарсить.")

    db.close()

if __name__ == "__main__":
    generate_lessons()
