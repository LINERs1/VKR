import sqlite3
c = sqlite3.connect('app.db')
for row in c.execute("SELECT id, identifier, title FROM nav_nodes WHERE identifier LIKE '/courses/ml?%'").fetchall():
    print(row)
