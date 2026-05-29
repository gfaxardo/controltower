#!/usr/bin/env python3
"""
Refresh YEGO Operational Flow Enriched — Historical Presence MV + Serving Fact v2.
Populates ops.fct_yego_operational_flow_monthly_v2 for Lima pilot months.
"""
import sys, os
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

MONTHS = [(2026, 2), (2026, 3), (2026, 4), (2026, 5)]
COUNTRY = "PE"
CITY = "lima"
DS_ID = "yego_operational_supply_30d"
INACTIVITY_DAYS = 30

print("=" * 70)
print("REFRESH: YEGO Operational Flow Enriched V2")
print("=" * 70)

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Refresh MV
    print("\n[1/3] Refreshing historical presence MV...")
    cur.execute("REFRESH MATERIALIZED VIEW ops.mv_yego_driver_historical_presence_v1;")
    cur.execute("SELECT COUNT(*) FROM ops.mv_yego_driver_historical_presence_v1")
    mv_count = cur.fetchone()['count']
    cur.execute("SELECT COUNT(*) FILTER (WHERE vintage_risk) FROM ops.mv_yego_driver_historical_presence_v1")
    vintage = cur.fetchone()['count']
    print(f"  MV rows: {mv_count:,} | vintage_risk: {vintage:,}")

    # 2. Populate serving fact for each month
    print("\n[2/3] Computing monthly operational flow...")
    for yr, mo in MONTHS:
        ms = date(yr, mo, 1)
        me = date(yr, mo + 1, 1) if mo < 12 else date(yr + 1, 1, 1)
        cut = ms - timedelta(days=INACTIVITY_DAYS)
        total_days = (me - ms).days

        # Active drivers in month (SH>0)
        cur.execute("""
            SELECT COUNT(DISTINCT driver_id)::int
            FROM public.module_ct_fleet_summary_daily
            WHERE fecha >= %(ms)s AND fecha < %(me)s AND work_time_hours > 0
        """, {"ms": ms, "me": me})
        active = cur.fetchone()['count']

        # New: first_yego_seen in month AND active in month (SH>0)
        cur.execute("""
            WITH active AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %(ms)s AND fecha < %(me)s AND work_time_hours > 0
            ),
            first_seen AS (
                SELECT driver_id FROM ops.mv_yego_driver_historical_presence_v1
                WHERE first_yego_seen_date >= %(ms)s AND first_yego_seen_date < %(me)s
            )
            SELECT COUNT(*)::int FROM active a JOIN first_seen f ON f.driver_id = a.driver_id
        """, {"ms": ms, "me": me})
        new_d = cur.fetchone()['count']

        # Reactivated: active in month AND first_seen before month AND no activity in window
        cur.execute("""
            WITH active AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %(ms)s AND fecha < %(me)s AND work_time_hours > 0
            ),
            recent_inactive AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %(cut)s AND fecha < %(ms)s AND work_time_hours > 0
            ),
            has_history AS (
                SELECT driver_id FROM ops.mv_yego_driver_historical_presence_v1
                WHERE first_yego_seen_date < %(ms)s
            )
            SELECT COUNT(DISTINCT a.driver_id)::int
            FROM active a
            JOIN has_history h ON h.driver_id = a.driver_id
            WHERE a.driver_id NOT IN (SELECT driver_id FROM recent_inactive)
        """, {"ms": ms, "me": me, "cut": cut})
        rea_d = cur.fetchone()['count']

        # Existing active
        existing = active - new_d - rea_d

        # False new: active in month, fleet_first_seen in month but has pre-fleet trip history
        cur.execute("""
            WITH active AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %(ms)s AND fecha < %(me)s AND work_time_hours > 0
            )
            SELECT COUNT(*)::int FROM ops.mv_yego_driver_historical_presence_v1 hp
            JOIN active a ON a.driver_id = hp.driver_id
            WHERE hp.vintage_risk = true
              AND hp.fleet_first_seen >= %(ms)s AND hp.fleet_first_seen < %(me)s
        """, {"ms": ms, "me": me})
        false_new = cur.fetchone()['count']

        # Reclassified
        reclassified = false_new

        # Vintage risk %
        vintage_pct = round(false_new / max(new_d, 1) * 100, 1)

        # Data until
        cur.execute("SELECT MAX(fecha) FROM public.module_ct_fleet_summary_daily WHERE fecha < %(me)s", {"me": me})
        data_until = cur.fetchone()['max']

        # Insert/update
        cur.execute("""
            INSERT INTO ops.fct_yego_operational_flow_monthly_v2
                (month_start, country, city_norm, metric_universe, definition_set_id,
                 source_key, activity_signal, inactivity_window_days,
                 yego_new_drivers, yego_reactivated_drivers, yego_existing_active_drivers,
                 yego_operational_new_plus_reactivated,
                 false_new_drivers_detected, reclassified_new_to_existing_or_reactivated,
                 vintage_risk_count, vintage_risk_pct,
                 split_available, historical_lookback_start, data_until,
                 coverage_status, source_confidence, definition_status,
                 runtime_source, last_refreshed_at, notes)
            VALUES (%(ms)s, %(c)s, %(ci)s, 'yego_operational', %(ds)s,
                    'fleet_summary_daily', 'work_time_hours > 0', %(iw)s,
                    %(new)s, %(rea)s, %(ex)s, %(nr)s,
                    %(fn)s, %(recl)s,
                    %(vrc)s, %(vrp)s,
                    true, '2025-01-01'::date, %(du)s,
                    'ok', 'medium', 'provisional_pending_validation',
                    'serving_fact', now(), 'Enriched with trips_2025+2026 historical presence.')
            ON CONFLICT (month_start, country, city_norm, definition_set_id) DO UPDATE SET
                yego_new_drivers = EXCLUDED.yego_new_drivers,
                yego_reactivated_drivers = EXCLUDED.yego_reactivated_drivers,
                yego_existing_active_drivers = EXCLUDED.yego_existing_active_drivers,
                yego_operational_new_plus_reactivated = EXCLUDED.yego_operational_new_plus_reactivated,
                false_new_drivers_detected = EXCLUDED.false_new_drivers_detected,
                reclassified_new_to_existing_or_reactivated = EXCLUDED.reclassified_new_to_existing_or_reactivated,
                vintage_risk_count = EXCLUDED.vintage_risk_count,
                vintage_risk_pct = EXCLUDED.vintage_risk_pct,
                data_until = EXCLUDED.data_until,
                coverage_status = EXCLUDED.coverage_status,
                last_refreshed_at = now();
        """, {"ms": ms, "c": COUNTRY, "ci": CITY, "ds": DS_ID, "iw": INACTIVITY_DAYS,
              "new": new_d, "rea": rea_d, "ex": existing, "nr": new_d + rea_d,
              "fn": false_new, "recl": reclassified, "vrc": false_new, "vrp": vintage_pct,
              "du": data_until})

        nr = new_d + rea_d
        print(f"  {ms.strftime('%Y-%m')}: active={active:>5,} new={new_d:>5,} rea={rea_d:>5,} "
              f"exist={existing:>5,} N+R={nr:>5,} false_new={false_new:>5,} v_risk={vintage_pct:.0f}%")

    # 3. Summary
    print("\n[3/3] Serving fact populated.")
    cur.execute("SELECT COUNT(*) FROM ops.fct_yego_operational_flow_monthly_v2")
    fact_count = cur.fetchone()['count']
    print(f"  Rows in serving fact: {fact_count}")

    conn.commit()
    print("\n" + "=" * 70)
    print("REFRESH COMPLETE")
    print("=" * 70)
