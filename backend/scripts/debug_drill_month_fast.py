"""Solo C, D y granos en real_drill_dim_fact. Sin escanear trips_all."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()
with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    print("--- Granos en real_drill_dim_fact ---")
    cur.execute("""
        SELECT period_grain, COUNT(*) AS cnt, MIN(period_start)::text AS min_ps, MAX(period_start)::text AS max_ps
        FROM ops.real_drill_dim_fact
        GROUP BY period_grain
    """)
    for r in cur.fetchall():
        print(r)
    print("\n--- C. real_drill_dim_fact period_grain=month breakdown=lob ---")
    cur.execute("""
        SELECT period_start::text, country, SUM(trips) AS trips, SUM(cancelled_trips) AS cancelled_trips
        FROM ops.real_drill_dim_fact
        WHERE period_grain = 'month' AND breakdown = 'lob'
          AND period_start >= '2025-11-01' AND period_start < '2026-04-01'
        GROUP BY period_start, country
        ORDER BY country, period_start
    """)
    rows = cur.fetchall()
    print(f"Filas: {len(rows)}")
    for r in rows[:10]:
        print(r)
    print("\n--- D. mv_real_drill_dim_agg period_grain=month breakdown=lob ---")
    cur.execute("""
        SELECT period_start::text, country, SUM(trips) AS trips, SUM(cancelled_trips) AS cancelled_trips
        FROM ops.mv_real_drill_dim_agg
        WHERE period_grain = 'month' AND breakdown = 'lob'
          AND period_start >= '2025-11-01' AND period_start < '2026-04-01'
        GROUP BY period_start, country
        ORDER BY country, period_start
    """)
    rows = cur.fetchall()
    print(f"Filas: {len(rows)}")
    for r in rows[:10]:
        print(r)
    cur.close()
