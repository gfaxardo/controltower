import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

with get_db() as conn:
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM raw_yango.mv_orders_day LIMIT 1")
        cols = [desc[0] for desc in cur.description]
        print(f"\nYango orders columns: {cols}")

        cur.execute("SELECT MAX(order_date), COUNT(*) FROM raw_yango.mv_orders_day")
        r = cur.fetchone()
        print(f"Yango orders: max={str(r[0])[:10]} rows={r[1]}")

        cur.execute("SELECT MAX(order_date), COUNT(*) FROM raw_yango.mv_revenue_day")
        r = cur.fetchone()
        print(f"Yango revenue: max={str(r[0])[:10]} rows={r[1]}")

        cur.execute("SELECT MAX(snapshot_date), COUNT(*) FROM raw_yango.mv_driver_profiles_snapshot")
        r = cur.fetchone()
        print(f"Yango drivers: max={str(r[0])[:10]} rows={r[1]}")

        # Check orders for Lima main park on specific date
        cur.execute("SELECT order_date, COUNT(*), SUM(COALESCE(orders_count,0)) FROM raw_yango.mv_orders_day WHERE park_id='08e20910d81d42658d4334d3f6d10ac0' AND order_date='2026-06-06' GROUP BY order_date")
        yr = cur.fetchone()
        if yr:
            print(f"\nYango Lima main park (06-06): rows={yr[1]} orders={yr[2]}")
        else:
            # Try without park filter
            cur.execute("SELECT order_date, COUNT(*) FROM raw_yango.mv_orders_day WHERE order_date='2026-06-06' GROUP BY order_date")
            yr2 = cur.fetchone()
            print(f"\nYango all parks (06-06): rows={yr2[1] if yr2 else 0}")

        # CT side for comparison
        cur.execute("SELECT SUM(completed_trips), COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips>0) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima' AND park_id='08e20910d81d42658d4334d3f6d10ac0' AND activity_date='2026-06-06'")
        r = cur.fetchone()
        print(f"\nCT Lima main park (06-06): trips={r[0]} drivers={r[1]}")

        # Yango side for same date + park
        cur.execute("SELECT order_date, total_orders, total_revenue FROM raw_yango.mv_orders_day WHERE park_id='08e20910d81d42658d4334d3f6d10ac0' AND order_date='2026-06-06'")
        yr = cur.fetchone()
        if yr:
            print(f"Yango Lima main park (06-06): orders={yr[1]} revenue={yr[2]}")
        else:
            print("Yango Lima main park (06-06): NO DATA")
    finally:
        cur.close()
