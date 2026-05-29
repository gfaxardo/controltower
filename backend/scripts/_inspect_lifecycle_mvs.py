import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. mv_driver_lifecycle_monthly_kpis
    print("=" * 70)
    print("1. ops.mv_driver_lifecycle_monthly_kpis")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'mv_driver_lifecycle_monthly_kpis'
            ORDER BY ordinal_position
        """)
        for c in cur.fetchall():
            print(f"  {c['column_name']} ({c['data_type']})")

        cur.execute("""
            SELECT * FROM ops.mv_driver_lifecycle_monthly_kpis
            WHERE country = 'peru' AND city = 'lima'
            ORDER BY month_key DESC LIMIT 3
        """)
        print("\n  Sample rows (Lima):")
        for r in cur.fetchall():
            print(f"  {dict(r)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 2. mv_driver_lifecycle_weekly_kpis
    print("\n" + "=" * 70)
    print("2. ops.mv_driver_lifecycle_weekly_kpis")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'mv_driver_lifecycle_weekly_kpis'
            ORDER BY ordinal_position
            LIMIT 25
        """)
        for c in cur.fetchall():
            print(f"  {c['column_name']} ({c['data_type']})")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 3. v_driver_weekly_churn_reactivation
    print("\n" + "=" * 70)
    print("3. ops.v_driver_weekly_churn_reactivation")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT column_name, data_type FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'v_driver_weekly_churn_reactivation'
            ORDER BY ordinal_position
        """)
        for c in cur.fetchall():
            print(f"  {c['column_name']} ({c['data_type']})")
        cur.execute("SELECT * FROM ops.v_driver_weekly_churn_reactivation LIMIT 2")
        for r in cur.fetchall():
            print(f"  {dict(r)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 4. Old loyalty service query: what did it need from lifecycle?
    print("\n" + "=" * 70)
    print("4. Derive N+R from trips (trips_2025 + trips_2026) — April 2026 test")
    print("=" * 70)
    cur.execute("""
        WITH all_trips AS (
            SELECT conductor_id, fecha_inicio_viaje::date as trip_date, condicion
            FROM public.trips_2026
            UNION ALL
            SELECT conductor_id, fecha_inicio_viaje::date as trip_date, condicion
            FROM public.trips_2025
        ),
        driver_first_trip AS (
            SELECT conductor_id, MIN(trip_date) as first_trip
            FROM all_trips WHERE condicion = 'completed'
            GROUP BY conductor_id
        ),
        drivers_april AS (
            SELECT DISTINCT conductor_id
            FROM public.trips_2026
            WHERE condicion = 'completed'
              AND fecha_inicio_viaje >= '2026-04-01'
              AND fecha_inicio_viaje < '2026-05-01'
        ),
        drivers_march AS (
            SELECT DISTINCT conductor_id
            FROM public.trips_2026
            WHERE condicion = 'completed'
              AND fecha_inicio_viaje >= '2026-03-01'
              AND fecha_inicio_viaje < '2026-04-01'
        )
        SELECT
            COUNT(*)::int as new_in_april,
            COUNT(*) FILTER (
                WHERE conductor_id NOT IN (SELECT conductor_id FROM drivers_march)
                AND first_trip < '2026-04-01'
            )::int as reactivated,
            COUNT(*) FILTER (
                WHERE first_trip >= '2026-04-01' AND first_trip < '2026-05-01'
            )::int as strictly_new
        FROM drivers_april d
        JOIN driver_first_trip f ON f.conductor_id = d.conductor_id
    """)
    r = cur.fetchone()
    print(f"  New (first trip in April): {r['strictly_new']}")
    print(f"  Reactivated (was in April, not in March, first trip before April): {r['reactivated']}")
    print(f"  New in April (inconsistent definition): {r['new_in_april']}")
    print(f"  N+R total: {r['strictly_new'] + r['reactivated']}")
    print(f"  Apr total drivers: {r['strictly_new'] + r['reactivated'] + (r['new_in_april'] - r['strictly_new'])}")

    # More precise: reactivated = drivers active in current month, inactive for 30+ days before
    print("\n" + "=" * 70)
    print("5. Reactivated: inactive >30 days then active in April")
    print("=" * 70)
    cur.execute("""
        WITH april_drivers AS (
            SELECT DISTINCT conductor_id
            FROM public.trips_2026
            WHERE condicion = 'completed'
              AND fecha_inicio_viaje >= '2026-04-01'
              AND fecha_inicio_viaje < '2026-05-01'
        ),
        last_trip_before_april AS (
            SELECT conductor_id, MAX(fecha_inicio_viaje::date) as last_trip
            FROM public.trips_2026
            WHERE condicion = 'completed'
              AND fecha_inicio_viaje < '2026-04-01'
            GROUP BY conductor_id
        ),
        all_time_first AS (
            SELECT conductor_id, MIN(fecha_inicio_viaje::date) as first_trip
            FROM public.trips_2026 WHERE condicion = 'completed'
            GROUP BY conductor_id
        )
        SELECT
            COUNT(*)::int as total_april,
            COUNT(*) FILTER (
                WHERE f.first_trip >= '2026-04-01' AND f.first_trip < '2026-05-01'
            )::int as new_drivers,
            COUNT(*) FILTER (
                WHERE f.first_trip < '2026-04-01'
                  AND l.last_trip IS NOT NULL
                  AND l.last_trip <= '2026-03-01'
            )::int as reactivated_30d_inactive,
            COUNT(*) FILTER (
                WHERE f.first_trip < '2026-04-01'
                  AND (l.last_trip IS NULL OR l.last_trip <= '2026-03-01')
            )::int as reactivated_or_returned
        FROM april_drivers a
        LEFT JOIN last_trip_before_april l ON l.conductor_id = a.conductor_id
        LEFT JOIN all_time_first f ON f.conductor_id = a.conductor_id
    """)
    r = cur.fetchone()
    print(f"  April active drivers: {r['total_april']}")
    print(f"  New (first trip in April): {r['new_drivers']}")
    print(f"  Reactivated (>30d inactive): {r['reactivated_30d_inactive']}")
    print(f"  Reactivated or returned: {r['reactivated_or_returned']}")
    total_nr = r['new_drivers'] + r['reactivated_30d_inactive']
    print(f"  N+R (30d def): {total_nr}")
    print(f"  Reference N+R: ~1064")

    cur.close()
