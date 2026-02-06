"""
[YEGO CT] PASO 3C E2E — Crear ops.v_plan_vs_real_lob_check (match directo).
Usa plan.plan_lob_long y ops.mv_real_tipo_servicio_universe_fast.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
PASO3C_SQL = os.path.join(SQL_DIR, "paso3c_plan_vs_real_lob_check.sql")


def main():
    init_db_pool()

    if not os.path.exists(PASO3C_SQL):
        print(f"[ERROR] No encontrado: {PASO3C_SQL}")
        sys.exit(1)

    with open(PASO3C_SQL, "r", encoding="utf-8") as f:
        lines = f.readlines()
    content = "\n".join(
        line[: line.index("--")].strip() if "--" in line else line.strip()
        for line in lines
    )
    statements = [s.strip() for s in content.split(";") if s.strip()]

    print("=== PASO 3C — Crear v_plan_lob_agg y v_plan_vs_real_lob_check ===\n")
    with get_db() as conn:
        cur = conn.cursor()
        for i, st in enumerate(statements):
            try:
                cur.execute(st)
                conn.commit()
                print(f"  OK: sentencia {i+1}")
            except Exception as e:
                print(f"  [ERROR] sentencia {i+1}: {e}")
                conn.rollback()
        cur.close()

    print("\n=== Validaciones ===\n")
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT coverage_status, COUNT(*)
                FROM ops.v_plan_vs_real_lob_check
                GROUP BY 1
                ORDER BY 2 DESC
            """)
            rows = cur.fetchall()
            print("  coverage_status, COUNT(*):")
            for r in rows:
                print(f"    {r[0]}: {r[1]}")
        except Exception as e:
            print(f"  [ERROR] cobertura: {e}")
            rows = []
        try:
            cur.execute("""
                SELECT *
                FROM ops.v_plan_vs_real_lob_check
                ORDER BY coverage_status, plan_trips DESC
                LIMIT 60
            """)
            sample = cur.fetchall()
            if sample:
                print("\n  Sample (primeras 10 filas):")
                for r in sample[:10]:
                    print(f"    {r}")
        except Exception as e:
            print(f"  [ERROR] sample: {e}")
        cur.close()

    has_ok = any(r[0] == 'OK' for r in rows) if rows else False
    has_plan_only = any(r[0] == 'PLAN_ONLY' for r in rows) if rows else False
    has_real_only = any(r[0] == 'REAL_ONLY' for r in rows) if rows else False
    print("\n" + "="*50)
    if rows and (has_ok or has_plan_only or has_real_only):
        print("  PASO 3C OK")
    else:
        print("  PASO 3C: revisar errores o timeout")
    print("="*50)


if __name__ == "__main__":
    main()
