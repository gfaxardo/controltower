"""OV2-F.2E — Direct bridge build from trips_2026 (small batches, 1-3 days)
Avoids the heavy resolved view. Joins dim_park + mapping_rules directly.
Usage:
  python -m scripts.build_driver_bridge_direct --date-from 2026-04-01 --date-to 2026-06-06 --batch-days 3 --dry-run
  python -m scripts.build_driver_bridge_direct --date-from 2026-04-01 --date-to 2026-06-06 --batch-days 3 --confirm
"""
import sys, os, argparse
from datetime import date as dt_date, datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

TABLE = "ops.driver_day_slice_fact"
BATCH_DAYS = 3

SQL = """
INSERT INTO ops.driver_day_slice_fact
    (activity_date, country, city, park_id, business_slice_name, driver_id,
     completed_trips, cancelled_trips, total_trips,
     completed_flag, cancel_only_flag, empty_supply_flag,
     first_completed_at, last_completed_at, source_system, refreshed_at)
SELECT
    t.trip_date,
    COALESCE(dp.country, 'peru'),
    COALESCE(dp.city, 'lima'),
    t.park_id,
    COALESCE(s.business_slice_name, 'unmapped') AS business_slice_name,
    t.driver_id,
    COUNT(*) FILTER (WHERE t.completed) AS completed_trips,
    COUNT(*) FILTER (WHERE t.cancelled) AS cancelled_trips,
    COUNT(*) AS total_trips,
    COUNT(*) FILTER (WHERE t.completed) > 0 AS completed_flag,
    COUNT(*) FILTER (WHERE t.completed) = 0 AND COUNT(*) > 0 AS cancel_only_flag,
    COUNT(*) FILTER (WHERE t.completed) = 0 AS empty_supply_flag,
    MIN(t.trip_ts) FILTER (WHERE t.completed),
    MAX(t.trip_ts) FILTER (WHERE t.completed),
    'CT_TRIPS_2026',
    now()
FROM (
    SELECT
        conductor_id AS driver_id,
        park_id,
        fecha_inicio_viaje::date AS trip_date,
        fecha_inicio_viaje AS trip_ts,
        condicion = 'Completado' AS completed,
        condicion = 'Cancelado' AS cancelled
    FROM public.trips_2026
    WHERE fecha_inicio_viaje::date >= %s AND fecha_inicio_viaje::date <= %s
      AND park_id IS NOT NULL AND conductor_id IS NOT NULL
) t
LEFT JOIN dim.dim_park dp ON lower(btrim(dp.park_id::text)) = lower(btrim(t.park_id::text))
LEFT JOIN (
    SELECT DISTINCT park_id, business_slice_name
    FROM ops.business_slice_mapping_rules
    WHERE is_active AND rule_type = 'park_only'
) s ON lower(btrim(s.park_id::text)) = lower(btrim(t.park_id::text))
WHERE s.business_slice_name IS NOT NULL OR t.park_id IS NOT NULL
GROUP BY t.trip_date, dp.country, dp.city, t.park_id, s.business_slice_name, t.driver_id
ON CONFLICT (activity_date, country, city, park_id, business_slice_name, driver_id)
DO UPDATE SET
    completed_trips = EXCLUDED.completed_trips,
    cancelled_trips = EXCLUDED.cancelled_trips,
    total_trips = EXCLUDED.total_trips,
    completed_flag = EXCLUDED.completed_flag,
    cancel_only_flag = EXCLUDED.cancel_only_flag,
    empty_supply_flag = EXCLUDED.empty_supply_flag,
    first_completed_at = EXCLUDED.first_completed_at,
    last_completed_at = EXCLUDED.last_completed_at,
    refreshed_at = now()
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", required=True)
    ap.add_argument("--date-to", required=True)
    ap.add_argument("--batch-days", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.confirm:
        print("Use --dry-run or --confirm"); return 1

    date_from = dt_date.fromisoformat(args.date_from)
    date_to = dt_date.fromisoformat(args.date_to)
    batch_size = args.batch_days

    print(f"OV2-F.2E DIRECT BRIDGE BUILD")
    print(f"  Source: public.trips_2026 + dim_park + mapping_rules")
    print(f"  Range: {date_from} -> {date_to}")
    print(f"  Batch: {batch_size} days")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'CONFIRMED'}")

    with get_db() as conn:
        cur = conn.cursor()
        try:
            current = date_from
            batch_num = 0
            total_rows = 0

            while current <= date_to:
                batch_end = min(current + timedelta(days=batch_size - 1), date_to)
                batch_num += 1

                if args.dry_run:
                    cur.execute("""
                        SELECT COUNT(*) AS trips,
                               COUNT(DISTINCT conductor_id) AS drivers
                        FROM public.trips_2026
                        WHERE fecha_inicio_viaje::date >= %s AND fecha_inicio_viaje::date <= %s
                          AND park_id IS NOT NULL AND conductor_id IS NOT NULL
                    """, (current, batch_end))
                    stats = cur.fetchone()
                    print(f"  Batch {batch_num:2d}: {current}->{batch_end} | trips={stats[0]:,} drivers={stats[1]:,} (DRY-RUN)")
                else:
                    cur.execute(SQL, (current, batch_end))
                    conn.commit()
                    rows = cur.rowcount
                    total_rows += rows
                    print(f"  Batch {batch_num:2d}: {current}->{batch_end} | {rows:,} rows inserted/updated")

                current = batch_end + timedelta(days=1)

            if not args.dry_run:
                cur.execute(f"SELECT COUNT(*) AS rows, COUNT(DISTINCT activity_date) AS days, COUNT(DISTINCT driver_id) AS drivers, SUM(completed_trips) AS trips FROM {TABLE} WHERE country='peru' AND city='lima'")
                s = cur.fetchone()
                print(f"\nBUILD COMPLETE: {s[0]:,} rows, {s[1]} days, {s[2]:,} drivers, {s[3]:,} trips")
            else:
                print(f"\nDRY-RUN COMPLETE. No data written.")
            return 0
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {e}")
            return 1
        finally:
            cur.close()

if __name__ == "__main__":
    raise SystemExit(main())
