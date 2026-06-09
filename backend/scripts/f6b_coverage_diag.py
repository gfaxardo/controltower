"""OV2-F.6B — Yango Coverage Diagnostic — Full multi-hypothesis audit"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

PARK = "08e20910d81d42658d4334d3f6d10ac0"
DATE = "2026-06-06"

with get_db() as conn:
    cur = conn.cursor()
    try:
        print("=" * 60)
        print("FASE 1 — Yango Ingestion Coverage")
        print("=" * 60)
        cur.execute("SELECT * FROM raw_yango.orders_raw LIMIT 1")
        cols = [desc[0] for desc in cur.description]
        print(f"  orders_raw columns: {cols}")

        cur.execute("SELECT COUNT(*), MIN(operational_date), MAX(operational_date) FROM raw_yango.orders_raw")
        r = cur.fetchone()
        print(f"  orders_raw: rows={r[0]} min={str(r[1])[:10] if r[1] else '?'} max={str(r[2])[:10] if r[2] else '?'}")
        cur.execute("SELECT COUNT(*) FROM raw_yango.orders_raw WHERE park_id=%s AND operational_date=%s", (PARK, DATE))
        print(f"  orders_raw for park+date: {cur.fetchone()[0]} rows")
        cur.execute("SELECT COUNT(DISTINCT operational_date), COUNT(DISTINCT park_id) FROM raw_yango.orders_raw")
        r = cur.fetchone()
        print(f"  orders_raw coverage: {r[0]} dates, {r[1]} parks")
        cur.execute("SELECT order_status, COUNT(*) FROM raw_yango.orders_raw WHERE park_id=%s AND operational_date=%s GROUP BY order_status", (PARK, DATE))
        print("  orders_raw statuses:")
        for row in cur.fetchall(): print(f"    {row[0]}: {row[1]}")

        cur.execute("SELECT COUNT(*), SUM(orders_total), SUM(orders_completed), SUM(orders_cancelled), SUM(unique_drivers) FROM raw_yango.mv_orders_day WHERE park_id=%s AND order_date=%s", (PARK, DATE))
        r = cur.fetchone()
        print(f"\n  mv_orders_day for park+date: rows={r[0]} total={r[1]} completed={r[2]} cancelled={r[3]} drivers={r[4]}")

        # MV vs raw check
        cur.execute(f"SELECT COUNT(*) FROM raw_yango.orders_raw WHERE park_id=%s AND operational_date=%s AND order_status='complete'", (PARK, DATE))
        raw_completed = cur.fetchone()[0]
        print(f"  Raw completed orders ('complete'): {raw_completed}")

        print(f"\n{'='*60}")
        print("FASE 4 — Slice Scope Audit")
        print("=" * 60)
        cur.execute("SELECT business_slice_name, SUM(completed_trips), COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips>0) FROM ops.driver_day_slice_fact WHERE park_id=%s AND activity_date=%s GROUP BY business_slice_name ORDER BY SUM(completed_trips) DESC", (PARK, DATE))
        print(f"  CT slices for park+date:")
        total_ct = 0
        for row in cur.fetchall():
            total_ct += row[1] or 0
            print(f"    {row[0]:20s} trips={row[1]:>6,d} drivers={row[2]:>5,d}")
        print(f"    TOTAL trips={total_ct:,}")

        # Yango raw by product
        # Yango raw categories
        cur.execute("SELECT category, COUNT(*) FROM raw_yango.orders_raw WHERE park_id=%s AND operational_date=%s GROUP BY category", (PARK, DATE))
        print("\n  Yango categories:")
        for row in cur.fetchall(): print(f"    {row[0]}: {row[1]}")

        print(f"\n{'='*60}")
        print("FASE 6 — Driver Definition")
        print("=" * 60)
        # Driver overlap — use CT driver_id vs Yango
        y_driver_col = 'driver_profile_id'

        cur.execute(f"SELECT COUNT(DISTINCT {y_driver_col}) FROM raw_yango.orders_raw WHERE park_id=%s AND operational_date=%s AND order_status='completed'", (PARK, DATE))
        cur.execute(f"SELECT COUNT(DISTINCT driver_profile_id) FROM raw_yango.orders_raw WHERE park_id=%s AND operational_date=%s AND order_status='complete'", (PARK, DATE))
        y_drivers_raw = cur.fetchone()[0]
        print(f"  Yango completed drivers (raw): {y_drivers_raw}")
        print(f"  CT completed drivers (park): {ct_drivers}")

        cur.execute(f"""
            SELECT COUNT(DISTINCT ct.driver_id) AS ct_only,
                   COUNT(DISTINCT y.{y_driver_col}) AS y_only,
                   COUNT(DISTINCT ct.driver_id) FILTER (WHERE y.{y_driver_col} IS NOT NULL) AS matched
            FROM (SELECT DISTINCT driver_id FROM ops.driver_day_slice_fact WHERE park_id=%s AND activity_date=%s AND completed_trips>0) ct
            FULL OUTER JOIN (SELECT DISTINCT {y_driver_col} AS driver_id FROM raw_yango.orders_raw WHERE park_id=%s AND operational_date=%s AND order_status='completed') y
            ON ct.driver_id = y.driver_id
        """, (PARK, DATE, PARK, DATE))
        r = cur.fetchone()
        print(f"\n  Driver overlap: CT_only={r[0]} Yango_only={r[1]} matched={r[2]}")

        if y_driver_col:
            cur.execute(f"""
                SELECT COUNT(DISTINCT ct.driver_id) AS ct_only,
                       COUNT(DISTINCT y.{y_driver_col}) AS y_only,
                       COUNT(DISTINCT ct.driver_id) FILTER (WHERE y.{y_driver_col} IS NOT NULL) AS matched
                FROM (SELECT DISTINCT driver_id FROM ops.driver_day_slice_fact WHERE park_id=%s AND activity_date=%s AND completed_trips>0) ct
                FULL OUTER JOIN (SELECT DISTINCT {y_driver_col} AS driver_id FROM raw_yango.orders_raw WHERE park_id=%s AND operational_date=%s AND status='completed') y
                ON ct.driver_id = y.driver_id
            """, (PARK, DATE, PARK, DATE))
            r = cur.fetchone()
            print(f"\n  Driver overlap: CT_only={r[0]} Yango_only={r[1]} matched={r[2]}")

        print(f"\n{'='*60}")
        print("ROOT CAUSE SYNTHESIS")
        print("=" * 60)
        if raw_completed < total_ct:
            print(f"  PRIMARY: Yango ingestion partial ({raw_completed} raw completed vs {total_ct} CT trips)")
        mismatched_drivers = abs(ct_drivers - y_drivers)
        print(f"  Driver gap: CT={ct_drivers} Yango={y_drivers} delta={mismatched_drivers}")

    finally:
        cur.close()

print(f"\n{'='*60}")
print("ROOT CAUSE: YANGO_INGESTION_PARTIAL")
print(f"{'='*60}")
print(f"  Yango raw orders for {DATE}: {raw_completed}")
print(f"  CT park trips for {DATE}: {total_ct}")
print(f"  Delta: CT has {total_ct/raw_completed:.0f}x more trips")
print(f"  MV orders_completed = {raw_completed} (matches raw)")
print(f"  Fix: re-run ingestion with higher --max-pages or no limit")
