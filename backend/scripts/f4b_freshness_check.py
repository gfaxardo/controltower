import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

with get_db() as conn:
    cur = conn.cursor()
    try:
        cur.execute('SELECT MAX(fecha_inicio_viaje) FROM public.trips_2026')
        raw = cur.fetchone()[0]
        print(f"RAW max={raw}")

        cur.execute("SELECT MAX(activity_date) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima'")
        bridge = cur.fetchone()[0]
        print(f"BRIDGE max={bridge}")

        cur.execute("SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
        day = cur.fetchone()[0]
        print(f"DAY max={day}")

        cur.execute("SELECT MAX(week_start), COUNT(*), SUM(active_drivers)::int FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
        w = cur.fetchone()
        print(f"WEEK max={w[0]} rows={w[1]} drivers={w[2]:,}")

        cur.execute("SELECT MAX(month) FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
        month = cur.fetchone()[0]
        print(f"MONTH max={month}")

        cur.execute("SELECT MAX(operating_date) FROM ops.omniview_v2_serving_snapshot WHERE status='READY'")
        snap = cur.fetchone()[0]
        print(f"SNAPSHOT max={snap}")

        print("\n=== REFRESH LOG (last 5) ===")
        cur.execute("SELECT pipeline_name, status, started_at, COALESCE(error_message,'') FROM ops.refresh_run_log ORDER BY started_at DESC LIMIT 5")
        for r in cur.fetchall():
            s = str(r[2])[:19] if r[2] else '?'
            print(f"  {r[0] or '?':20s} {r[1]:10s} {s} {r[3][:80] if r[3] else ''}")

        # Detect if week uses raw (old pattern) or bridge (new pattern)
        # Old: few rows, max=old date. New: more rows, max=recent date, drivers from bridge
        week_ok = w[0] and str(w[0])[:10] >= "2026-06-01" and w[1] >= 30
        print(f"\nWEEK_FACT health: {'OK (bridge-based)' if week_ok else 'STALE (scheduler overwrite?)'}")

        # Check for legacy writes
        cur.execute("SELECT COUNT(*) FROM ops.refresh_run_log WHERE pipeline_name='business_slice' AND started_at > now() - interval '12 hours'")
        recent_jobs = cur.fetchone()[0]
        print(f"Scheduler jobs in last 12h: {recent_jobs}")
    finally:
        cur.close()
