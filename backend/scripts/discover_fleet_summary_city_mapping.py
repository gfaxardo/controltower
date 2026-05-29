#!/usr/bin/env python3
"""
TAREA 0 Discovery Part 2: Find how to map driver_work_rule_id -> city.
Check dim tables and resolve city mapping for fleet_summary_daily.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 70)
    print("PART 2: City mapping for module_ct_fleet_summary_daily")
    print("=" * 70)

    # 1. Check ops.v_dim_park_resolved columns
    print("\n--- ops.v_dim_park_resolved columns ---")
    try:
        cur.execute("SELECT * FROM ops.v_dim_park_resolved LIMIT 3")
        cols = [desc[0] for desc in cur.description]
        print(f"  Columns: {cols}")
        rows = cur.fetchall()
        for r in rows:
            print(f"  Sample: {dict(r)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 2. Check if driver_work_rule_id matches park_id in dim_park
    print("\n--- Matching driver_work_rule_id to dim_park ---")
    try:
        cur.execute("""
            SELECT COUNT(DISTINCT f.driver_work_rule_id) as total_work_rules,
                   COUNT(DISTINCT CASE WHEN dp.park_id IS NOT NULL THEN f.driver_work_rule_id END) as matched_to_dim_park
            FROM public.module_ct_fleet_summary_daily f
            LEFT JOIN dim.dim_park dp ON dp.park_id = f.driver_work_rule_id
        """)
        result = cur.fetchone()
        print(f"  Total distinct work_rule_ids: {result['total_work_rules']}")
        print(f"  Matched to dim.dim_park.park_id: {result['matched_to_dim_park']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 3. Check distinct driver_work_rule_ids
    print("\n--- Distinct driver_work_rule_id values ---")
    try:
        cur.execute("""
            SELECT driver_work_rule_id, COUNT(DISTINCT driver_id) as drivers, COUNT(*) as rows
            FROM public.module_ct_fleet_summary_daily
            GROUP BY driver_work_rule_id
            ORDER BY drivers DESC
            LIMIT 10
        """)
        for r in cur.fetchall():
            print(f"  {r['driver_work_rule_id']}: {r['drivers']} drivers, {r['rows']} rows")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 4. Try ops.v_dim_park_resolved matching
    print("\n--- Matching work_rule_id to v_dim_park_resolved ---")
    try:
        cur.execute("""
            SELECT COUNT(DISTINCT f.driver_work_rule_id) as total,
                   COUNT(DISTINCT CASE WHEN vp.park_id IS NOT NULL THEN f.driver_work_rule_id END) as matched
            FROM public.module_ct_fleet_summary_daily f
            LEFT JOIN ops.v_dim_park_resolved vp ON vp.park_id = f.driver_work_rule_id
        """)
        result = cur.fetchone()
        print(f"  Matched to v_dim_park_resolved: {result['matched']} / {result['total']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 5. Check if there's a work_rules / work_rule table
    print("\n--- Searching for work_rule related tables ---")
    try:
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name LIKE '%work_rule%'
               OR table_name LIKE '%rule%park%'
               OR table_name LIKE '%park%rule%'
            ORDER BY table_schema, table_name
        """)
        for r in cur.fetchall():
            print(f"  {r['table_schema']}.{r['table_name']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 6. Try matching with park via different dim tables
    print("\n--- Checking dim.dim_park structure for city ---")
    try:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'dim' AND table_name = 'dim_park'
            ORDER BY ordinal_position
        """)
        for r in cur.fetchall():
            print(f"  {r['column_name']} ({r['data_type']})")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 7. Check if there's a driver->park mapping table
    print("\n--- Searching for driver-to-park mapping ---")
    try:
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name LIKE '%driver%park%'
               OR table_name LIKE '%park%driver%'
               OR table_name LIKE '%contractor%'
               OR table_name LIKE '%cabinet%driver%'
            ORDER BY table_schema, table_name
            LIMIT 15
        """)
        for r in cur.fetchall():
            print(f"  {r['table_schema']}.{r['table_name']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 8. Try join via public.module_ct_cabinet_drivers
    print("\n--- public.module_ct_cabinet_drivers columns ---")
    try:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'module_ct_cabinet_drivers'
            ORDER BY ordinal_position
        """)
        for r in cur.fetchall():
            print(f"  {r['column_name']} ({r['data_type']})")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 9. Check if cabinet_drivers has driver_id and park/city
    print("\n--- Testing cabinet_drivers join for city ---")
    try:
        cur.execute("""
            SELECT COUNT(DISTINCT f.driver_id) as total_drivers,
                   COUNT(DISTINCT CASE WHEN cd.driver_id IS NOT NULL THEN f.driver_id END) as matched_cabinet
            FROM public.module_ct_fleet_summary_daily f
            LEFT JOIN public.module_ct_cabinet_drivers cd ON cd.driver_id = f.driver_id
            WHERE f.fecha >= '2026-04-01' AND f.fecha < '2026-05-01'
        """)
        result = cur.fetchone()
        print(f"  April 2026 drivers: {result['total_drivers']}")
        print(f"  Matched to cabinet: {result['matched_cabinet']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 10. Quick test: use dim_park to map work_rule_id -> city
    print("\n--- Attempting work_rule_id -> dim_park -> city mapping ---")
    try:
        cur.execute("""
            SELECT dp.city, COUNT(DISTINCT f.driver_id) as drivers,
                   SUM(f.work_time_hours) as supply_hours
            FROM public.module_ct_fleet_summary_daily f
            JOIN dim.dim_park dp ON dp.park_id = f.driver_work_rule_id
            WHERE f.fecha >= '2026-04-01' AND f.fecha < '2026-05-01'
              AND f.count_orders_completed > 0
            GROUP BY dp.city
            ORDER BY drivers DESC
        """)
        rows = cur.fetchall()
        if rows:
            print("  SUCCESS! work_rule_id maps to dim_park:")
            for r in rows:
                print(f"    {r['city']}: AD={r['drivers']}, SH={r['supply_hours']:.0f}")
        else:
            print("  No results - work_rule_id doesn't match dim_park.park_id")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 11. Alternative: try to find city via cabinet_drivers
    print("\n--- Testing cabinet_drivers for city resolution ---")
    try:
        cur.execute("SELECT * FROM public.module_ct_cabinet_drivers LIMIT 2")
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        print(f"  Columns: {cols}")
        for r in rows:
            # Print just relevant columns
            relevant = {k: v for k, v in dict(r).items() if any(x in k.lower() for x in ['city', 'park', 'driver_id', 'country'])}
            print(f"  {relevant}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    cur.close()
    print(f"\n{'='*70}")
    print("DISCOVERY PART 2 COMPLETE")
    print(f"{'='*70}")
