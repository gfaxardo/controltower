#!/usr/bin/env python3
"""
T1 Discovery: Find N+R (Nuevos + Reactivados) data sources for Lima.
Read only. No modifications.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 75)
    print("T1: DISCOVERY DE FUENTES NUEVOS + REACTIVADOS (LIMA)")
    print("=" * 75)

    # 1. Search for lifecycle tables/views
    print("\n--- Lifecycle objects ---")
    cur.execute("""
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE (table_name LIKE '%lifecycle%' OR table_name LIKE '%life_cycle%'
               OR table_name LIKE '%new_driver%' OR table_name LIKE '%reactivat%'
               OR table_name LIKE '%churn%')
          AND table_schema NOT IN ('pg_catalog','information_schema')
        ORDER BY table_schema, table_name
    """)
    lifecycle_objects = cur.fetchall()
    if lifecycle_objects:
        for o in lifecycle_objects:
            print(f"  {o['table_schema']}.{o['table_name']} ({o['table_type']})")
    else:
        print("  (none found)")

    # 2. Check ops.v_driver_lifecycle_* views
    print("\n--- ops.v_driver_lifecycle* views ---")
    cur.execute("""
        SELECT table_name FROM information_schema.views
        WHERE table_schema = 'ops' AND table_name LIKE '%driver%lifecycle%'
        UNION
        SELECT matviewname FROM pg_matviews
        WHERE schemaname = 'ops' AND matviewname LIKE '%driver%lifecycle%'
        ORDER BY 1
    """)
    for r in cur.fetchall():
        print(f"  {r['table_name']}" if 'table_name' in r else f"  {r['matviewname']}")

    # 3. Check ops.real_business_slice columns for new/reactivated
    print("\n--- ops.real_business_slice_month_fact columns ---")
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'ops' AND table_name = 'real_business_slice_month_fact'
        ORDER BY ordinal_position
    """)
    rbs_cols = [r['column_name'] for r in cur.fetchall()]
    print(f"  Total columns: {len(rbs_cols)}")
    nr_relevant = [c for c in rbs_cols if any(t in c.lower() for t in ['new','active','driver','lifecycle','reactiv','churn','activ'])]
    print(f"  N+R relevant: {nr_relevant}")

    # 4. Check public.module_ct_cabinet_drivers for lifecycle
    print("\n--- public.module_ct_cabinet_drivers — lifecycle columns ---")
    cur.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'module_ct_cabinet_drivers'
        ORDER BY ordinal_position
    """)
    cab_cols = cur.fetchall()
    nr_cab = [c for c in cab_cols if any(t in c['column_name'].lower() for t in ['new','active','lifecycle','reactiv','churn','hire','first','stage','segment'])]
    print(f"  Total columns: {len(cab_cols)}")
    print(f"  N+R relevant:")
    for c in nr_cab:
        print(f"    {c['column_name']} ({c['data_type']})")

    # 5. Check cabinet_drivers stage/segment values
    print("\n--- cabinet_drivers: stage & segment distribution ---")
    cur.execute("SELECT stage, COUNT(*)::int as cnt FROM public.module_ct_cabinet_drivers GROUP BY stage ORDER BY cnt DESC LIMIT 10")
    for r in cur.fetchall():
        print(f"  stage='{r['stage']}': {r['cnt']}")
    cur.execute("SELECT segment, COUNT(*)::int as cnt FROM public.module_ct_cabinet_drivers GROUP BY segment ORDER BY cnt DESC LIMIT 10")
    for r in cur.fetchall():
        print(f"  segment='{r['segment']}': {r['cnt']}")

    # 6. Check trips_unified for first-trip per driver
    print("\n--- public.trips_unified: first trip date per driver ---")
    cur.execute("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'trips_unified'
        ORDER BY ordinal_position
        LIMIT 20
    """)
    for c in cur.fetchall():
        print(f"  {c['column_name']} ({c['data_type']})")

    # Check if trips_unified has driver_id
    cur.execute("""
        SELECT COUNT(*)::int, MIN(date)::text, MAX(date)::text
        FROM public.trips_unified
    """)
    r = cur.fetchone()
    print(f"  Rows: {r['count']}, range: {r['min']} to {r['max']}")

    # 7. Check trips_2026 for driver first-trip
    print("\n--- public.trips_2026: conductor_id — check if usable for N+R ---")
    cur.execute("""
        SELECT COUNT(*)::int as total,
               COUNT(DISTINCT conductor_id)::int as unique_drivers,
               MIN(fecha_inicio_viaje::date)::text as first,
               MAX(fecha_inicio_viaje::date)::text as last
        FROM public.trips_2026
        WHERE condicion = 'completed'
    """)
    r = cur.fetchone()
    print(f"  Total trips: {r['total']:,}, drivers: {r['unique_drivers']:,}")
    print(f"  Range: {r['first']} to {r['last']}")

    # 8. Best candidate: real_business_slice with active_drivers
    # Check if there's a new_drivers or activation column anywhere
    print("\n--- Searching for activation/new/reactivation columns in ops.* ---")
    cur.execute("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'ops'
          AND (column_name LIKE '%new%' OR column_name LIKE '%activ%'
               OR column_name LIKE '%reactiv%')
        ORDER BY table_name, column_name
    """)
    for c in cur.fetchall():
        print(f"  ops.{c['table_name']}.{c['column_name']} ({c['data_type']})")

    # 9. Check if trips_2025/2026 can resolve first-trip-per-driver
    print("\n--- Approach: derive N+R from trips history ---")
    cur.execute("""
        WITH driver_first_trip AS (
            SELECT conductor_id, MIN(fecha_inicio_viaje::date) as first_trip_date
            FROM public.trips_2026
            WHERE condicion = 'completed'
            GROUP BY conductor_id
        )
        SELECT
            COUNT(*)::int as total_drivers,
            COUNT(*) FILTER (WHERE first_trip_date >= '2026-04-01'
                             AND first_trip_date < '2026-05-01')::int as new_in_april,
            COUNT(*) FILTER (WHERE first_trip_date < '2025-01-01')::int as veteran_before_2025,
            MIN(first_trip_date)::text as earliest,
            MAX(first_trip_date)::text as latest
        FROM driver_first_trip
    """)
    r = cur.fetchone()
    print(f"  trips_2026 driver universe: {r['total_drivers']:,}")
    print(f"    New in April 2026: {r['new_in_april']}")
    print(f"    Veterans (before 2025): {r['veteran_before_2025']:,}")
    print(f"    Range: {r['earliest']} to {r['latest']}")

    # 10. Also check trips_2025 for historical data
    print("\n--- trips_2025 historical check ---")
    cur.execute("""
        SELECT COUNT(DISTINCT conductor_id)::int as drivers,
               MIN(fecha_inicio_viaje::date)::text as first,
               MAX(fecha_inicio_viaje::date)::text as last
        FROM public.trips_2025 WHERE condicion = 'completed'
    """)
    r = cur.fetchone()
    print(f"  Drivers: {r['drivers']:,}, range: {r['first']} to {r['last']}")

    # 11. Reactivated: drivers with trips in current month but NOT in previous window
    # Quick test: reactivated in April 2026 (trips in April, no trips in March)
    print("\n--- Reactivated test: April 2026 drivers (trips April, no trips Feb-March) ---")
    cur.execute("""
        WITH april_drivers AS (
            SELECT DISTINCT conductor_id
            FROM public.trips_2026
            WHERE condicion = 'completed'
              AND fecha_inicio_viaje >= '2026-04-01'
              AND fecha_inicio_viaje < '2026-05-01'
        ),
        prev_drivers AS (
            SELECT DISTINCT conductor_id
            FROM public.trips_2026
            WHERE condicion = 'completed'
              AND fecha_inicio_viaje >= '2026-03-01'
              AND fecha_inicio_viaje < '2026-04-01'
            UNION
            SELECT DISTINCT conductor_id
            FROM public.trips_2025
            WHERE condicion = 'completed'
              AND fecha_inicio_viaje >= '2026-03-01'
              AND fecha_inicio_viaje < '2026-04-01'
        )
        SELECT
            (SELECT COUNT(*) FROM april_drivers)::int as april_total,
            (SELECT COUNT(*) FROM prev_drivers)::int as march_total,
            (SELECT COUNT(*) FROM april_drivers a WHERE a.conductor_id NOT IN (SELECT p.conductor_id FROM prev_drivers p))::int as possible_new_or_returned
    """)
    r = cur.fetchone()
    print(f"  April drivers: {r['april_total']}")
    print(f"  March drivers: {r['march_total']}")
    print(f"  April-not-in-March: {r['possible_new_or_returned']}")

    # 12. cabinet_drivers: hire_date field
    print("\n--- cabinet_drivers hire_date check ---")
    cur.execute("""
        SELECT COUNT(*)::int as total,
               COUNT(*) FILTER (WHERE hire_date IS NOT NULL AND hire_date != '')::int as with_hire_date
        FROM public.module_ct_cabinet_drivers
    """)
    r = cur.fetchone()
    print(f"  Total: {r['total']:,}, with hire_date: {r['with_hire_date']:,} ({r['with_hire_date']/r['total']*100:.1f}%)")

    if r['with_hire_date'] > 0:
        cur.execute("""
            SELECT hire_date, COUNT(*)::int as cnt
            FROM public.module_ct_cabinet_drivers
            WHERE hire_date IS NOT NULL AND hire_date != ''
            GROUP BY hire_date
            ORDER BY hire_date DESC LIMIT 5
        """)
        print(f"  Sample hire_dates:")
        for hd in cur.fetchall():
            print(f"    {hd['hire_date']}: {hd['cnt']}")

    # 13. ops.yango_loyalty_kpi_registry — what source does it use for N_R?
    print("\n--- KPI registry: N_R source definition ---")
    cur.execute("""
        SELECT kpi_code, kpi_name, source_type, source_table, source_query, category
        FROM ops.yango_loyalty_kpi_registry
        WHERE kpi_code = 'N_R'
    """)
    r = cur.fetchone()
    if r:
        print(f"  kpi_code: {r['kpi_code']}")
        print(f"  source_type: {r['source_type']}")
        print(f"  source_table: {r['source_table']}")
        print(f"  source_query: {r['source_query']}")
        print(f"  category: {r['category']}")

    # 14. The existing loyalty service uses mv_driver_lifecycle_monthly_kpis
    # Check if it exists
    print("\n--- mv_driver_lifecycle_* MVs ---")
    cur.execute("""
        SELECT schemaname, matviewname FROM pg_matviews
        WHERE matviewname LIKE '%lifecycle%' OR matviewname LIKE '%driver%'
        ORDER BY matviewname
    """)
    mvs = cur.fetchall()
    for m in mvs:
        print(f"  {m['schemaname']}.{m['matviewname']}")

    print("\n" + "=" * 75)
    print("DISCOVERY COMPLETE")
    print("=" * 75)
