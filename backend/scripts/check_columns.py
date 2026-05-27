import sys; sys.path.insert(0, '.')
from app.db.connection import get_db
with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='ops' AND table_name='driver_daily_activity_fact' ORDER BY ordinal_position")
    for r in cur.fetchall():
        print(f"{r[0]:<30} {r[1]}")
