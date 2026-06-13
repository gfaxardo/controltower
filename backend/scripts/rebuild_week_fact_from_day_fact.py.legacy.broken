"""OV2-F.2C — Rebuild week_fact FROM day_fact (no raw trips, ISO weeks)
Usage:
  python -m scripts.rebuild_week_fact_from_day_fact --date-from 2026-04-01 --date-to 2026-06-06 --country peru --city lima --dry-run
  python -m scripts.rebuild_week_fact_from_day_fact --date-from 2026-04-01 --date-to 2026-06-06 --country peru --city lima --confirm
"""
import sys, os, argparse, logging
from datetime import date as dt_date, datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

STAGING_TABLE = "ops._stg_rebuild_week_fact"
TARGET_TABLE = "ops.real_business_slice_week_fact"
BATCH_DAYS = 30


def _first_monday(d: dt_date) -> dt_date:
    return d - timedelta(days=d.weekday())


def main():
    ap = argparse.ArgumentParser(description="Rebuild week_fact from day_fact (no raw trips)")
    ap.add_argument("--date-from", required=True)
    ap.add_argument("--date-to", required=True)
    ap.add_argument("--country", default="peru")
    ap.add_argument("--city", default="lima")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.confirm:
        print("Use --dry-run to validate or --confirm to execute.")
        return 1

    date_from = dt_date.fromisoformat(args.date_from)
    date_to = dt_date.fromisoformat(args.date_to)
    fm = _first_monday(date_from)
    lm = _first_monday(date_to) + timedelta(days=6)

    print(f"OV2-F.2C WEEK FACT REBUILD FROM DAY_FACT")
    print(f"  Range: {date_from} -> {date_to}")
    print(f"  ISO weeks: {fm} -> {lm}")
    print(f"  Source: {TARGET_TABLE.replace('week','day')}")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'CONFIRMED'}")

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # ── 1) Build staging from day_fact ──
            build_sql = f"""
            DROP TABLE IF EXISTS {STAGING_TABLE};
            CREATE TABLE {STAGING_TABLE} (LIKE {TARGET_TABLE} INCLUDING DEFAULTS);

            INSERT INTO {STAGING_TABLE}
                (week_start, week_end, country, city, business_slice_name,
                 fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name,
                 trips_completed, trips_cancelled, active_drivers,
                 avg_ticket, trips_per_driver, revenue_yego_final, revenue_yego_net,
                 refreshed_at, loaded_at)
            SELECT
                date_trunc('week', trip_date)::date AS week_start,
                (date_trunc('week', trip_date)::date + interval '6 days')::date AS week_end,
                TRIM(country), TRIM(city), business_slice_name,
                COALESCE(fleet_display_name, ''),
                COALESCE(is_subfleet, false),
                COALESCE(subfleet_name, ''),
                COALESCE(parent_fleet_name, ''),
                SUM(COALESCE(trips_completed, 0)) AS trips_completed,
                SUM(COALESCE(trips_cancelled, 0)) AS trips_cancelled,
                SUM(COALESCE(active_drivers, 0)) AS active_drivers,
                CASE WHEN SUM(COALESCE(trips_completed, 0)) > 0
                     THEN SUM(COALESCE(revenue_yego_final, 0))
                          / NULLIF(SUM(COALESCE(trips_completed, 0)), 0)
                END AS avg_ticket,
                CASE WHEN SUM(COALESCE(active_drivers, 0)) > 0
                     THEN SUM(COALESCE(trips_completed, 0))::numeric
                          / NULLIF(SUM(COALESCE(active_drivers, 0)), 0)
                END AS trips_per_driver,
                SUM(COALESCE(revenue_yego_final, 0)) AS revenue_yego_final,
                SUM(COALESCE(revenue_yego_net, 0)) AS revenue_yego_net,
                now(), now()
            FROM ops.real_business_slice_day_fact
            WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s
              AND trip_date >= %s AND trip_date <= %s
            GROUP BY
                date_trunc('week', trip_date)::date,
                (date_trunc('week', trip_date)::date + interval '6 days')::date,
                TRIM(country), TRIM(city), business_slice_name,
                fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name
            """
            print(f"\nBuilding staging from day_fact...")
            cur.execute(build_sql, (args.country, args.city, date_from, date_to))
            conn.commit()

            # ── 2) Validate staging ──
            cur.execute(f"SELECT COUNT(*) AS rows, COUNT(DISTINCT week_start) AS weeks, SUM(trips_completed) AS trips, SUM(revenue_yego_final) AS revenue FROM {STAGING_TABLE}")
            staging = dict(cur.fetchone())
            print(f"  Staging: {staging['rows']} rows, {staging['weeks']} weeks, {staging['trips']:,} trips, {staging['revenue']:,.0f} revenue")

            cur.execute(f"""
                SELECT week_start, EXTRACT(DOW FROM week_start)::int AS dow
                FROM {STAGING_TABLE} GROUP BY week_start
                HAVING EXTRACT(DOW FROM week_start)::int != 1
            """)
            bad_dow = cur.fetchall()
            if bad_dow:
                print(f"  ISO VALIDATION FAILED: {len(bad_dow)} week_start values are not Monday")
                for r in bad_dow:
                    print(f"    week_start={r['week_start']} DOW={r['dow']}")
                return 1

            # ── 3) Validate against day_fact totals ──
            cur.execute(f"""
                SELECT SUM(COALESCE(trips_completed,0)) AS day_trips,
                       SUM(COALESCE(revenue_yego_final,0)) AS day_revenue
                FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s
                  AND trip_date >= %s AND trip_date <= %s
            """, (args.country, args.city, date_from, date_to))
            day_totals = dict(cur.fetchone())
            trips_ok = abs((staging['trips'] or 0) - (day_totals['day_trips'] or 0)) < 2
            rev_ok = abs((staging['revenue'] or 0) - (day_totals['day_revenue'] or 0)) < 0.01
            print(f"  Day totals: {day_totals['day_trips']:,} trips, {day_totals['day_revenue']:,.0f} revenue")
            print(f"  Trips match: {'OK' if trips_ok else 'MISMATCH'} | Revenue match: {'OK' if rev_ok else 'MISMATCH'}")

            # ── 4) Show week-level breakdown ──
            cur.execute(f"""
                SELECT week_start, week_end, COUNT(*) AS slices,
                       SUM(trips_completed) AS trips, SUM(revenue_yego_final) AS revenue
                FROM {STAGING_TABLE}
                GROUP BY week_start, week_end ORDER BY week_start
            """)
            print(f"\n  Week breakdown:")
            for w in cur.fetchall():
                print(f"    {w['week_start']} → {w['week_end']}: {w['slices']} slices, {int(w['trips'] or 0):,} trips, {w['revenue']:,.0f} revenue")

            if args.dry_run:
                print(f"\nDRY-RUN PASS. No changes made to {TARGET_TABLE}.")
                print(f"To execute: re-run with --confirm")
                return 0

            # ── 5) Atomic swap: DELETE affected weeks, INSERT from staging ──
            print(f"\nSwapping staging -> production...")
            cur.execute(f"""
                DELETE FROM {TARGET_TABLE}
                WHERE week_start IN (SELECT DISTINCT week_start FROM {STAGING_TABLE})
                  AND LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s
            """, (args.country, args.city))
            deleted = cur.rowcount
            print(f"  Deleted {deleted} existing rows")

            cur.execute(f"INSERT INTO {TARGET_TABLE} SELECT * FROM {STAGING_TABLE}")
            inserted = cur.rowcount
            print(f"  Inserted {inserted} new rows")

            cur.execute(f"DROP TABLE IF EXISTS {STAGING_TABLE}")
            conn.commit()

            print(f"\nREBUILD COMPLETE: {inserted} rows across {staging['weeks']} ISO weeks")
            if not trips_ok or not rev_ok:
                print("WARNING: Day→week totals don't match day_fact. Review above.")
                return 2
            return 0

        except Exception as e:
            conn.rollback()
            print(f"ERROR: {e}")
            return 1
        finally:
            cur.close()


if __name__ == "__main__":
    raise SystemExit(main())
