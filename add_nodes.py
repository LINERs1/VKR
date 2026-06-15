import sqlite3
c = sqlite3.connect('c:/Users/liner/Desktop/Diplom/backend/app.db')
c.execute("INSERT INTO nav_nodes (node_type, identifier, title, depth) VALUES ('page', '/deep-4', 'Уровень 4', 4)")
c.execute("INSERT INTO nav_nodes (node_type, identifier, title, depth) VALUES ('page', '/deep-5', 'Уровень 5', 5)")
c.commit()
c.close()
