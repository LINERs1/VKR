import sqlite3, re
c = sqlite3.connect(r'c:\Users\liner\Desktop\Diplom\platform_service\backend\app.db')
r = c.execute("SELECT content FROM lessons WHERE course_id='python-100-days-ru'").fetchall()
for row in r:
    images = re.findall(r'<img\s+[^>]*src=[\'"]([^\'"]+)[\'"]', row[0], re.IGNORECASE)
    if images:
        print("HTML Images:", images[:3])
c.close()
