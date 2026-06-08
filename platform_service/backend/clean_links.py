import sqlite3
import re

c = sqlite3.connect(r'c:\Users\liner\Desktop\Diplom\platform_service\backend\app.db')
r = c.execute("SELECT id, content FROM lessons WHERE course_id='python-100-days-ru'").fetchall()

for row in r:
    lesson_id = row[0]
    content = row[1]
    
    # Регулярка для удаления навигационных ссылок GitHub
    # Ищем строки, содержащие ссылки вроде [Вернуться...](...) или [Назад](...)
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        lower_line = line.lower()
        if re.search(r'\[.*?\]\(.*?\)', line) and ('вернуться' in lower_line or 'назад' in lower_line or 'главную' in lower_line or 'next' in lower_line or 'previous' in lower_line or 'вперед' in lower_line or 'далее' in lower_line or 'day ' in lower_line):
            # Skip this line (it's a navigation link)
            continue
        new_lines.append(line)
        
    new_content = '\n'.join(new_lines)
    
    # Если в конце есть мусорные пустые строки, почистим
    new_content = new_content.strip()
    
    c.execute("UPDATE lessons SET content=? WHERE id=?", (new_content, lesson_id))

c.commit()
print("Ссылки успешно удалены из всех лекций.")
c.close()
