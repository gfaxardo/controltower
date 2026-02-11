import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
init_db_pool()
with get_db() as conn:
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='yego_integral' AND table_name='parks'
        ORDER BY 1
    """)
    rows = cur.fetchall()
    print("column_name       | data_type")
    print("------------------+-------------------")
    for r in rows:
        print(f"{r[0]:17} | {r[1]}")
    if not rows:
        print("(ninguna fila)")
