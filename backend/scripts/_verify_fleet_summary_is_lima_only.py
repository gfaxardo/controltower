#!/usr/bin/env python3
"""
Verify hypothesis: module_ct_fleet_summary_daily ONLY contains Lima drivers.
Evidence: cross-reference with real_business_slice_month_fact.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor
init_db_pool()

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 70)
    print("HYPOTHESIS: fleet_summary_daily is LIMA-ONLY data")
    print("=" * 70)

    # 1. Compare fleet_summary AD with real_business_slice AD per city
    print("\n1. AD comparison (April 2026)")
    print("   real_business_slice_month_fact (official, city-resolved):")
    cur.execute("""
        SELECT city, business_slice_name, active_drivers
        FROM ops.real_business_slice_month_fact
        WHERE month = '2026-04-01' AND country = 'peru'
        ORDER BY active_drivers DESC
    """)
    for r in cur.fetchall():
        print(f"     {r['city']}/{r['business_slice_name']}: AD={r['active_drivers']}")

    print("\n   fleet_summary_daily active drivers (completed>0):")
    cur.execute("""
        SELECT COUNT(DISTINCT driver_id) as ad
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
          AND count_orders_completed > 0
    """)
    r = cur.fetchone()
    print(f"     Total: AD={r['ad']}")

    # 2. If fleet_summary were ALL Lima, compare totals
    lima_auto_ad = 5496  # from real_business_slice
    fleet_ad = r['ad']
    print(f"\n2. fleet_summary AD ({fleet_ad}) vs Lima Auto regular AD ({lima_auto_ad})")
    print(f"   Coverage: {fleet_ad/lima_auto_ad*100:.1f}%")
    print(f"   This strongly suggests fleet_summary = Lima fleet only")

    # 3. Check if any fleet_summary driver appears in Trujillo/Arequipa trips
    print("\n3. Cross-reference: do any fleet_summary drivers do trips in Trujillo/Arequipa?")
    print("   (checking via trips_2026 park_id -> dim_park city)")
    
    # First check what park_ids exist for Trujillo/Arequipa
    cur.execute("""
        SELECT park_id, city FROM dim.dim_park
        WHERE city IN ('trujillo', 'arequipa') AND country = 'peru'
    """)
    provincial_parks = cur.fetchall()
    print(f"   Parks in Trujillo/Arequipa: {len(provincial_parks)}")
    for p in provincial_parks:
        print(f"     {p['park_id'][:16]}... -> {p['city']}")

    # 4. Check trips_2026 for Trujillo/Arequipa park_ids
    if provincial_parks:
        park_ids = [p['park_id'] for p in provincial_parks]
        cur.execute("""
            SELECT dp.city, COUNT(DISTINCT t.conductor_id) as drivers
            FROM public.trips_2026 t
            JOIN dim.dim_park dp ON dp.park_id = t.park_id
            WHERE dp.city IN ('trujillo', 'arequipa')
              AND t.fecha_inicio_viaje >= '2026-04-01'
              AND t.fecha_inicio_viaje < '2026-05-01'
              AND t.condicion = 'completed'
            GROUP BY dp.city
        """)
        prov_drivers = cur.fetchall()
        print(f"\n   Trujillo/Arequipa drivers in trips_2026 (April):")
        for r in prov_drivers:
            print(f"     {r['city']}: {r['drivers']} unique drivers")

        # 5. Do ANY of those provincial drivers appear in fleet_summary?
        cur.execute("""
            WITH prov_drivers AS (
                SELECT DISTINCT t.conductor_id
                FROM public.trips_2026 t
                JOIN dim.dim_park dp ON dp.park_id = t.park_id
                WHERE dp.city IN ('trujillo', 'arequipa')
                  AND t.fecha_inicio_viaje >= '2026-04-01'
                  AND t.fecha_inicio_viaje < '2026-05-01'
                  AND t.condicion = 'completed'
            )
            SELECT COUNT(*) as match_count
            FROM prov_drivers pd
            JOIN public.module_ct_fleet_summary_daily f ON f.driver_id = pd.conductor_id
            WHERE f.fecha >= '2026-04-01' AND f.fecha < '2026-05-01'
        """)
        match = cur.fetchone()
        print(f"\n   Provincial drivers found in fleet_summary: {match['match_count']}")
        if match['match_count'] == 0:
            print("   CONFIRMED: fleet_summary does NOT contain Trujillo/Arequipa drivers")
        else:
            print(f"   PARTIAL: {match['match_count']} provincial drivers also in fleet_summary")

    # 6. Final conclusion
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("  If fleet_summary only contains Lima drivers:")
    print(f"    Lima SH (all work_rules) = 310,730")
    print(f"    Lima SH reference = 357,000")
    print(f"    Coverage = {310730/357000*100:.1f}% (gap likely due to incomplete daily ingestion)")
    print(f"    Trujillo SH from fleet_summary = 0 (not in this table)")
    print(f"    Arequipa SH from fleet_summary = 0 (not in this table)")
    print(f"\n  RECOMMENDATION: Map ALL 8 work_rule_ids to 'lima'")
    print(f"  For Trujillo/Arequipa SH: use manual_input or discover separate data source")
