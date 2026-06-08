import sqlite3
import re

c = sqlite3.connect(r'c:\Users\liner\Desktop\Diplom\platform_service\backend\app.db')
r = c.execute("SELECT content FROM lessons WHERE course_id='python-100-days-ru' LIMIT 5").fetchall()

for row in r:
    content = row[0]
    
    # Remove code blocks
    text_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    text_no_code = re.sub(r'`.*?`', '', text_no_code)
    
    # Try finding markdown headers H1-H3
    match = re.search(r'^(?:#{1,3})\s+(.+)$', text_no_code, re.MULTILINE)
    if match:
        print("HEADER FOUND:", match.group(1).strip())
    else:
        # Just grab the first non-empty line
        lines = [l.strip() for l in text_no_code.split('\n') if l.strip()]
        if lines:
            print("FIRST LINE:", lines[0][:50])

c.close()
