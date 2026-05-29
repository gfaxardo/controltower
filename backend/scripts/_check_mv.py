import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
init_db_pool()
with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SELECT schemaname, matviewname FROM pg_matviews WHERE matviewname LIKE '%yango_loyalty%'")
    print("pg_matviews:", cur.fetchall())
    cur.execute("SELECT COUNT(*) FROM ops.mv_yango_loyalty_performance_monthly_v1")
    print("MV row count:", cur.fetchone()[0])
    cur.execute("SELECT city_norm, active_drivers_mtd, supply_hours_mtd FROM ops.mv_yango_loyalty_performance_monthly_v1 WHERE country='peru' AND month_start='2026-04-01' ORDER BY active_drivers_mtd DESC LIMIT 5")
    print("April 2026 data:")
    for r in cur.fetchall():
        print(f"  {r}")
