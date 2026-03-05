#!/usr/bin/env python3
"""
FASE 0 — Mapeo: dim.dim_park y columnas de MVs driver lifecycle para Supply.
Ejecutar: cd backend && python -m scripts.map_dim_park_and_supply_columns
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from app.db.connection import init_db_pool, get_db
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        print("=" * 70)
        print("FASE 0 — MAPEO dim.dim_park y fuentes Supply")
        print("=" * 70)

        # 0.1 dim.dim_park
        print("\n--- 0.1 dim.dim_park (columnas) ---")
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'dim' AND table_name = 'dim_park'
            ORDER BY ordinal_position
        """)
        cols = cur.fetchall()
        for c in cols:
            print(f"  {c['column_name']}: {c['data_type']} (nullable={c['is_nullable']})")

        cur.execute("SELECT COUNT(*) AS n FROM dim.dim_park")
        n = cur.fetchone()["n"]
        print(f"\n  Conteo: {n}")

        print("\n  Ejemplos park_name (10):")
        cur.execute("SELECT park_id, park_name FROM dim.dim_park ORDER BY park_id LIMIT 10")
        for r in cur.fetchall():
            print(f"    {r['park_id']} | {r['park_name']}")

        # ¿Existen city/country?
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'dim' AND table_name = 'dim_park'
            AND column_name IN ('city','country')
        """)
        geo_cols = [r["column_name"] for r in cur.fetchall()]
        print(f"\n  Columnas geo (city, country): {geo_cols or 'NO EXISTEN'}")

        if geo_cols:
            cur.execute("""
                SELECT COUNT(*) AS n_unknown
                FROM dim.dim_park
                WHERE city IS NULL OR TRIM(COALESCE(city,'')) = ''
                   OR country IS NULL OR TRIM(COALESCE(country,'')) = ''
            """)
            n_unknown = cur.fetchone()["n_unknown"]
            print(f"  Filas con city/country vacío o NULL: {n_unknown}")

        # 0.2 mv_driver_weekly_stats (por park)
        print("\n--- 0.2 ops.mv_driver_weekly_stats (columnas para supply) ---")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'mv_driver_weekly_stats'
            ORDER BY ordinal_position
        """)
        for c in cur.fetchall():
            print(f"  {c['column_name']}: {c['data_type']}")

        # 0.3 mv_driver_lifecycle_weekly_kpis (global; sin park)
        print("\n--- 0.3 ops.mv_driver_lifecycle_weekly_kpis (columnas) ---")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'mv_driver_lifecycle_weekly_kpis'
            ORDER BY ordinal_position
        """)
        for c in cur.fetchall():
            print(f"  {c['column_name']}: {c['data_type']}")

        # 0.4 mv_driver_lifecycle_base (para activations/ttf)
        print("\n--- 0.4 ops.mv_driver_lifecycle_base (columnas) ---")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'mv_driver_lifecycle_base'
            ORDER BY ordinal_position
        """)
        for c in cur.fetchall():
            print(f"  {c['column_name']}: {c['data_type']}")

        cur.close()

    print("\n--- DECISIÓN GEO ---")
    print("  dim.dim_park puede no tener city/country fiables.")
    print("  Implementar dim.dim_geo_park (nuevo) con seed manual: backend/seeds/geo_parks_seed.sql")
    print("=" * 70)

if __name__ == "__main__":
    main()
