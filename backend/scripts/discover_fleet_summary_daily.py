#!/usr/bin/env python3
"""
TAREA 0 Discovery: Inspect public.module_ct_fleet_summary_daily schema and sample data.
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
    print("DISCOVERY: public.module_ct_fleet_summary_daily")
    print("=" * 70)

    # 1. Check if table exists
    cur.execute("""
        SELECT table_schema, table_name, table_type
        FROM information_schema.tables
        WHERE table_name = 'module_ct_fleet_summary_daily'
        ORDER BY table_schema;
    """)
    tables = cur.fetchall()
    if not tables:
        print("\n[ERROR] Table 'module_ct_fleet_summary_daily' NOT FOUND in any schema.")
        print("\nSearching for similar tables...")
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_name LIKE '%fleet_summary%'
               OR table_name LIKE '%module_ct_fleet%'
               OR table_name LIKE '%ct_fleet%'
            ORDER BY table_schema, table_name;
        """)
        similar = cur.fetchall()
        if similar:
            print(f"  Found {len(similar)} similar tables:")
            for t in similar:
                print(f"    {t['table_schema']}.{t['table_name']}")
        else:
            print("  No similar tables found.")

        print("\nSearching tables with 'fleet' or 'supply' in name...")
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE (table_name LIKE '%fleet%' OR table_name LIKE '%supply%'
                   OR table_name LIKE '%driver%daily%')
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
            LIMIT 30;
        """)
        related = cur.fetchall()
        if related:
            for t in related:
                print(f"    {t['table_schema']}.{t['table_name']}")
        sys.exit(1)

    print(f"\n[OK] Found in {len(tables)} schema(s):")
    for t in tables:
        print(f"  {t['table_schema']}.{t['table_name']} ({t['table_type']})")

    target_schema = tables[0]['table_schema']

    # 2. Get all columns
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = 'module_ct_fleet_summary_daily'
        ORDER BY ordinal_position;
    """, (target_schema,))
    columns = cur.fetchall()
    print(f"\n{'='*70}")
    print(f"COLUMNS ({len(columns)} total):")
    print(f"{'='*70}")
    print(f"{'#':<4} {'Column':<40} {'Type':<25} {'Nullable':<10}")
    print("-" * 80)
    for i, col in enumerate(columns, 1):
        print(f"{i:<4} {col['column_name']:<40} {col['data_type']:<25} {col['is_nullable']:<10}")

    # 3. Sample data
    full_table = f"{target_schema}.module_ct_fleet_summary_daily"
    cur.execute(f"SELECT * FROM {full_table} LIMIT 3")
    rows = cur.fetchall()
    print(f"\n{'='*70}")
    print(f"SAMPLE DATA (3 rows):")
    print(f"{'='*70}")
    for i, row in enumerate(rows, 1):
        print(f"\n--- Row {i} ---")
        for k, v in row.items():
            print(f"  {k}: {v}")

    # 4. Data range
    col_names = [c['column_name'] for c in columns]
    date_col = None
    for candidate in ['activity_date', 'date', 'day', 'report_date', 'fecha', 'dt']:
        if candidate in col_names:
            date_col = candidate
            break
    if not date_col:
        date_cols = [c for c in col_names if 'date' in c.lower() or 'day' in c.lower() or 'dt' in c.lower()]
        if date_cols:
            date_col = date_cols[0]

    if date_col:
        cur.execute(f"SELECT MIN({date_col}) as min_date, MAX({date_col}) as max_date, COUNT(*) as total_rows FROM {full_table}")
        stats = cur.fetchone()
        print(f"\n{'='*70}")
        print(f"DATA RANGE (column: {date_col}):")
        print(f"  Min: {stats['min_date']}")
        print(f"  Max: {stats['max_date']}")
        print(f"  Total rows: {stats['total_rows']}")

    # 5. Check for key columns we need
    print(f"\n{'='*70}")
    print("KEY COLUMN MAPPING CHECK:")
    print(f"{'='*70}")
    needed = {
        'driver_id': ['driver_id', 'contractor_id', 'driver_uuid', 'driver'],
        'date': ['activity_date', 'date', 'day', 'report_date', 'dt'],
        'country': ['country', 'country_code', 'pais'],
        'city': ['city', 'city_norm', 'ciudad', 'city_name'],
        'park/fleet': ['park', 'park_id', 'fleet', 'partner', 'partner_key', 'fleet_key'],
        'trips': ['completed_trips', 'trips', 'orders_completed', 'completados', 'rides'],
        'supply_hours': ['supply_hours', 'online_hours', 'active_hours', 'hours_online', 'sh'],
        'new_driver': ['new_driver', 'is_new', 'lifecycle', 'first_trip_date', 'is_new_driver'],
        'reactivated': ['reactivated', 'is_reactivated', 'reactivation'],
    }
    for concept, candidates in needed.items():
        found = [c for c in candidates if c in col_names]
        if found:
            print(f"  {concept:<15} -> FOUND: {', '.join(found)}")
        else:
            partial = [c for c in col_names if any(cand in c.lower() for cand in [concept.split('/')[0].lower()])]
            if partial:
                print(f"  {concept:<15} -> PARTIAL MATCH: {', '.join(partial[:3])}")
            else:
                print(f"  {concept:<15} -> NOT FOUND")

    # 6. Distinct cities and countries
    city_col = None
    for c in ['city_norm', 'city', 'ciudad', 'city_name']:
        if c in col_names:
            city_col = c
            break
    country_col = None
    for c in ['country', 'country_code', 'pais']:
        if c in col_names:
            country_col = c
            break

    if city_col:
        cur.execute(f"SELECT DISTINCT {city_col} FROM {full_table} ORDER BY 1")
        cities = [r[city_col] for r in cur.fetchall()]
        print(f"\n  Cities ({city_col}): {cities[:20]}")

    if country_col:
        cur.execute(f"SELECT DISTINCT {country_col} FROM {full_table} ORDER BY 1")
        countries = [r[country_col] for r in cur.fetchall()]
        print(f"  Countries ({country_col}): {countries[:10]}")

    # 7. Quick AD/SH count for April 2026 if possible
    if date_col and city_col:
        driver_col = None
        for c in ['driver_id', 'contractor_id', 'driver_uuid', 'driver']:
            if c in col_names:
                driver_col = c
                break
        sh_col = None
        for c in ['supply_hours', 'online_hours', 'active_hours', 'hours_online']:
            if c in col_names:
                sh_col = c
                break

        if driver_col:
            print(f"\n{'='*70}")
            print(f"QUICK VALIDATION: April 2026 AD by city")
            print(f"  (driver_col={driver_col}, date_col={date_col}, city_col={city_col})")
            cur.execute(f"""
                SELECT {city_col},
                       COUNT(DISTINCT {driver_col}) as active_drivers,
                       {'SUM(' + sh_col + ') as supply_hours,' if sh_col else ''}
                       COUNT(*) as rows
                FROM {full_table}
                WHERE {date_col} >= '2026-04-01' AND {date_col} < '2026-05-01'
                GROUP BY {city_col}
                ORDER BY COUNT(DISTINCT {driver_col}) DESC
            """)
            april = cur.fetchall()
            for row in april:
                print(f"  {row}")

    cur.close()
    print(f"\n{'='*70}")
    print("DISCOVERY COMPLETE")
    print(f"{'='*70}")
