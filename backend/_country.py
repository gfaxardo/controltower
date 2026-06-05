from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT DISTINCT country, city FROM ops.real_business_slice_day_fact WHERE trip_date >= '2026-05-01' AND trip_date < '2026-06-01' LIMIT 10")
    print("day_fact distinct country/city:")
    for r in cur.fetchall():
        print(f"  country='{r['country']}' city='{r['city']}'")
    
    cur.execute("SELECT COUNT(*) FROM ops.real_business_slice_day_fact WHERE country = 'peru' AND city = 'lima' AND trip_date >= '2026-05-01' AND trip_date < '2026-06-01'")
    print(f"Exact match: {cur.fetchone()}")
    
    cur.execute("SELECT COUNT(*) FROM ops.real_business_slice_day_fact WHERE country ILIKE '%peru%' AND city ILIKE '%lima%' AND trip_date >= '2026-05-01' AND trip_date < '2026-06-01'")
    print(f"ILIKE match: {cur.fetchone()}")
    
    cur.close()
