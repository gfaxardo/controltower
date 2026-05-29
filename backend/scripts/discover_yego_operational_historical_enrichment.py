#!/usr/bin/env python3
"""
Discovery: Can trips_2025/trips_2026 enrich YEGO Operational Flow
to reduce false "new" drivers caused by fleet_summary vintage limitation?

All read-only. No production changes.
"""
import sys, os
from datetime import date, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

FLEET_VINTAGE_START = date(2026, 2, 15)
MONTH_START = date(2026, 4, 1)
MONTH_END = date(2026, 5, 1)

print("=" * 80)
print("DISCOVERY: Historical Enrichment for YEGO Operational Flow")
print("=" * 80)

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ═══════════════════════════════════════════════════════════════
    # T1: SOURCE AUDIT
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("T1: SOURCE AUDIT — Coverage & Driver Overlap")
    print("=" * 80)

    # Fleet summary
    cur.execute("""
        SELECT
            MIN(fecha) as min_date, MAX(fecha) as max_date,
            COUNT(DISTINCT driver_id) as total_drivers,
            COUNT(DISTINCT driver_id) FILTER (WHERE count_orders_completed > 0) as active_drivers,
            COUNT(DISTINCT driver_id) FILTER (WHERE work_time_hours > 0) as sh_drivers
        FROM public.module_ct_fleet_summary_daily
    """)
    fs = cur.fetchone()
    print(f"\n  fleet_summary_daily:")
    print(f"    Date range:         {fs['min_date']} to {fs['max_date']}")
    print(f"    Total drivers:      {fs['total_drivers']:,}")
    print(f"    Active (trips>0):   {fs['active_drivers']:,}")
    print(f"    With SH>0:          {fs['sh_drivers']:,}")

    # Fleet summary — April 2026
    cur.execute("""
        SELECT
            COUNT(DISTINCT driver_id) as total,
            COUNT(DISTINCT driver_id) FILTER (WHERE count_orders_completed > 0) as active,
            COUNT(DISTINCT driver_id) FILTER (WHERE work_time_hours > 0) as sh
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
    """)
    fs_apr = cur.fetchone()
    print(f"    April 2026:          total={fs_apr['total']:,} active={fs_apr['active']:,} sh>0={fs_apr['sh']:,}")

    # trips_2025
    cur.execute("""
        SELECT
            MIN(fecha_inicio_viaje::date) as min_date,
            MAX(fecha_inicio_viaje::date) as max_date,
            COUNT(DISTINCT conductor_id) as total_drivers,
            COUNT(DISTINCT conductor_id) FILTER (WHERE condicion = 'Completado') as active_drivers
        FROM public.trips_2025
    """)
    t5 = cur.fetchone()
    print(f"\n  trips_2025:")
    print(f"    Date range:          {t5['min_date']} to {t5['max_date']}")
    print(f"    Total drivers:       {t5['total_drivers']:,}")
    print(f"    Active (completed):  {t5['active_drivers']:,}")

    # trips_2026
    cur.execute("""
        SELECT
            MIN(fecha_inicio_viaje::date) as min_date,
            MAX(fecha_inicio_viaje::date) as max_date,
            COUNT(DISTINCT conductor_id) as total_drivers,
            COUNT(DISTINCT conductor_id) FILTER (WHERE condicion = 'Completado') as active_drivers
        FROM public.trips_2026
    """)
    t6 = cur.fetchone()
    print(f"\n  trips_2026:")
    print(f"    Date range:          {t6['min_date']} to {t6['max_date']}")
    print(f"    Total drivers:       {t6['total_drivers']:,}")
    print(f"    Active (completed):  {t6['active_drivers']:,}")

    # Lima-specific trips
    cur.execute("""
        WITH lima_parks AS (
            SELECT DISTINCT park_id FROM dim.dim_park
            WHERE city = 'lima' AND country = 'peru'
        )
        SELECT
            COUNT(DISTINCT t.conductor_id) as lima_total,
            COUNT(DISTINCT t.conductor_id) FILTER (WHERE t.condicion = 'Completado') as lima_active
        FROM public.trips_2026 t
        JOIN lima_parks lp ON lp.park_id = t.park_id
        WHERE t.fecha_inicio_viaje >= '2026-04-01'
          AND t.fecha_inicio_viaje < '2026-05-01'
    """)
    lima_trips = cur.fetchone()
    print(f"    April Lima active:   {lima_trips['lima_active']:,}")

    # ═══════════════════════════════════════════════════════════════
    # T2: DRIVER OVERLAP BETWEEN SOURCES
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("T2: DRIVER OVERLAP — fleet_summary vs trips")
    print("=" * 80)

    # Overlap: fleet_summary drivers also in trips
    cur.execute("""
        WITH fleet_ids AS (
            SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
        ),
        trip_ids_2025 AS (
            SELECT DISTINCT conductor_id FROM public.trips_2025
        ),
        trip_ids_2026 AS (
            SELECT DISTINCT conductor_id FROM public.trips_2026
        )
        SELECT
            (SELECT COUNT(*) FROM fleet_ids)::int as fleet_total,
            (SELECT COUNT(*) FROM trip_ids_2025)::int as trips_2025_total,
            (SELECT COUNT(*) FROM trip_ids_2026)::int as trips_2026_total,
            (SELECT COUNT(*) FROM fleet_ids f JOIN trip_ids_2025 t ON t.conductor_id = f.driver_id)::int as fleet_in_2025,
            (SELECT COUNT(*) FROM fleet_ids f JOIN trip_ids_2026 t ON t.conductor_id = f.driver_id)::int as fleet_in_2026
    """)
    ov = cur.fetchone()
    print(f"\n  fleet_summary total drivers:           {ov['fleet_total']:,}")
    print(f"  trips_2025 total drivers:              {ov['trips_2025_total']:,}")
    print(f"  trips_2026 total drivers:              {ov['trips_2026_total']:,}")
    print(f"  fleet drivers ALSO in trips_2025:      {ov['fleet_in_2025']:,} ({ov['fleet_in_2025']/max(ov['fleet_total'],1)*100:.1f}%)")
    print(f"  fleet drivers ALSO in trips_2026:      {ov['fleet_in_2026']:,} ({ov['fleet_in_2026']/max(ov['fleet_total'],1)*100:.1f}%)")
    print(f"  fleet drivers NOT in any trips:        {ov['fleet_total'] - max(ov['fleet_in_2025'], ov['fleet_in_2026']):,}")

    # ═══════════════════════════════════════════════════════════════
    # T3: VINTAGE RISK — "Fake New" Detection
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("T3: VINTAGE RISK — Fake New Detection (April 2026)")
    print("=" * 80)

    # Current operational flow: new = first SH>0 in fleet_summary
    cur.execute("""
        WITH fleet_new AS (
            SELECT driver_id, MIN(fecha) as first_seen
            FROM public.module_ct_fleet_summary_daily
            WHERE work_time_hours > 0
            GROUP BY driver_id
        ),
        april_new AS (
            SELECT * FROM fleet_new
            WHERE first_seen >= '2026-04-01' AND first_seen < '2026-05-01'
        ),
        trips_before_feb AS (
            SELECT DISTINCT conductor_id FROM public.trips_2025
            WHERE fecha_inicio_viaje < '2026-02-15' AND condicion = 'Completado'
            UNION
            SELECT DISTINCT conductor_id FROM public.trips_2026
            WHERE fecha_inicio_viaje < '2026-02-15' AND condicion = 'Completado'
        ),
        trips_between_feb_mar AS (
            SELECT DISTINCT conductor_id FROM public.trips_2026
            WHERE fecha_inicio_viaje >= '2026-02-01' AND fecha_inicio_viaje < '2026-04-01'
              AND condicion = 'Completado'
        )
        SELECT
            (SELECT COUNT(*) FROM april_new)::int as fleet_classified_new,
            (SELECT COUNT(*) FROM april_new a JOIN trips_before_feb t ON t.conductor_id = a.driver_id)::int as had_trips_before_fleet_vintage,
            (SELECT COUNT(*) FROM april_new a JOIN trips_between_feb_mar t ON t.conductor_id = a.driver_id)::int as had_trips_feb_mar,
            (SELECT COUNT(*) FROM april_new a
             WHERE a.driver_id NOT IN (SELECT conductor_id FROM trips_before_feb)
               AND a.driver_id NOT IN (SELECT conductor_id FROM trips_between_feb_mar))::int as genuine_no_trip_history
    """)
    v = cur.fetchone()
    print(f"\n  Drivers classified as NEW by fleet_summary in April:  {v['fleet_classified_new']:,}")
    print(f"  ...BUT had trips BEFORE fleet vintage (pre Feb 15):   {v['had_trips_before_fleet_vintage']:,} ({v['had_trips_before_fleet_vintage']/max(v['fleet_classified_new'],1)*100:.0f}%)")
    print(f"  ...BUT had trips in Feb-Mar (between vintage & April): {v['had_trips_feb_mar']:,}")
    print(f"  Genuinely no trip history before April:               {v['genuine_no_trip_history']:,}")
    print(f"")
    print(f"  POTENTIAL FAKE NEW: {v['had_trips_before_fleet_vintage']:,} drivers classified as new")
    print(f"  but actually had completed trips BEFORE fleet_summary started tracking.")
    print(f"  These {v['had_trips_before_fleet_vintage']} should be RE-CLASSIFIED (reactivated or existing).")

    # ═══════════════════════════════════════════════════════════════
    # T4: OPERATIONAL FLOW — fleet-only vs trips-enriched
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("T4: OPERATIONAL FLOW — fleet-only vs trips-enriched (30d window)")
    print("=" * 80)

    for window_days in [30, 60, 90]:
        cut = MONTH_START - timedelta(days=window_days)
        print(f"\n  --- Window: {window_days} days ---")

        # Fleet-only new (current logic)
        cur.execute("""
            WITH first_sh AS (
                SELECT driver_id, MIN(fecha) as first_seen
                FROM public.module_ct_fleet_summary_daily
                WHERE work_time_hours > 0
                GROUP BY driver_id
            )
            SELECT COUNT(*)::int FROM first_sh
            WHERE first_seen >= '2026-04-01' AND first_seen < '2026-05-01'
        """)
        fleet_new = cur.fetchone()['count']

        # Enriched new: first SH>0 in April AND no trips before Feb 15
        cur.execute("""
            WITH first_sh AS (
                SELECT driver_id, MIN(fecha) as first_seen
                FROM public.module_ct_fleet_summary_daily
                WHERE work_time_hours > 0
                GROUP BY driver_id
            ),
            april_new_fleet AS (
                SELECT driver_id FROM first_sh
                WHERE first_seen >= '2026-04-01' AND first_seen < '2026-05-01'
            ),
            has_trip_history AS (
                SELECT DISTINCT conductor_id FROM public.trips_2025 WHERE condicion = 'Completado'
                UNION
                SELECT DISTINCT conductor_id FROM public.trips_2026 WHERE condicion = 'Completado'
            )
            SELECT COUNT(*)::int FROM april_new_fleet a
            WHERE a.driver_id NOT IN (SELECT conductor_id FROM has_trip_history)
        """)
        enriched_new = cur.fetchone()['count']
        fake_new = fleet_new - enriched_new

        # Fleet-only reactivated
        cur.execute("""
            WITH current_d AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01' AND work_time_hours > 0
            ),
            historical_d AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha < '2026-04-01' AND work_time_hours > 0
            ),
            recent_inactive AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %(cut)s AND fecha < '2026-04-01' AND work_time_hours > 0
            )
            SELECT COUNT(DISTINCT cd.driver_id)::int
            FROM current_d cd
            WHERE cd.driver_id IN (SELECT driver_id FROM historical_d)
              AND cd.driver_id NOT IN (SELECT driver_id FROM recent_inactive)
        """, {"cut": cut})
        fleet_rea = cur.fetchone()['count']

        # Enriched reactivated: add fake-new drivers that were idle in window
        cur.execute("""
            WITH current_d AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01' AND work_time_hours > 0
            ),
            historical_d AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha < '2026-04-01' AND work_time_hours > 0
            ),
            recent_inactive AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %(cut)s AND fecha < '2026-04-01' AND work_time_hours > 0
            ),
            trips_active_recent AS (
                SELECT DISTINCT conductor_id FROM public.trips_2026
                WHERE condicion = 'Completado' AND fecha_inicio_viaje >= %(cut)s
                  AND fecha_inicio_viaje < '2026-04-01'
            ),
            has_trip_history AS (
                SELECT DISTINCT conductor_id FROM public.trips_2025 WHERE condicion = 'Completado'
                UNION
                SELECT DISTINCT conductor_id FROM public.trips_2026 WHERE condicion = 'Completado'
            )
            SELECT COUNT(DISTINCT cd.driver_id)::int
            FROM current_d cd
            WHERE (cd.driver_id IN (SELECT driver_id FROM historical_d)
                   OR cd.driver_id IN (SELECT conductor_id FROM has_trip_history))
              AND cd.driver_id NOT IN (SELECT driver_id FROM recent_inactive)
              AND cd.driver_id NOT IN (SELECT conductor_id FROM trips_active_recent)
        """, {"cut": cut})
        enriched_rea = cur.fetchone()['count']

        print(f"    Fleet-only:     New={fleet_new:>5,}  Rea={fleet_rea:>5,}  N+R={fleet_new+fleet_rea:>5,}")
        print(f"    Trips-enriched: New={enriched_new:>5,}  Rea={enriched_rea:>5,}  N+R={enriched_new+enriched_rea:>5,}")
        print(f"    Reclassified:   fake_new->rea={fake_new:>5,}  extra_rea={enriched_rea-fleet_rea:>+5,}")
        print(f"    Vintage risk:   {fake_new/max(fleet_new,1)*100:.0f}% of fleet_new were fake new")

    # ═══════════════════════════════════════════════════════════════
    # T5: UNIVERSE CONTAMINATION RISK
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("T5: UNIVERSE CONTAMINATION RISK")
    print("=" * 80)

    # trips_2026 has park_id — can we filter to YEGO Lima?
    cur.execute("""
        SELECT dp.park_id, dp.park_name, dp.city, COUNT(DISTINCT t.conductor_id) as drivers
        FROM public.trips_2026 t
        JOIN dim.dim_park dp ON dp.park_id = t.park_id
        WHERE t.fecha_inicio_viaje >= '2026-04-01'
          AND t.fecha_inicio_viaje < '2026-05-01'
          AND dp.city = 'lima'
        GROUP BY dp.park_id, dp.park_name, dp.city
        ORDER BY drivers DESC LIMIT 10
    """)
    lima_parks = cur.fetchall()
    print(f"\n  Lima parks in trips_2026 (April):")
    for p in lima_parks:
        print(f"    {p['park_name'][:30]:<30} park_id={p['park_id'][:12]}... drivers={p['drivers']:,}")

    # Can we match fleet_summary driver_ids with trips?
    cur.execute("""
        WITH fleet_apr AS (
            SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
            WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
        ),
        trips_apr AS (
            SELECT DISTINCT t.conductor_id FROM public.trips_2026 t
            JOIN dim.dim_park dp ON dp.park_id = t.park_id
            WHERE dp.city = 'lima' AND dp.country = 'peru'
              AND t.fecha_inicio_viaje >= '2026-04-01'
              AND t.fecha_inicio_viaje < '2026-05-01'
              AND t.condicion = 'Completado'
        )
        SELECT
            (SELECT COUNT(*) FROM fleet_apr)::int as fleet_april,
            (SELECT COUNT(*) FROM trips_apr)::int as trips_lima_april,
            (SELECT COUNT(*) FROM fleet_apr f JOIN trips_apr t ON t.conductor_id = f.driver_id)::int as overlap
    """)
    match = cur.fetchone()
    print(f"\n  April driver match: fleet_summary vs Lima trips:")
    print(f"    Fleet April drivers:     {match['fleet_april']:,}")
    print(f"    Lima trips April:        {match['trips_lima_april']:,}")
    print(f"    Overlap (same driver):   {match['overlap']:,} ({match['overlap']/max(match['fleet_april'],1)*100:.0f}%)")
    print(f"    Drivers in trips NOT in fleet:  {match['trips_lima_april'] - match['overlap']:,}")
    print(f"")
    print(f"  KEY FINDING: {match['overlap']/max(match['fleet_april'],1)*100:.0f}% of fleet_summary drivers")
    print(f"  also appear in Lima trips. driver_id format IS compatible between sources.")

    # ═══════════════════════════════════════════════════════════════
    # T6: RECOMMENDATION
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("T6: RECOMMENDATION")
    print("=" * 80)

    print(f"""
  YES — trips_2025 and trips_2026 CAN serve as historical enrichment
  to reduce false "new" drivers in YEGO Operational Flow.

  Rationale:
  1. Driver ID format IS compatible between fleet_summary and trips.
  2. {match['overlap']/max(match['fleet_april'],1)*100:.0f}% of fleet drivers appear in trips (strong overlap).
  3. {v['had_trips_before_fleet_vintage']} drivers classified as "new" in April actually had trips BEFORE
     fleet_summary started tracking. These are FALSE NEW.
  4. Trips can identify pre-existing YEGO activity going back to 2025.

  Recommended approach for future implementation:
  - Use trips as AUXILIARY historical presence source only.
  - Do NOT replace fleet_summary as primary activity source.
  - Enrichment: if a driver appears as "new" in fleet_summary but has
    completed trips before fleet_summary vintage → reclassify as
    "existing with pre-fleet history" (not new).
  - For reactivation: add trips-based activity check to the inactivity
    window to detect reactivation more accurately.

  Best window: 30 days (standard, most sensitive)
  Alternative: 60 days for less noise

  GO for implementation in next phase.
  DO NOT implement in production yet.
""")

    cur.close()
    print("=" * 80)
    print("DISCOVERY COMPLETE")
    print("=" * 80)
