"""Comprueba tipo de ops.mv_real_drill_dim_agg (view vs materialized view) y si SUM(cancelled_trips) funciona."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()
with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Tipo de objeto
    cur.execute("""
        SELECT c.relkind, obj_description(c.oid) AS comment
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'ops' AND c.relname = 'mv_real_drill_dim_agg'
    """)
    r = cur.fetchone()
    kind = {'v': 'view', 'm': 'materialized view'}.get(r['relkind'], r['relkind']) if r else 'not found'
    print("mv_real_drill_dim_agg type:", kind)
    # Query con cancelled_trips
    try:
        cur.execute("""
            SELECT period_grain, period_start, SUM(trips) AS viajes, SUM(cancelled_trips) AS cancelaciones
            FROM ops.mv_real_drill_dim_agg
            WHERE period_start >= CURRENT_DATE - INTERVAL '7 days' AND breakdown = 'lob'
            GROUP BY period_grain, period_start
            LIMIT 3
        """)
        rows = cur.fetchall()
        print("Query SUM(cancelled_trips) FROM mv_real_drill_dim_agg:", "OK" if rows else "empty", len(rows), "rows")
        for row in rows[:2]:
            print(" ", row)
    except Exception as e:
        print("Query SUM(cancelled_trips) FROM mv_real_drill_dim_agg: FAIL", str(e))
    cur.close()
