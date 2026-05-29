#!/usr/bin/env python3
"""
TAREA 0 Discovery Part 3: Resolve work_rule_id -> city mapping.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Check ops.mv_driver_lifecycle_monthly_kpis structure
    print("=" * 70)
    print("1. ops.mv_driver_lifecycle_monthly_kpis columns")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'mv_driver_lifecycle_monthly_kpis'
            ORDER BY ordinal_position
        """)
        for r in cur.fetchall():
            print(f"  {r['column_name']} ({r['data_type']})")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 2. Check ops.real_business_slice_month_fact structure
    print("\n" + "=" * 70)
    print("2. ops.real_business_slice_month_fact columns")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'real_business_slice_month_fact'
            ORDER BY ordinal_position
        """)
        for r in cur.fetchall():
            print(f"  {r['column_name']} ({r['data_type']})")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 3. Check if there's a yango-specific dimension mapping work_rule -> city
    print("\n" + "=" * 70)
    print("3. Searching for park/work_rule/fleet mapping tables")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE (table_name LIKE '%park%' OR table_name LIKE '%fleet%'
                   OR table_name LIKE '%yango%')
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
        """)
        for r in cur.fetchall():
            print(f"  {r['table_schema']}.{r['table_name']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 4. Check ops.geo_parks or similar
    print("\n" + "=" * 70)
    print("4. Checking ops.geo_parks if exists")
    print("=" * 70)
    try:
        cur.execute("SELECT * FROM ops.geo_parks LIMIT 5")
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        print(f"  Columns: {cols}")
        for r in rows:
            print(f"  {dict(r)}")
    except Exception as e:
        print(f"  Not found or error: {e}")
        conn.rollback()

    # 5. Cross-reference: find drivers that are in BOTH fleet_summary AND lifecycle kpis
    print("\n" + "=" * 70)
    print("5. Cross-reference driver_id in fleet_summary with lifecycle/trips tables")
    print("=" * 70)
    try:
        # Check if there's a daily trips table with park_id
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name LIKE '%trips%'
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
        """)
        print("  Tables with 'trips':")
        for r in cur.fetchall():
            print(f"    {r['table_schema']}.{r['table_name']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 6. Look at public.trips_2026 or similar
    print("\n" + "=" * 70)
    print("6. Checking trips_2026 columns for park_id")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'trips_2026'
            ORDER BY ordinal_position
            LIMIT 30
        """)
        for r in cur.fetchall():
            print(f"  {r['column_name']} ({r['data_type']})")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 7. Key insight: since there are only 8 work_rule_ids, let's identify them
    # by cross-referencing with cabinet_drivers which has park_id and park_name
    print("\n" + "=" * 70)
    print("7. Cross-ref work_rule_id with cabinet park_id via driver_id")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT f.driver_work_rule_id,
                   cd.park_name,
                   cd.park_id,
                   COUNT(DISTINCT f.driver_id) as drivers
            FROM public.module_ct_fleet_summary_daily f
            JOIN public.module_ct_cabinet_drivers cd ON cd.driver_id = f.driver_id
            WHERE f.fecha >= '2026-04-01' AND f.fecha < '2026-05-01'
            GROUP BY f.driver_work_rule_id, cd.park_name, cd.park_id
            ORDER BY drivers DESC
            LIMIT 20
        """)
        for r in cur.fetchall():
            print(f"  work_rule={r['driver_work_rule_id'][:12]}... park_name={r['park_name']} park_id={r['park_id'][:12]}... drivers={r['drivers']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 8. Check trips_2026 for park_id -> city resolution
    print("\n" + "=" * 70)
    print("8. Checking trips_2026: driver + park + city resolution")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT f.driver_work_rule_id,
                   t.park_id,
                   dp.city,
                   COUNT(DISTINCT f.driver_id) as drivers
            FROM public.module_ct_fleet_summary_daily f
            JOIN public.trips_2026 t ON t.driver_id = f.driver_id
                AND t.date::date >= '2026-04-01' AND t.date::date < '2026-04-05'
            JOIN dim.dim_park dp ON dp.park_id = t.park_id
            WHERE f.fecha >= '2026-04-01' AND f.fecha < '2026-04-05'
            GROUP BY f.driver_work_rule_id, t.park_id, dp.city
            ORDER BY drivers DESC
            LIMIT 20
        """)
        for r in cur.fetchall():
            print(f"  work_rule={r['driver_work_rule_id'][:12]}... park={r['park_id'][:12]}... city={r['city']} drivers={r['drivers']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 9. Alternative: Simple approach - check if work_rule_id IS a park_id in trips
    print("\n" + "=" * 70)
    print("9. Check if work_rule_id appears as park_id in trips_2026")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT DISTINCT f.driver_work_rule_id,
                   (SELECT dp.city FROM dim.dim_park dp WHERE dp.park_id = f.driver_work_rule_id) as city_if_park
            FROM public.module_ct_fleet_summary_daily f
        """)
        for r in cur.fetchall():
            print(f"  {r['driver_work_rule_id']}: city={r['city_if_park']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 10. Try: get parks from trips that match these drivers
    print("\n" + "=" * 70)
    print("10. Park_ids in trips_2026 for April fleet_summary drivers")
    print("=" * 70)
    try:
        cur.execute("""
            WITH april_drivers AS (
                SELECT DISTINCT driver_id, driver_work_rule_id
                FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= '2026-04-01' AND fecha < '2026-04-02'
            )
            SELECT ad.driver_work_rule_id,
                   t.park_id,
                   dp.city,
                   dp.country,
                   COUNT(DISTINCT ad.driver_id) as driver_count
            FROM april_drivers ad
            JOIN public.trips_2026 t ON t.driver_id = ad.driver_id
                AND t.date::date = '2026-04-01'
            JOIN dim.dim_park dp ON dp.park_id = t.park_id
            GROUP BY ad.driver_work_rule_id, t.park_id, dp.city, dp.country
            ORDER BY driver_count DESC
            LIMIT 15
        """)
        for r in cur.fetchall():
            print(f"  work_rule={r['driver_work_rule_id'][:16]}... park={r['park_id'][:16]}... city={r['city']} country={r['country']} drivers={r['driver_count']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    cur.close()
    print(f"\n{'='*70}")
    print("DISCOVERY PART 3 COMPLETE")
    print(f"{'='*70}")
