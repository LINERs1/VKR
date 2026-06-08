import os
import requests
import zipfile
import io
import re
import sqlite3

DB_PATH = r"c:\Users\liner\Desktop\Diplom\platform_service\backend\app.db"
COURSE_ID = "python-100-days-ru"

def import_python_course():
    print("Скачивание курса BEPb/Python-100-days с GitHub...")
    url = "https://github.com/BEPb/Python-100-days/archive/refs/heads/master.zip"
    resp = requests.get(url)
    if resp.status_code != 200:
        print("Ошибка скачивания")
        return
    
    print("Распаковка и обработка...")
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        # Ищем все файлы readme.md в папках дней
        md_files = [f for f in z.namelist() if f.lower().endswith('readme.md') and ('day' in f.lower() or 'день' in f.lower() or re.search(r'\d+', f))]
        
        # Сортируем по номеру дня из папки
        def get_day(name):
            folder_path = '/'.join(name.split('/')[:-1])
            # Ищем все числа в названии папки (например, "День 01-15/День 01")
            matches = re.findall(r'\d+', folder_path)
            if matches:
                # Последнее число обычно означает номер конкретного дня (например, 01)
                return int(matches[-1])
            return 999
        
        md_files.sort(key=get_day)
        
        # Оставляем только уникальные дни (иногда бывает несколько readme.md в подпапках, берем первый для каждого дня)
        unique_days = []
        seen_days = set()
        for f in md_files:
            d = get_day(f)
            if d != 999 and d not in seen_days:
                seen_days.add(d)
                unique_days.append(f)
                
        # Берем ровно 10 дней
        unique_days = unique_days[:10]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        title = "Python за 100 дней (Первые 10 дней)"
        desc = "Старт легендарного открытого курса BEPb/Python-100-days. Базовый синтаксис, переменные, циклы и функции."
        
        # Очистка
        cursor.execute("DELETE FROM lessons WHERE course_id='python-100-days-ru'")
        cursor.execute("DELETE FROM courses WHERE id='python-100-days-ru'")
        
        cursor.execute(
            "INSERT INTO courses (id, title, description, instructor, duration, icon, tags, lessons_count, students, rating) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (COURSE_ID, title, desc, "GitHub Open Source", "10 Дней", "python", "python, backend", len(unique_days), 5302, 4.9)
        )
        
        print(f"Курс {COURSE_ID} создан.")
        
        for index, f in enumerate(unique_days):
            try:
                content = z.read(f).decode('utf-8')
            except UnicodeDecodeError:
                continue
            
            # Удаляем блоки кода, чтобы случайно не выдернуть Python-комментарий как заголовок
            text_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
            text_no_code = re.sub(r'`.*?`', '', text_no_code)
            
            # Ищем настоящий заголовок
            match = re.search(r'^(?:#{1,3})\s+(.+)$', text_no_code, re.MULTILINE)
            if match and len(match.group(1).strip()) > 3:
                lesson_title = f"День {index+1}. {match.group(1).strip()}"
            else:
                # Берем первую непустую строку
                lines = [l.strip() for l in text_no_code.split('\n') if l.strip()]
                if lines:
                    # Убираем решетки если они слиплись с текстом
                    first_line = lines[0].lstrip('#').strip()
                    lesson_title = f"День {index+1}. {first_line[:50]}"
                else:
                    lesson_title = f"День {index+1}. Основы Python"
            
            cursor.execute(
                "INSERT INTO lessons (course_id, title, content, duration) VALUES (?, ?, ?, ?)",
                (COURSE_ID, lesson_title, content, "45 мин")
            )
            
            safe_title = lesson_title.encode('ascii', 'replace').decode('ascii')
            print(f"Импортирован урок: {safe_title}")
            
        conn.commit()
        conn.close()
        print("Импорт успешно завершен! Проверьте платформу.")

if __name__ == "__main__":
    import_python_course()
