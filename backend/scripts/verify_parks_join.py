"""
PASO 3D — Verificar tipos de columnas y que la vista devuelve filas.
Ejecutar después de: alembic upgrade head (030)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '120s'")

        print("=== 1) Tipo trips_all.park_id ===\n")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'trips_all' AND column_name = 'park_id'
        """)
        for r in cur.fetchall():
            print(f"  {r[0]}: {r[1]}")
        if not cur.rowcount:
            print("  (no encontrado)")

        print("\n=== 2) Tipo parks.city ===\n")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'parks' AND column_name = 'city'
        """)
        for r in cur.fetchall():
            print(f"  {r[0]}: {r[1]}")
        if not cur.rowcount:
            print("  (no encontrado)")

        print("\n=== 3) COUNT vista ===\n")
        cur.execute("SELECT COUNT(*) FROM ops.v_real_universe_by_park_for_hunt")
        n = cur.fetchone()[0]
        print(f"  Filas: {n}")

        print("\n=== 4) Top 20 vista ===\n")
        cur.execute("""
            SELECT park_id, park_name, country, city, real_tipo_servicio, real_trips
            FROM ops.v_real_universe_by_park_for_hunt
            ORDER BY real_trips DESC NULLS LAST
            LIMIT 20
        """)
        for r in cur.fetchall():
            print(f"  {r[1]!r} | {r[3]} | {r[4]!r} | {r[5]}")
        cur.close()

if __name__ == "__main__":
    main()
