"""OV2-F.2D — Rebuild week_fact from day_fact (trips/revenue) + driver bridge (exact active_drivers)
Usage:
  python -m scripts.rebuild_week_from_day_and_bridge --date-from 2026-04-01 --date-to 2026-06-06 --country peru --city lima --dry-run
  python -m scripts.rebuild_week_from_day_and_bridge --date-from 2026-04-01 --date-to 2026-06-06 --country peru --city lima --confirm
"""
import sys, os, argparse
from datetime import date as dt_date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

STAGING = "ops._stg_rebuild_week_v2"
TARGET = "ops.real_business_slice_week_fact"
DAY = "ops.real_business_slice_day_fact"
BRIDGE = "ops.driver_day_slice_fact"

SQL_BUILD = f"""
DROP TABLE IF EXISTS {STAGING};
CREATE TABLE {STAGING} AS
WITH day_agg AS (
    SELECT
        date_trunc('week', trip_date)::date AS week_start,
        (date_trunc('week', trip_date)::date + interval '6 days')::date AS week_end,
        TRIM(country) AS country, TRIM(city) AS city,
        business_slice_name,
        COALESCE(fleet_display_name, '') AS fleet_display_name,
        COALESCE(is_subfleet, false) AS is_subfleet,
        COALESCE(subfleet_name, '') AS subfleet_name,
        COALESCE(parent_fleet_name, '') AS parent_fleet_name,
        SUM(COALESCE(trips_completed, 0)) AS trips_completed,
        SUM(COALESCE(trips_cancelled, 0)) AS trips_cancelled,
        SUM(COALESCE(revenue_yego_final, 0)) AS revenue_yego_final,
        SUM(COALESCE(revenue_yego_net, 0)) AS revenue_yego_net
    FROM {DAY}
    WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s
      AND trip_date >= %s AND trip_date <= %s
    GROUP BY week_start, week_end, TRIM(country), TRIM(city), business_slice_name,
             fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name
),
driver_agg AS (
    SELECT
        date_trunc('week', activity_date)::date AS week_start,
        country, city, business_slice_name,
        COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS active_drivers,
        COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips = 0 AND total_trips > 0) AS empty_supply_drivers,
        COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0 OR total_trips > 0) AS total_drivers
    FROM {BRIDGE}
    WHERE country = %s AND city = %s
      AND activity_date >= %s AND activity_date <= %s
    GROUP BY week_start, country, city, business_slice_name
)
SELECT
    d.week_start, d.week_end, d.country, d.city, d.business_slice_name,
    d.fleet_display_name, d.is_subfleet, d.subfleet_name, d.parent_fleet_name,
    d.trips_completed, d.trips_cancelled,
    COALESCE(b.active_drivers, 0) AS active_drivers,
    CASE WHEN d.trips_completed > 0
         THEN d.revenue_yego_final / d.trips_completed END AS avg_ticket,
    CASE WHEN COALESCE(b.active_drivers, 0) > 0
         THEN d.trips_completed::numeric / b.active_drivers END AS trips_per_driver,
    d.revenue_yego_final, d.revenue_yego_net,
    CASE WHEN d.trips_completed > 0 AND d.revenue_yego_final > 0
         THEN d.revenue_yego_net / NULLIF(d.revenue_yego_final, 0) END AS commission_pct,
    COALESCE(b.empty_supply_drivers, 0) AS empty_supply_drivers,
    COALESCE(b.total_drivers, 0) AS total_drivers,
    CASE WHEN COALESCE(b.active_drivers, 0) > 0
         THEN (d.trips_completed::numeric - d.trips_cancelled::numeric)
              / NULLIF(d.trips_completed + d.trips_cancelled, 0) * 100 END AS completed_rate_pct,
    now() AS refreshed_at, now() AS loaded_at
FROM day_agg d
LEFT JOIN driver_agg b ON d.week_start = b.week_start
    AND d.country = b.country AND d.city = b.city
    AND d.business_slice_name = b.business_slice_name
ORDER BY d.week_start, d.business_slice_name
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

    print(f"OV2-F.2D WEEK REBUILD (day_fact + driver bridge)")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'CONFIRMED'}")

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(SQL_BUILD, (args.country, args.city, args.date_from, args.date_to,
                                     args.country, args.city, args.date_from, args.date_to))

            cur.execute(f"SELECT COUNT(*) AS rows, COUNT(DISTINCT week_start) AS weeks, SUM(trips_completed) AS trips, SUM(active_drivers) AS drivers FROM {STAGING}")
            s = dict(cur.fetchone())
            print(f"  Staging: {s['rows']} rows, {s['weeks']} weeks, {s['trips']:,} trips, {s['drivers']:,} active_drivers")

            cur.execute(f"SELECT week_start, EXTRACT(DOW FROM week_start) FROM {STAGING} GROUP BY week_start HAVING EXTRACT(DOW FROM week_start)::int != 1")
            bad = cur.fetchall()
            if bad:
                print(f"  ISO FAIL: {len(bad)} weeks not Monday")
                return 1

            if args.dry_run:
                cur.execute(f"SELECT week_start, week_end, COUNT(*) AS slices, SUM(trips_completed) AS trips, SUM(active_drivers)::int AS drivers FROM {STAGING} GROUP BY 1,2 ORDER BY 1")
                for w in cur.fetchall():
                    print(f"    {w['week_start']} -> {w['week_end']}: {w['slices']} slices, {w['trips']:,} trips, {w['drivers']:,} drivers")
                print("DRY-RUN PASS")
                return 0

            staging_rows = s["rows"]
            if staging_rows == 0:
                print(f"  ABORT — staging is empty, no delete/insert performed")
                cur.execute(f"DROP TABLE IF EXISTS {STAGING}")
                return 0

            cur.execute(f"DELETE FROM {TARGET} WHERE week_start IN (SELECT DISTINCT week_start FROM {STAGING})")
            deleted = cur.rowcount
            cur.execute(f"""
                INSERT INTO {TARGET} (week_start, country, city, business_slice_name,
                    fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name,
                    trips_completed, trips_cancelled, active_drivers, avg_ticket,
                    trips_per_driver, revenue_yego_final, revenue_yego_net,
                    refreshed_at, loaded_at)
                SELECT week_start, country, city, business_slice_name,
                    fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name,
                    trips_completed, trips_cancelled, active_drivers, avg_ticket,
                    trips_per_driver, revenue_yego_final, revenue_yego_net,
                    refreshed_at, loaded_at
                FROM {STAGING}
            """)
            inserted = cur.rowcount
            conn.commit()
            cur.execute(f"DROP TABLE IF EXISTS {STAGING}")
            conn.commit()
            print(f"  Deleted {deleted}, Inserted {inserted}")
            print(f"  COMPLETE — active_drivers from bridge (exact, no upper bound)")
            return 0
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {e}"); return 1
        finally:
            cur.close()

if __name__ == "__main__":
    raise SystemExit(main())
