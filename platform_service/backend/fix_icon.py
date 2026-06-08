import sqlite3
conn = sqlite3.connect(r'c:\Users\liner\Desktop\Diplom\platform_service\backend\app.db')
c = conn.cursor()
c.execute("UPDATE courses SET icon='🐍' WHERE id='python-100-days-ru'")
conn.commit()
conn.close()
