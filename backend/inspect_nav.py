from app.database import engine
from sqlalchemy import inspect
insp = inspect(engine)

for table in ['nav_nodes', 'nav_edges', 'node_access_rules']:
    print(f'\n=== {table} ===')
    for col in insp.get_columns(table):
        nullable = '' if col['nullable'] else ' NOT NULL'
        fk_info = ''
        print(f"  {col['name']} : {col['type']}{nullable}")
    fks = insp.get_foreign_keys(table)
    for fk in fks:
        print(f"  FK: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
