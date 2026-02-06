"""
[YEGO CT] PASO 3B E2E — Crear agregación REAL rápida por tipo_servicio (MV).
Crea ops.mv_real_tipo_servicio_universe_fast + índices. Validación: top 30 sin timeout.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
PASO3B_SQL = os.path.join(SQL_DIR, "paso3b_mv_real_tipo_servicio_fast.sql")


def main():
    init_db_pool()

    if not os.path.exists(PASO3B_SQL):
        print(f"[ERROR] No encontrado: {PASO3B_SQL}")
        sys.exit(1)

    with open(PASO3B_SQL, "r", encoding="utf-8") as f:
        lines = f.readlines()
    content = "\n".join(
        line[: line.index("--")].strip() if "--" in line else line.strip()
        for line in lines
    )
    statements = [s.strip() for s in content.split(";") if s.strip()]

    print("=== PASO 3B — Crear MV e índices ===\n")
    print("  (Puede tardar si trips_all es muy grande; se ejecuta una sola vez.)\n")
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '600000'")
        except Exception:
            pass
        for i, st in enumerate(statements):
            try:
                cur.execute(st)
                conn.commit()
                print(f"  OK: sentencia {i+1}")
            except Exception as e:
                print(f"  [ERROR] sentencia {i+1}: {e}")
                conn.rollback()
        cur.close()

    print("\n=== Validaciones rápidas ===\n")
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM ops.mv_real_tipo_servicio_universe_fast")
            n = cur.fetchone()[0]
            print(f"  COUNT(*): {n}")
        except Exception as e:
            print(f"  [ERROR] COUNT: {e}")
            n = 0
        try:
            cur.execute("""
                SELECT * FROM ops.mv_real_tipo_servicio_universe_fast
                ORDER BY trips_count DESC
                LIMIT 30
            """)
            rows = cur.fetchall()
            if rows:
                print("  Top 30 (trips_count DESC):")
                for r in rows[:15]:
                    print(f"    {r}")
                if len(rows) > 15:
                    print(f"    ... y {len(rows)-15} más")
        except Exception as e:
            print(f"  [ERROR] top 30: {e}")
            rows = []
        cur.close()

    print("\n" + "="*50)
    if n > 0 and rows is not None and len(rows) > 0:
        print("  PASO 3B OK")
    else:
        print("  PASO 3B: revisar errores (timeout o MV vacía)")
    print("="*50)


if __name__ == "__main__":
    main()
