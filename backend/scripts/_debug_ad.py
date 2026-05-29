import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor
from datetime import date

init_db_pool()

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Method 1: Hardcoded string (worked in previous script)
    cur.execute("SELECT SUM(active_drivers) FROM ops.real_business_slice_month_fact WHERE month = '2026-04-01' AND country = 'peru' AND city = 'lima'")
    r = cur.fetchone()
    print(f"Method 1 (hardcoded str): {r}")

    # Method 2: Parameterized with date object
    cur.execute("SELECT SUM(active_drivers) FROM ops.real_business_slice_month_fact WHERE month = %s AND country = %s AND city = %s",
               (date(2026,4,1), 'peru', 'lima'))
    r = cur.fetchone()
    print(f"Method 2 (date object): {r}")

    # Method 3: Parameterized with string
    cur.execute("SELECT SUM(active_drivers) FROM ops.real_business_slice_month_fact WHERE month = %s AND country = %s AND city = %s",
               ('2026-04-01', 'peru', 'lima'))
    r = cur.fetchone()
    print(f"Method 3 (str param): {r}")

    # Method 4: dict-param style (what the service uses)
    d = date(2026, 4, 1)
    cur.execute("""
        SELECT SUM(active_drivers) AS active_drivers_mtd
        FROM ops.real_business_slice_month_fact
        WHERE month = %(month_start)s
          AND country = 'peru'
          AND city = 'lima'
    """, {"month_start": d})
    r = cur.fetchone()
    print(f"Method 4 (dict, date obj): {r}")

    # Method 5: dict-param with string
    cur.execute("""
        SELECT SUM(active_drivers) AS active_drivers_mtd
        FROM ops.real_business_slice_month_fact
        WHERE month = %(month_start)s
          AND country = 'peru'
          AND city = 'lima'
    """, {"month_start": "2026-04-01"})
    r = cur.fetchone()
    print(f"Method 5 (dict, str param): {r}")
