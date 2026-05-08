"""Perf split: week_fact fetch vs aggregate (P3 diagnostic)."""
import time
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db, init_db_pool
from app.services import business_slice_service as bs

init_db_pool()
with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    w = [
        "country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))",
        "week_start >= date_trunc('week', CURRENT_DATE)::date - interval '35 days'",
    ]
    p = ["peru"]
    where_sql = "WHERE " + " AND ".join(w)
    sql = f"""
        SELECT week_start, country, city, business_slice_name, fleet_display_name,
               is_subfleet, subfleet_name,
               trips_completed, trips_cancelled, active_drivers,
               avg_ticket, revenue_yego_net, commission_pct, trips_per_driver, cancel_rate_pct
        FROM ops.real_business_slice_week_fact
        {where_sql}
        ORDER BY week_start ASC
        LIMIT %s
    """
    t0 = time.perf_counter()
    cur.execute(sql, p + [1500])
    raw = cur.fetchall()
    t_fetch = time.perf_counter() - t0
    t0 = time.perf_counter()
    ser = [bs._serialize_row(dict(r)) for r in raw]
    bs.aggregate_business_slice_rows(ser, extra_key_fields=bs._canonical_group_fields("week_start"))
    t_agg = time.perf_counter() - t0
    print(f"fetch {len(raw)} rows: {t_fetch * 1000:.1f} ms")
    print(f"serialize+aggregate: {t_agg * 1000:.1f} ms")
    cur.close()

    t0 = time.perf_counter()
    ser2 = [bs._serialize_row(dict(r)) for r in raw]
    bs.aggregate_business_slice_rows(ser2, extra_key_fields=bs._canonical_group_fields("week_start"))
    print(f"serialize+aggregate 2nd pass: {(time.perf_counter() - t0) * 1000:.1f} ms")

