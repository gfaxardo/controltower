from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Check for duplicates in week_fact for anomalous weeks
    print("=== DUPLICATE CHECK: Week 2026-03-30, Auto Regular Lima ===")
    cur.execute("""
        SELECT week_start, business_slice_name, fleet_display_name,
               COUNT(*) AS row_count,
               SUM(trips_completed)::bigint AS trips,
               SUM(revenue_yego_final)::numeric AS rev
        FROM ops.real_business_slice_week_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
          AND week_start = '2026-03-30'
        GROUP BY week_start, business_slice_name, fleet_display_name
        ORDER BY trips DESC
    """)
    for r in cur.fetchall():
        print(f"  rows={r['row_count']} trips={r['trips']} rev={r['rev']} fleet={r['fleet_display_name']}")

    # Check ALL slices for that week
    print("\n=== ALL SLICES: Week 2026-03-30 ===")
    cur.execute("""
        SELECT business_slice_name,
               COUNT(*) AS rows,
               SUM(trips_completed)::bigint AS trips
        FROM ops.real_business_slice_week_fact
        WHERE week_start = '2026-03-30'
        GROUP BY business_slice_name
        ORDER BY trips DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['business_slice_name']}: {r['rows']} rows, {r['trips']} trips")

    # Compare: normal week
    print("\n=== ALL SLICES: Week 2026-05-25 (normal) ===")
    cur.execute("""
        SELECT business_slice_name,
               COUNT(*) AS rows,
               SUM(trips_completed)::bigint AS trips
        FROM ops.real_business_slice_week_fact
        WHERE week_start = '2026-05-25'
        GROUP BY business_slice_name
        ORDER BY trips DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['business_slice_name']}: {r['rows']} rows, {r['trips']} trips")

    # Check: does day_fact have the same anomaly?
    print("\n=== DAY_FACT: Week 2026-03-30 vs 2026-05-25 ===")
    cur.execute("""
        SELECT '2026-03-30' AS wk,
               SUM(trips_completed)::bigint AS trips,
               COUNT(DISTINCT trip_date) AS days
        FROM ops.real_business_slice_day_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
          AND trip_date >= '2026-03-30' AND trip_date < '2026-04-06'
        UNION ALL
        SELECT '2026-05-25' AS wk,
               SUM(trips_completed)::bigint AS trips,
               COUNT(DISTINCT trip_date) AS days
        FROM ops.real_business_slice_day_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
          AND trip_date >= '2026-05-25' AND trip_date < '2026-05-31'
    """)
    for r in cur.fetchall():
        print(f"  week={r['wk']} day_fact: trips={r['trips']} days={r['days']}")

    cur.close()
