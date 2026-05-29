#!/usr/bin/env python3
"""
TAREA 0 Discovery Final: Compare sources and determine best path.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. ops.real_business_slice_month_fact for April 2026 Peru
    print("=" * 70)
    print("1. ops.real_business_slice_month_fact - April 2026 Peru")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT city, 
                   SUM(active_drivers) as active_drivers,
                   SUM(trips_completed) as trips_completed
            FROM ops.real_business_slice_month_fact
            WHERE month = '2026-04-01'
              AND country = 'peru'
            GROUP BY city
            ORDER BY SUM(active_drivers) DESC
        """)
        for r in cur.fetchall():
            print(f"  {r['city']}: AD={r['active_drivers']}, Trips={r['trips_completed']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 2. Check if mv_driver_lifecycle_monthly_kpis exists
    print("\n" + "=" * 70)
    print("2. Check if mv_driver_lifecycle_monthly_kpis exists")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_name LIKE '%driver_lifecycle%'
            ORDER BY table_schema, table_name
        """)
        for r in cur.fetchall():
            print(f"  {r['table_schema']}.{r['table_name']} ({r['table_type']})")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 3. Check for supply_hours in any ops view/table
    print("\n" + "=" * 70)
    print("3. Tables/views with supply or hours columns in ops schema")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'ops'
              AND (column_name LIKE '%supply%' OR column_name LIKE '%hours%'
                   OR column_name LIKE '%work_time%' OR column_name LIKE '%online%')
            ORDER BY table_name, column_name
        """)
        for r in cur.fetchall():
            print(f"  {r['table_name']}.{r['column_name']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 4. fleet_summary SH totals per work_rule (without completed>0 filter)
    print("\n" + "=" * 70)
    print("4. Fleet summary April SH per work_rule (NO completed>0 filter)")
    print("=" * 70)
    cur.execute("""
        SELECT driver_work_rule_id,
               COUNT(DISTINCT driver_id) as total_drivers,
               SUM(work_time_hours) as supply_hours
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
        GROUP BY driver_work_rule_id
        ORDER BY supply_hours DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['driver_work_rule_id']}: drivers={r['total_drivers']}, SH={float(r['supply_hours']):.0f}")

    # 5. Create a work_rule -> city hypothesis
    # Based on reference: Lima AD~5601, Trujillo AD~550, Arequipa AD~269
    # Sum of top 4 work_rules (completed>0): 2440+1025+912+592 = 4969 (close to Lima 5601?)
    # Could work_rules 5 & 6 (70+48=118) map to small cities?
    # Actually sum total = 5087, reference total = 6420 → big gap
    print("\n" + "=" * 70)
    print("5. Hypothesis: check if trips_2026 has MORE drivers than fleet_summary")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT COUNT(DISTINCT conductor_id) as unique_drivers
            FROM public.trips_2026
            WHERE fecha_inicio_viaje >= '2026-04-01' AND fecha_inicio_viaje < '2026-05-01'
              AND condicion = 'completed'
        """)
        r = cur.fetchone()
        print(f"  trips_2026 April completed unique drivers: {r['unique_drivers']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 6. Check how real_business_slice calculates active_drivers
    # It might use a different definition
    print("\n" + "=" * 70)
    print("6. real_business_slice_month_fact total Peru April")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT SUM(active_drivers) as total_ad,
                   SUM(trips_completed) as total_trips,
                   COUNT(*) as rows
            FROM ops.real_business_slice_month_fact
            WHERE month = '2026-04-01'
              AND country = 'peru'
        """)
        r = cur.fetchone()
        print(f"  Total AD (all slices): {r['total_ad']}, Trips: {r['total_trips']}, Rows: {r['rows']}")
        print("  NOTE: AD might double-count across business_slices!")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 7. Check by business_slice_name to understand granularity
    print("\n" + "=" * 70)
    print("7. real_business_slice_month_fact breakdown April Peru")
    print("=" * 70)
    try:
        cur.execute("""
            SELECT city, business_slice_name, fleet_display_name,
                   active_drivers, trips_completed
            FROM ops.real_business_slice_month_fact
            WHERE month = '2026-04-01'
              AND country = 'peru'
            ORDER BY active_drivers DESC
        """)
        for r in cur.fetchall():
            print(f"  {r['city']}/{r['business_slice_name']}/{r['fleet_display_name']}: AD={r['active_drivers']}, Trips={r['trips_completed']}")
    except Exception as e:
        print(f"  ERROR: {e}")
        conn.rollback()

    # 8. What if we use work_time_hours without completed>0 filter for SH?
    print("\n" + "=" * 70)
    print("8. Fleet summary April: SH with different AD definitions")
    print("=" * 70)
    cur.execute("""
        SELECT 
            COUNT(DISTINCT driver_id) as ad_all,
            COUNT(DISTINCT CASE WHEN count_orders_completed > 0 THEN driver_id END) as ad_completed,
            SUM(work_time_hours) as sh_all,
            SUM(CASE WHEN count_orders_completed > 0 THEN work_time_hours ELSE 0 END) as sh_completed_only
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
    """)
    r = cur.fetchone()
    print(f"  AD (all connected): {r['ad_all']}")
    print(f"  AD (completed>0): {r['ad_completed']}")
    print(f"  SH (all): {float(r['sh_all']):.0f}")
    print(f"  SH (only days with completions): {float(r['sh_completed_only']):.0f}")

    # 9. Check date coverage in fleet_summary for April
    print("\n" + "=" * 70)
    print("9. Fleet summary April date coverage")
    print("=" * 70)
    cur.execute("""
        SELECT fecha, COUNT(DISTINCT driver_id) as drivers, SUM(work_time_hours) as sh
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
        GROUP BY fecha
        ORDER BY fecha
    """)
    rows = cur.fetchall()
    print(f"  Days covered: {len(rows)} / 30")
    if rows:
        print(f"  First: {rows[0]['fecha']}, Last: {rows[-1]['fecha']}")
        print(f"  Sample days:")
        for r in rows[:5]:
            print(f"    {r['fecha']}: drivers={r['drivers']}, SH={float(r['sh']):.0f}")

    cur.close()
    print(f"\n{'='*70}")
    print("DISCOVERY FINAL COMPLETE")
    print(f"{'='*70}")
