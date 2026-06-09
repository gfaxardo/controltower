import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

with get_db() as conn:
    cur = conn.cursor()
    try:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ops' AND table_name='driver_day_slice_fact' ORDER BY ordinal_position")
        print("=== BRIDGE COLUMNS ===")
        for r in cur.fetchall(): print(f"  {r[0]}")

        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ops' AND table_name='real_business_slice_day_fact' ORDER BY ordinal_position")
        day_cols = [r[0] for r in cur.fetchall()]
        print(f"\n=== DAY_FACT COLUMNS ({len(day_cols)}) ===")
        for c in day_cols: print(f"  {c}")

        cur.execute("SELECT COUNT(DISTINCT park_id) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima'")
        print(f"\nPark IDs in bridge (Lima): {cur.fetchone()[0]}")

        cur.execute("SELECT DISTINCT fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' LIMIT 10")
        print("\n=== FLEET DATA (day_fact Lima) ===")
        for r in cur.fetchall(): print(f"  fleet={r[0]} sub={r[1]} sub_name={r[2]} parent={r[3]}")

        cur.execute("SELECT COUNT(*), COUNT(DISTINCT fleet_display_name) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
        r = cur.fetchone()
        print(f"\nday_fact Lima rows={r[0]} distinct_fleets={r[1]}")

        cur.execute("SELECT COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips>0) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima' AND business_slice_name='Auto regular' AND activity_date='2026-06-06'")
        print(f"\nDrivers for Auto regular on 06-06: {cur.fetchone()[0]}")

    finally:
        cur.close()
