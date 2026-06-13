"""OV2-F.2D — Build ops.driver_day_slice_fact from resolved view (batch-based, 7-day windows)
Usage:
  python -m scripts.build_driver_day_slice_fact --date-from 2026-04-01 --date-to 2026-06-06 --country peru --city lima --batch-days 7 --dry-run
  python -m scripts.build_driver_day_slice_fact --date-from 2026-04-01 --date-to 2026-06-06 --country peru --city lima --batch-days 7 --confirm
"""
import sys, os, argparse
from datetime import date as dt_date, datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

BATCH_DAYS = 7
TABLE = "ops.driver_day_slice_fact"
SOURCE_VIEW = "ops.v_real_trips_business_slice_resolved"

def build_batch(cur, conn, date_from, date_to, country, city):
    """INSERT one batch into the bridge. Returns row count."""
    cur.execute(f"""
        INSERT INTO {TABLE}
            (activity_date, country, city, park_id, business_slice_name, driver_id,
             completed_trips, cancelled_trips, total_trips,
             completed_flag, cancel_only_flag, empty_supply_flag,
             first_completed_at, last_completed_at, source_system, refreshed_at)
        SELECT
            trip_date::date AS activity_date,
            country, city, park_id, business_slice_name, driver_id,
            COUNT(*) FILTER (WHERE completed_flag) AS completed_trips,
            COUNT(*) FILTER (WHERE cancelled_flag) AS cancelled_trips,
            COUNT(*) AS total_trips,
            COUNT(*) FILTER (WHERE completed_flag) > 0 AS completed_flag,
            COUNT(*) FILTER (WHERE completed_flag) = 0 AND COUNT(*) > 0 AS cancel_only_flag,
            COUNT(*) FILTER (WHERE completed_flag) = 0 AS empty_supply_flag,
            MIN(trip_start) FILTER (WHERE completed_flag) AS first_completed_at,
            MAX(trip_start) FILTER (WHERE completed_flag) AS last_completed_at,
            'CT_TRIPS_2026', now()
        FROM {SOURCE_VIEW}
        WHERE country = %s AND city = %s
          AND trip_date::date >= %s AND trip_date::date <= %s
          AND driver_id IS NOT NULL
          AND business_slice_name IS NOT NULL
        GROUP BY trip_date::date, country, city, park_id, business_slice_name, driver_id
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
    """, (country, city, date_from, date_to))
    conn.commit()
    return cur.rowcount

def main():
    ap = argparse.ArgumentParser(description="Build driver_day_slice_fact from resolved view")
    ap.add_argument("--date-from", required=True)
    ap.add_argument("--date-to", required=True)
    ap.add_argument("--country", default="peru")
    ap.add_argument("--city", default="lima")
    ap.add_argument("--batch-days", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.confirm:
        print("Use --dry-run or --confirm")
        return 1

    date_from = dt_date.fromisoformat(args.date_from)
    date_to = dt_date.fromisoformat(args.date_to)

    print(f"OV2-F.2D BUILD DRIVER DAY SLICE BRIDGE")
    print(f"  Range: {date_from} -> {date_to}")
    print(f"  Batch: {args.batch_days} days")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'CONFIRMED'}")

    with get_db() as conn:
        cur = conn.cursor()
        try:
            current = date_from
            total_rows = 0
            batch_num = 0

            while current <= date_to:
                batch_end = min(current + timedelta(days=args.batch_days - 1), date_to)
                batch_num += 1

                if args.dry_run:
                    cur.execute(f"""
                        SELECT COUNT(*) AS trips,
                               COUNT(DISTINCT driver_id) AS drivers,
                               COUNT(DISTINCT business_slice_name) AS slices
                        FROM {SOURCE_VIEW}
                        WHERE country = %s AND city = %s
                          AND trip_date::date >= %s AND trip_date::date <= %s
                          AND driver_id IS NOT NULL AND business_slice_name IS NOT NULL
                    """, (args.country, args.city, current, batch_end))
                    stats = cur.fetchone()
                    print(f"  Batch {batch_num}: {current}->{batch_end} | trips={stats[0]:,} drivers={stats[1]:,} slices={stats[2]} (DRY-RUN)")
                else:
                    rows = build_batch(cur, conn, current, batch_end, args.country, args.city)
                    total_rows += rows
                    print(f"  Batch {batch_num}: {current}->{batch_end} | {rows} rows inserted")

                current = batch_end + timedelta(days=1)

            if not args.dry_run:
                cur.execute(f"SELECT COUNT(*) AS rows, COUNT(DISTINCT activity_date) AS days, COUNT(DISTINCT driver_id) AS drivers FROM {TABLE} WHERE country=%s AND city=%s", (args.country, args.city))
                stats = cur.fetchone()
                print(f"\nBUILD COMPLETE: {stats[0]:,} rows, {stats[1]} days, {stats[2]:,} drivers")
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
