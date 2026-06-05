from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=== MAY 2026 WEEKS: Row duplication analysis ===")
    cur.execute("""
        SELECT week_start, business_slice_name,
               COUNT(*) AS rows,
               COUNT(DISTINCT fleet_display_name) AS fleets,
               SUM(trips_completed)::bigint AS trips_total,
               MIN(trips_completed)::bigint AS trips_per_row,
               SUM(revenue_yego_final)::numeric AS rev_total
        FROM ops.real_business_slice_week_fact
        WHERE country = 'peru' AND city = 'lima'
          AND week_start >= '2026-05-01'
        GROUP BY week_start, business_slice_name
        HAVING COUNT(*) > 1
        ORDER BY week_start, trips_total DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['week_start']} {r['business_slice_name']}: {r['rows']} rows x {r['trips_per_row']:,} trips = {r['trips_total']:,} total | {r['fleets']} fleets | rev={r['rev_total']:,.0f}")

    # Corrected counts (using DISTINCT on composite key)
    print("\n=== CORRECTED WEEKS: Deduplicated (MAX per composite key) ===")
    cur.execute("""
        SELECT week_start, business_slice_name,
               SUM(trips_completed)::bigint AS trips_dup,
               (SELECT SUM(t) FROM (
                   SELECT DISTINCT ON (week_start, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name)
                   trips_completed AS t
                   FROM ops.real_business_slice_week_fact w2
                   WHERE w2.week_start = w1.week_start
                     AND w2.country = w1.country
                     AND w2.city = w1.city
                     AND w2.business_slice_name = w1.business_slice_name
               ) sub)::bigint AS trips_corrected
        FROM ops.real_business_slice_week_fact w1
        WHERE country = 'peru' AND city = 'lima'
          AND week_start >= '2026-05-01'
        GROUP BY week_start, business_slice_name, country, city
        HAVING COUNT(DISTINCT fleet_display_name) > 1
        ORDER BY week_start
    """)
    for r in cur.fetchall():
        ratio = r['trips_dup'] / r['trips_corrected'] if r['trips_corrected'] else 0
        print(f"  {r['week_start']} {r['business_slice_name']}: dup={r['trips_dup']:,} corrected={r['trips_corrected']:,} ratio={ratio:.1f}x")

    # Check day_fact for same issue
    print("\n=== DAY_FACT: Duplication check ===")
    cur.execute("""
        SELECT trip_date, business_slice_name,
               COUNT(*) AS rows,
               COUNT(DISTINCT fleet_display_name) AS fleets
        FROM ops.real_business_slice_day_fact
        WHERE country = 'peru' AND city = 'lima'
          AND trip_date >= '2026-05-20'
        GROUP BY trip_date, business_slice_name
        HAVING COUNT(*) > 1
        ORDER BY trip_date
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  {r['trip_date']} {r['business_slice_name']}: {r['rows']} rows, {r['fleets']} fleets")

    cur.close()
