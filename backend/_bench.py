import time
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    t0 = time.time()
    cur.execute("SELECT SUM(trips_completed) FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' AND month='2026-05-01' AND LOWER(TRIM(business_slice_name))='auto regular'")
    print(f"month_fact: {time.time()-t0:.2f}s = {cur.fetchone()}")
    
    t0 = time.time()
    cur.execute("SELECT COUNT(*) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' AND trip_date>='2026-05-01' AND trip_date<'2026-06-01'")
    print(f"day_fact count: {time.time()-t0:.2f}s = {cur.fetchone()}")
    
    t0 = time.time()
    cur.execute("SELECT COUNT(*) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' AND week_start>='2026-05-01' AND week_start<'2026-06-01'")
    print(f"week_fact count: {time.time()-t0:.2f}s = {cur.fetchone()}")
    
    cur.close()
