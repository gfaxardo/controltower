"""Descubre public.parks: existencia, columnas, 5 filas."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema='public' AND table_name='parks'
        """)
        row = cur.fetchone()
        print("=== 1) Tabla public.parks existe? ===")
        print(f"  {row}\n" if row else "  NO\n")

        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='parks'
            ORDER BY 1
        """)
        cols = cur.fetchall()
        print("=== 2) Columnas ===")
        for r in cols:
            print(f"  {r[0]}: {r[1]}")
        print()

        if not cols:
            return
        col_names = [r[0] for r in cols]
        cur.execute("SELECT * FROM public.parks LIMIT 5")
        rows = cur.fetchall()
        print("=== 3) 5 filas ===")
        for i, row in enumerate(rows, 1):
            print(f"  Fila {i}: " + ", ".join(f"{c}={v!r}" for c, v in zip(col_names, row)))
        cur.close()

if __name__ == "__main__":
    main()
