import sys,os,json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

with get_db() as conn:
    cur = conn.cursor()
    try:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ops' AND table_name='driver_day_slice_fact' AND column_name ILIKE '%rev%'")
        print(f"Revenue cols in bridge: {[r[0] for r in cur.fetchall()] or 'NONE'}")

        cur.execute("SELECT SUM(completed_trips), COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips>0) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima' AND activity_date='2026-06-06' AND business_slice_name='Auto regular'")
        r = cur.fetchone()
        print(f"Bridge day trips={r[0]} drivers={r[1]}")
    finally:
        cur.close()
