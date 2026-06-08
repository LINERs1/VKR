import re
from langchain_community.document_loaders import PyPDFLoader
from app.database import SessionLocal
from app.models.user import User
from app.models.course import Course, Lesson
from app.models.homework import Homework
from app.models.course_material import CourseMaterial
from app.models.homework_template import HomeworkTemplate
from app.models.notification import Notification

pdf_path = r'C:\Users\liner\Desktop\Diplom\mr-osnovy-algoritmizatsii-i-programm.pdf'
loader = PyPDFLoader(pdf_path)
pages = loader.load()
text = '\n'.join([page.page_content for page in pages])

# Разделяем текст по заголовку "ПРАКТИЧЕСКАЯ РАБОТА №..."
pattern = re.compile(r'(ПРАКТИЧЕСКАЯ РАБОТА №\s*\d+)')
parts = pattern.split(text)

lessons = []
if len(parts) > 1:
    # parts[0] - это введение/оглавление
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i+1].strip() if i+1 < len(parts) else ""
        
        # Попытаемся извлечь первую строчку после заголовка как подзаголовок
        lines = content.split('\n')
        subtitle = ""
        if len(lines) > 0 and len(lines[0].strip()) > 0:
            subtitle = lines[0].strip()
            
        full_title = f"{title}. {subtitle}" if subtitle else title
        lessons.append({
            "title": full_title[:200],  # обрезка длины заголовка
            "content": f"{title}\n\n{content}"
        })

db = SessionLocal()
course_id = 'python'

if lessons:
    # Удаляем старые тестовые уроки
    db.query(Lesson).filter(Lesson.course_id == course_id).delete()
    db.commit()
    
    # Добавляем новые
    for lesson_data in lessons:
        lesson = Lesson(
            course_id=course_id,
            title=lesson_data["title"],
            duration="2 часа",
            content=lesson_data["content"]
        )
        db.add(lesson)
    db.commit()
    
    # Обновляем счетчик уроков в курсе
    course = db.query(Course).filter(Course.id == course_id).first()
    if course:
        course.lessons_count = len(lessons)
        db.commit()
        
    print(f"Успешно создано {len(lessons)} настоящих уроков из методички.")
else:
    print("Не удалось распарсить практические работы из методички.")

db.close()
