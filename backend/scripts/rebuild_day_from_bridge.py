"""OV2-F.4C — Rebuild day_fact from bridge (trips/drivers) + existing day_fact (revenue)
Usage:
  python -m scripts.rebuild_day_from_bridge --date-from 2026-06-01 --date-to 2026-06-07 --dry-run
  python -m scripts.rebuild_day_from_bridge --date-from 2026-06-01 --date-to 2026-06-07 --confirm
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

STAGING = "ops._stg_rebuild_day_v1"
TARGET = "ops.real_business_slice_day_fact"
BRIDGE = "ops.driver_day_slice_fact"

SQL = f"""
DROP TABLE IF EXISTS {STAGING};
CREATE TABLE {STAGING} AS
WITH bridge_agg AS (
    SELECT
        activity_date AS trip_date,
        country, city, business_slice_name, park_id,
        SUM(completed_trips) AS completed_trips,
        SUM(cancelled_trips) AS cancelled_trips,
        COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS active_drivers,
        COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips = 0 AND total_trips > 0) AS empty_supply_drivers,
        COUNT(DISTINCT driver_id) AS total_drivers
    FROM {BRIDGE}
    WHERE country = %s AND city = %s
      AND activity_date >= %s AND activity_date <= %s
    GROUP BY activity_date, country, city, business_slice_name, park_id
),
day_revenue AS (
    SELECT trip_date, business_slice_name,
           SUM(COALESCE(revenue_yego_final, 0)) AS revenue_yego_final,
           SUM(COALESCE(revenue_yego_net, 0)) AS revenue_yego_net
    FROM {TARGET}
    WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s
      AND trip_date >= %s AND trip_date <= %s
    GROUP BY trip_date, business_slice_name
)
SELECT
    b.trip_date, b.country, b.city, b.business_slice_name,
    b.park_id, b.park_id AS fleet_display_name,
    false AS is_subfleet, '' AS subfleet_name, '' AS parent_fleet_name,
    b.completed_trips AS trips_completed,
    b.cancelled_trips AS trips_cancelled,
    b.active_drivers,
    COALESCE(r.revenue_yego_final, 0) AS revenue_yego_final,
    COALESCE(r.revenue_yego_net, 0) AS revenue_yego_net,
    CASE WHEN b.completed_trips > 0
         THEN COALESCE(r.revenue_yego_final, 0) / b.completed_trips END AS avg_ticket,
    CASE WHEN b.active_drivers > 0
         THEN b.completed_trips::numeric / b.active_drivers END AS trips_per_driver,
    CASE WHEN b.completed_trips > 0 AND COALESCE(r.revenue_yego_final, 0) > 0
         THEN COALESCE(r.revenue_yego_net, 0) / COALESCE(r.revenue_yego_final, 0) END AS commission_pct,
    now() AS refreshed_at, now() AS loaded_at
FROM bridge_agg b
LEFT JOIN day_revenue r ON b.trip_date = r.trip_date
    AND b.business_slice_name = r.business_slice_name
ORDER BY b.trip_date, b.business_slice_name
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date-from", required=True)
    ap.add_argument("--date-to", required=True)
    ap.add_argument("--country", default="peru")
    ap.add_argument("--city", default="lima")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.confirm:
        print("Use --dry-run or --confirm"); return 1

    mode = "DRY-RUN" if args.dry_run else "CONFIRMED"
    print(f"OV2-F.4C DAY REBUILD (bridge trips/drivers + day_fact revenue) [{mode}]")

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(SQL, (args.country, args.city, args.date_from, args.date_to,
                               args.country.lower(), args.city.lower(), args.date_from, args.date_to))
            cur.execute(f"SELECT COUNT(*) AS rows, COUNT(DISTINCT trip_date) AS days, SUM(trips_completed) AS trips, SUM(active_drivers)::int AS drivers, SUM(revenue_yego_final) AS revenue FROM {STAGING}")
            s = dict(cur.fetchone())
            print(f"  Staging: {s['rows']} rows, {s['days']} days, {s['trips']:,} trips, {s['drivers']:,} drivers, {s['revenue']:,.0f} revenue")

            if args.dry_run:
                print(f"DRY-RUN PASS")
                cur.execute(f"DROP TABLE IF EXISTS {STAGING}")
                return 0

            staging_rows = s["rows"]
            if staging_rows == 0:
                print(f"  ABORT — staging is empty, no delete/insert performed")
                cur.execute(f"DROP TABLE IF EXISTS {STAGING}")
                return 0

            cur.execute(f"DELETE FROM {TARGET} WHERE trip_date >= %s AND trip_date <= %s", (args.date_from, args.date_to))
            deleted = cur.rowcount
            cur.execute(f"INSERT INTO {TARGET} (trip_date, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name, trips_completed, trips_cancelled, active_drivers, revenue_yego_final, revenue_yego_net, avg_ticket, trips_per_driver, refreshed_at, loaded_at) SELECT trip_date, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name, trips_completed, trips_cancelled, active_drivers, revenue_yego_final, revenue_yego_net, avg_ticket, trips_per_driver, refreshed_at, loaded_at FROM {STAGING}")
            inserted = cur.rowcount
            conn.commit()
            cur.execute(f"DROP TABLE IF EXISTS {STAGING}")
            conn.commit()
            print(f"  Deleted {deleted}, Inserted {inserted}")
            print(f"  COMPLETE — day_fact now from bridge (trips/drivers)")
            return 0
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {e}"); return 1
        finally:
            cur.close()

if __name__ == "__main__":
    raise SystemExit(main())
