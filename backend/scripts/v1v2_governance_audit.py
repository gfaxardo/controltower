"""V1/V2 Governance Closure — Freshness Inventory + Bridge Cert + Runtime Check"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

with get_db() as conn:
    cur = conn.cursor()
    try:
        print("=== FASE 2: FRESHNESS INVENTORY (REAL vs PLAN vs PROJECTION) ===\n")
        layers = [
            ("real_day_fact", "ops.real_business_slice_day_fact", "trip_date", "day", "REAL"),
            ("real_week_fact", "ops.real_business_slice_week_fact", "week_start", "week", "REAL"),
            ("real_month_fact", "ops.real_business_slice_month_fact", "month", "month", "REAL"),
            ("driver_bridge", "ops.driver_day_slice_fact", "activity_date", "day", "BRIDGE"),
            ("snapshot", "ops.omniview_v2_serving_snapshot", "operating_date", "day", "SNAPSHOT"),
        ]
        for name, table, col, grain, kind in layers:
            cur.execute(f"SELECT MAX({col}) FROM {table}")
            mx = cur.fetchone()[0]
            max_str = str(mx)[:10] if mx else "NULL"
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            rows = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} >= CURRENT_DATE - 2")
            recent = cur.fetchone()[0]
            status = "FRESH" if recent > 0 else "STALE"
            print(f"  {name:25s} max={max_str:12s} rows={rows:>8,d} recent={recent:>5,d} [{status}] ({kind}, {grain})")

        print(f"\n=== FASE 3: DRIVER BRIDGE CERTIFICATION ===")
        cur.execute("SELECT MIN(activity_date), MAX(activity_date), COUNT(*), COUNT(DISTINCT driver_id) FROM ops.driver_day_slice_fact")
        r = cur.fetchone()
        print(f"  Range: {str(r[0])[:10]} -> {str(r[1])[:10]}")
        print(f"  Rows: {r[2]:,}  Drivers: {r[3]:,}")

        cur.execute("SELECT COUNT(DISTINCT park_id) FROM ops.driver_day_slice_fact")
        parks = cur.fetchone()[0]
        print(f"  Parks: {parks}")

        cur.execute("SELECT COUNT(*) FROM ops.driver_day_slice_fact WHERE activity_date = CURRENT_DATE - 1")
        print(f"  D-1 rows: {cur.fetchone()[0]:,}")

        # Bridge vs day_fact consistency
        cur.execute("""SELECT SUM(completed_trips) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima'""")
        b_trips = cur.fetchone()[0] or 0
        cur.execute("""SELECT SUM(trips_completed) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'""")
        d_trips = cur.fetchone()[0] or 0
        delta = abs(b_trips - d_trips) / max(d_trips, 1) * 100
        status = "MATCH" if delta < 1 else "DELTA"
        print(f"  Bridge trips={b_trips:,} day_fact trips={d_trips:,} delta={delta:.2f}% [{status}]")

        print(f"\n=== WRITER AUDIT ===")
        writers = {
            "day_fact": "rebuild_day_from_bridge.py (bridge)",
            "week_fact": "rebuild_week_from_day_and_bridge.py (day+bridge)",
            "month_fact": "rebuild_month_from_day_and_bridge.py (day+bridge)",
            "driver_bridge": "build_driver_bridge_direct.py (trips_2026)",
            "snapshot": "refresh_omniview_v2_snapshots.py",
        }
        for tbl, writer in writers.items():
            print(f"  {tbl:25s} -> {writer}")

    finally:
        cur.close()
