#!/usr/bin/env python3
"""
TAREA 0 Discovery Part 4: Resolve city mapping definitively.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. April AD per work_rule_id (with completed > 0 filter)
    print("=" * 70)
    print("1. April 2026 AD per work_rule_id (completed > 0)")
    print("=" * 70)
    cur.execute("""
        SELECT driver_work_rule_id,
               COUNT(DISTINCT driver_id) as active_drivers,
               SUM(work_time_hours) as supply_hours,
               SUM(count_orders_completed) as trips
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
          AND count_orders_completed > 0
        GROUP BY driver_work_rule_id
        ORDER BY active_drivers DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['driver_work_rule_id']}: AD={r['active_drivers']}, SH={float(r['supply_hours']):.0f}, Trips={r['trips']}")

    # 2. Check trips_2026 with conductor_id matching driver_id
    print("\n" + "=" * 70)
    print("2. trips_2026 matching via conductor_id")
    print("=" * 70)
    try:
        cur.execute("""
            WITH sample_drivers AS (
                SELECT DISTINCT driver_id, driver_work_rule_id
                FROM public.module_ct_fleet_summary_daily
                WHERE fecha = '2026-04-01'
                LIMIT 100
            )
            SELECT sd.driver_work_rule_id, t.park_id,
                   COUNT(DISTINCT sd.driver_id) as matched
            FROM sample_drivers sd
            JOIN public.trips_2026 t ON t.conductor_id = sd.driver_id
                AND t.fecha_inicio_viaje::date = '2026-04-01'
            GROUP BY sd.driver_work_rule_id, t.park_id
            ORDER BY matched DESC
            LIMIT 10
        """)
        for r in cur.fetchall():
            print(f"  work_rule={r['driver_work_rule_id'][:16]}... park_id={r['park_id']} matched={r['matched']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 3. Check dim.dim_geo_park
    print("\n" + "=" * 70)
    print("3. dim.dim_geo_park columns")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'dim' AND table_name = 'dim_geo_park'
            ORDER BY ordinal_position
        """)
        for r in cur.fetchall():
            print(f"  {r['column_name']} ({r['data_type']})")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 4. Check dim.dim_geo_park data
    print("\n" + "=" * 70)
    print("4. dim.dim_geo_park sample data")
    print("=" * 70)
    try:
        cur.execute("SELECT * FROM dim.dim_geo_park LIMIT 10")
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        print(f"  Columns: {cols}")
        for r in rows:
            print(f"  {dict(r)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 5. Check ops.stg_park_territory
    print("\n" + "=" * 70)
    print("5. ops.stg_park_territory")
    print("=" * 70)
    try:
        cur.execute("SELECT * FROM ops.stg_park_territory LIMIT 10")
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        print(f"  Columns: {cols}")
        for r in rows:
            print(f"  {dict(r)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 6. Match trips_2026 conductor_id -> park_id -> dim_park -> city
    print("\n" + "=" * 70)
    print("6. Full chain: fleet_summary driver -> trips conductor -> park -> city")
    print("=" * 70)
    try:
        cur.execute("""
            WITH april_drivers AS (
                SELECT DISTINCT driver_id, driver_work_rule_id
                FROM public.module_ct_fleet_summary_daily
                WHERE fecha = '2026-04-15'
                  AND count_orders_completed > 0
            )
            SELECT ad.driver_work_rule_id,
                   dp.city,
                   COUNT(DISTINCT ad.driver_id) as drivers
            FROM april_drivers ad
            JOIN public.trips_2026 t ON t.conductor_id = ad.driver_id
                AND t.fecha_inicio_viaje::date = '2026-04-15'
                AND t.condicion = 'completed'
            JOIN dim.dim_park dp ON dp.park_id = t.park_id
            GROUP BY ad.driver_work_rule_id, dp.city
            ORDER BY drivers DESC
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"  work_rule={r['driver_work_rule_id'][:16]}... city={r['city']} drivers={r['drivers']}")
        else:
            print("  No results")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 7. Alternative: check if there's a direct mapping known somewhere
    # The work_rule_ids might just BE city identifiers in Yango's system
    # Let's check April totals vs reference values
    print("\n" + "=" * 70)
    print("7. April totals (ALL drivers, completed>0) vs reference")
    print("=" * 70)
    cur.execute("""
        SELECT COUNT(DISTINCT driver_id) as total_ad,
               SUM(work_time_hours) as total_sh
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
          AND count_orders_completed > 0
    """)
    r = cur.fetchone()
    print(f"  Total AD (completed>0): {r['total_ad']}")
    print(f"  Total SH (completed>0): {float(r['total_sh']):.0f}")
    print(f"  Reference total: AD~{5601+550+269}={5601+550+269}, SH~{357000+20127+12735}={357000+20127+12735}")

    # 8. Full April with ALL rows (including 0 completed)
    print("\n" + "=" * 70)
    print("8. April totals (ALL drivers, no filter)")
    print("=" * 70)
    cur.execute("""
        SELECT COUNT(DISTINCT driver_id) as total_ad,
               SUM(work_time_hours) as total_sh
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
    """)
    r = cur.fetchone()
    print(f"  Total AD (all): {r['total_ad']}")
    print(f"  Total SH (all): {float(r['total_sh']):.0f}")

    # 9. Check dim_geo_park if it maps work_rule_id
    print("\n" + "=" * 70)
    print("9. Check if any table has these 8 work_rule_ids with city labels")
    print("=" * 70)
    work_rules = []
    cur.execute("SELECT DISTINCT driver_work_rule_id FROM public.module_ct_fleet_summary_daily")
    work_rules = [r['driver_work_rule_id'] for r in cur.fetchall()]
    print(f"  Work rules: {work_rules}")

    # Try dim_geo_park
    try:
        cur.execute("""
            SELECT * FROM dim.dim_geo_park
            WHERE park_id = ANY(%s)
        """, (work_rules,))
        rows = cur.fetchall()
        if rows:
            print("  MATCH in dim_geo_park:")
            for r in rows:
                print(f"    {dict(r)}")
        else:
            print("  No match in dim_geo_park")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # Try stg_park_territory
    try:
        cur.execute("""
            SELECT * FROM ops.stg_park_territory
            WHERE park_id = ANY(%s)
        """, (work_rules,))
        rows = cur.fetchall()
        if rows:
            print("  MATCH in stg_park_territory:")
            for r in rows:
                print(f"    {dict(r)}")
        else:
            print("  No match in stg_park_territory")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    cur.close()
    print(f"\n{'='*70}")
    print("DISCOVERY PART 4 COMPLETE")
    print(f"{'='*70}")
