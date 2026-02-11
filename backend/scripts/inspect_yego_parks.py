"""
Inspección de parks (yego_integral.parks o public.parks): columnas, 5 filas, caso park_id Cali.
Misma BD donde está trips_all.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def inspect_parks(cur, schema: str, table: str = "parks"):
    qual = f"{schema}.{table}"
    print(f"=== {qual} ===\n")
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, (schema, table))
    rows = cur.fetchall()
    if not rows:
        print(f"  (tabla no encontrada)\n")
        return
    cols = [r[0] for r in rows]
    print("  Columnas:", [f"{r[0]} ({r[1]})" for r in rows])
    cur.execute(f'SELECT * FROM "{schema}"."{table}" LIMIT 5')
    five = cur.fetchall()
    print(f"  5 filas:")
    for i, row in enumerate(five, 1):
        print(f"    Fila {i}: " + ", ".join(f"{c}={v!r}" for c, v in zip(cols, row)))
    # Caso Cali
    pk_col = "id" if "id" in cols else "park_id"
    cur.execute(f'SELECT * FROM "{schema}"."{table}" WHERE "{pk_col}" = %s', ("05b1c831e66f41a9a87f5f3fa0a186ae",))
    one = cur.fetchone()
    if one:
        print(f"  Park Cali ({pk_col}=05b1c8...): " + ", ".join(f"{c}={v!r}" for c, v in zip(cols, one)))
    else:
        print(f"  Park Cali: no encontrado con {pk_col}=05b1c831e66f41a9a87f5f3fa0a186ae")
    print()
    return cols

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()

        print("=== 1) Schemas existentes (con 'yego' o 'public') ===\n")
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name IN ('yego_integral', 'public')
            ORDER BY 1
        """)
        for r in cur.fetchall():
            print(f"  {r[0]}")

        print("\n=== 2) Tabla parks (yego_integral o public) ===\n")
        for schema in ("yego_integral", "public"):
            cur.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'parks'
            """, (schema,))
            if cur.fetchone():
                inspect_parks(cur, schema)
                break
        else:
            print("  No existe ni yego_integral.parks ni public.parks.")
            print("  Ejecuta: CREATE SCHEMA IF NOT EXISTS yego_integral; y crea/mueve la tabla parks ahí.\n")

        cur.close()

if __name__ == "__main__":
    main()
