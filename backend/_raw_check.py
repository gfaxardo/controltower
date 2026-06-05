from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. MONTH_TRIPS_MISMATCH raw query
    cur.execute("""
        WITH last_m AS (
            SELECT MAX(month)::date AS m
            FROM ops.real_business_slice_month_fact
            WHERE month < date_trunc('month', CURRENT_DATE)::date
        )
        SELECT last_m.m::text AS period,
               (SELECT SUM(trips_completed)::numeric FROM ops.real_business_slice_month_fact WHERE month = (SELECT m FROM last_m)) AS fact_trips,
               (SELECT SUM(trips_completed)::numeric FROM ops.real_business_slice_day_fact WHERE date_trunc('month', trip_date)::date = (SELECT m FROM last_m)) AS raw_trips
        FROM last_m
    """)
    r = cur.fetchone()
    print(f"MONTH_TRIPS query: period={r['period']} fact={r['fact_trips']} raw={r['raw_trips']}")

    # 2. day_fact
    cur.execute("SELECT MIN(trip_date), MAX(trip_date), COUNT(DISTINCT trip_date), SUM(trips_completed)::bigint FROM ops.real_business_slice_day_fact")
    d = cur.fetchone()
    print(f"day_fact: min={d[0]} max={d[1]} dates={d[2]} trips={d[3]}")

    # 3. month_fact May
    cur.execute("SELECT SUM(trips_completed)::bigint FROM ops.real_business_slice_month_fact WHERE month = '2026-05-01'")
    m = cur.fetchone()
    print(f"month_fact May: trips={m[0]}")

    # 4. v_real_trips_business_slice_resolved May
    cur.execute("SELECT COUNT(*)::bigint FROM ops.v_real_trips_business_slice_resolved WHERE trip_month = '2026-05-01' AND resolution_status = 'resolved'")
    v = cur.fetchone()
    print(f"v_resolved May: rows={v[0]}")

    # 5. raw trips_2026 May
    cur.execute("SELECT COUNT(*)::bigint FROM public.trips_2026 WHERE fecha_inicio_viaje >= '2026-05-01' AND fecha_inicio_viaje < '2026-06-01'")
    t = cur.fetchone()
    print(f"trips_2026 May: rows={t[0]}")

    # 6. day_fact May dates
    cur.execute("SELECT trip_date FROM ops.real_business_slice_day_fact WHERE trip_date >= '2026-05-01' AND trip_date < '2026-06-01' ORDER BY trip_date LIMIT 5")
    may_dates = [r2[0] for r2 in cur.fetchall()]
    cur.execute("SELECT COUNT(DISTINCT trip_date) FROM ops.real_business_slice_day_fact WHERE trip_date >= '2026-05-01' AND trip_date < '2026-06-01'")
    may_n = cur.fetchone()[0]
    print(f"day_fact May dates: first={may_dates} count={may_n}")

    # 7. staging table status
    cur.execute("SELECT COUNT(*) FROM _stg_real_business_slice_day_fact")
    stg = cur.fetchone()[0]
    print(f"staging day rows: {stg}")

    # 8. audit last run
    cur.execute("SELECT run_id, status, day_rows, week_rows, month_rows, finished_at FROM ops.omniview_real_slice_refresh_audit ORDER BY started_at DESC LIMIT 2")
    for ar in cur.fetchall():
        print(f"audit: {ar['run_id']} {ar['status']} D={ar['day_rows']} W={ar['week_rows']} M={ar['month_rows']} @{ar['finished_at']}")

    cur.close()
