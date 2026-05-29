import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor
from datetime import date, timedelta, datetime

init_db_pool()

month_start = date(2026, 4, 1)
reactivation_cutoff = month_start - timedelta(days=30)
month_end = date(2026, 4, 30)

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SET LOCAL statement_timeout = '120000'")  # 2 min

    cur.execute("""
        WITH all_trips_history AS (
            SELECT conductor_id, fecha_inicio_viaje::date as trip_date
            FROM public.trips_2026 WHERE condicion = 'completed'
            UNION ALL
            SELECT conductor_id, fecha_inicio_viaje::date
            FROM public.trips_2025 WHERE condicion = 'completed'
        ),
        driver_first_trip AS (
            SELECT conductor_id, MIN(trip_date) as first_trip
            FROM all_trips_history GROUP BY conductor_id
        ),
        active_current_month AS (
            SELECT DISTINCT conductor_id FROM public.trips_2026
            WHERE condicion = 'completed'
              AND fecha_inicio_viaje >= %(ms)s AND fecha_inicio_viaje < %(me)s
        ),
        last_activity_before_window AS (
            SELECT conductor_id, MAX(fecha_inicio_viaje::date) as last_trip
            FROM public.trips_2026
            WHERE condicion = 'completed' AND fecha_inicio_viaje < %(ms)s
            GROUP BY conductor_id
        )
        SELECT
            COUNT(*)::int as total_active,
            COUNT(*) FILTER (
                WHERE f.first_trip >= %(ms)s AND f.first_trip < %(me)s
            )::int as new_drivers,
            COUNT(*) FILTER (
                WHERE f.first_trip < %(ms)s
                  AND (l.last_trip IS NULL OR l.last_trip < %(rc)s)
            )::int as reactivated_drivers
        FROM active_current_month a
        LEFT JOIN driver_first_trip f ON f.conductor_id = a.conductor_id
        LEFT JOIN last_activity_before_window l ON l.conductor_id = a.conductor_id
    """, {"ms": month_start, "me": month_end, "rc": reactivation_cutoff})

    print("Query executing...")
    r = cur.fetchone()
    print(f"Result: {dict(r)}")
    print(f"Total active: {r['total_active']}")
    print(f"New: {r['new_drivers']}")
    print(f"Reactivated: {r['reactivated_drivers']}")
    print(f"N+R: {r['new_drivers'] + r['reactivated_drivers']}")
