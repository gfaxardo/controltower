"""Ejecuta inventario de columnas: trips_all y yego_integral.parks (PASO 3D)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        print("=== 1) trips_all (columnas park/tipo_servicio/fecha) ===")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'trips_all'
              AND (column_name ILIKE '%%park%%' OR column_name ILIKE '%%tipo_serv%%'
                   OR column_name ILIKE '%%fecha%%' OR column_name ILIKE '%%start%%' OR column_name ILIKE '%%inicio%%')
            ORDER BY 1
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
        print("\n=== 2) Schemas/tablas con 'park' o 'integral' ===")
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
              AND (table_schema ILIKE '%%integral%%' OR table_schema ILIKE '%%yego%%' OR table_name ILIKE '%%park%%')
            ORDER BY 1, 2
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}.{row[1]}")
        print("\n=== 3) yego_integral.parks (columnas) ===")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'yego_integral' AND table_name = 'parks'
            ORDER BY 1
        """)
        rows = cur.fetchall()
        if not rows:
            print("  (tabla no encontrada)")
        for row in rows:
            print(f"  {row[0]}: {row[1]}")
        print("\n=== 4) public.parks (columnas) ===")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'parks'
            ORDER BY 1
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
        print("\n=== 5) dim.dim_park (columnas) ===")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'dim' AND table_name = 'dim_park'
            ORDER BY 1
        """)
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
        cur.close()

if __name__ == "__main__":
    main()
