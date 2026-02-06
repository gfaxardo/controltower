"""
[YEGO CT] PASO 3D E2E — Vista Plan vs Real RESUELTO (directo + homologación + trazabilidad).
Crea ops.v_plan_lob_agg (plan_lob_name_norm), ops.v_real_to_plan_lob_resolved,
ops.v_plan_vs_real_lob_check_resolved. Actualiza v_plan_vs_real_lob_check para compatibilidad.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
PASO3D_SQL = os.path.join(SQL_DIR, "paso3d_plan_vs_real_resolved.sql")


def _strip_sql_comments(text: str) -> str:
    """Quita comentarios de línea (-- ...) para no romper split por ';'."""
    out = []
    for line in text.splitlines():
        if "--" in line:
            idx = line.index("--")
            out.append(line[:idx].strip())
        else:
            out.append(line.strip())
    return "\n".join(out)


def main():
    init_db_pool()

    if not os.path.exists(PASO3D_SQL):
        print(f"[ERROR] No encontrado: {PASO3D_SQL}")
        sys.exit(1)

    with open(PASO3D_SQL, "r", encoding="utf-8") as f:
        content = f.read()
    content = _strip_sql_comments(content)
    statements = [s.strip() for s in content.split(";") if s.strip()]

    print("=== PASO 3D — Plan vs Real RESUELTO (directo + homologación) ===\n")
    with get_db() as conn:
        cur = conn.cursor()
        for i, st in enumerate(statements):
            if not st:
                continue
            try:
                cur.execute(st)
                conn.commit()
                print(f"  OK: sentencia {i + 1}")
            except Exception as e:
                print(f"  [ERROR] sentencia {i + 1}: {e}")
                conn.rollback()
        cur.close()

    print("\n=== Validaciones (v_plan_vs_real_lob_check_resolved) ===\n")
    with get_db() as conn:
        cur = conn.cursor()
        # 1) Conteos por coverage_status
        try:
            cur.execute("""
                SELECT coverage_status, COUNT(*)
                FROM ops.v_plan_vs_real_lob_check_resolved
                GROUP BY 1
                ORDER BY 2 DESC
            """)
            by_status = cur.fetchall()
            print("  1) Por coverage_status:")
            for r in by_status:
                print(f"      {r[0]}: {r[1]}")
        except Exception as e:
            print(f"  [ERROR] por status: {e}")
            by_status = []

        # 2) Conteos por resolution_method
        try:
            cur.execute("""
                SELECT resolution_method, COUNT(*)
                FROM ops.v_plan_vs_real_lob_check_resolved
                GROUP BY 1
                ORDER BY 2 DESC
            """)
            by_method = cur.fetchall()
            print("\n  2) Por resolution_method:")
            for r in by_method:
                print(f"      {r[0]}: {r[1]}")
        except Exception as e:
            print(f"  [ERROR] por method: {e}")
            by_method = []

        # 3) Top REAL_ONLY por volumen
        try:
            cur.execute("""
                SELECT country, city, plan_lob_name_norm, real_tipo_servicio,
                       plan_trips, plan_revenue, real_trips, coverage_status, resolution_method
                FROM ops.v_plan_vs_real_lob_check_resolved
                WHERE coverage_status = 'REAL_ONLY'
                ORDER BY real_trips DESC
                LIMIT 30
            """)
            real_only = cur.fetchall()
            print("\n  3) Top REAL_ONLY (real_trips DESC, límite 30):")
            for r in real_only[:10]:
                print(f"      {r}")
            if len(real_only) > 10:
                print(f"      ... y {len(real_only) - 10} más")
        except Exception as e:
            print(f"  [ERROR] REAL_ONLY: {e}")

        # 4) Top PLAN_ONLY por volumen
        try:
            cur.execute("""
                SELECT country, city, plan_lob_name_norm, real_tipo_servicio,
                       plan_trips, plan_revenue, real_trips, coverage_status, resolution_method
                FROM ops.v_plan_vs_real_lob_check_resolved
                WHERE coverage_status = 'PLAN_ONLY'
                ORDER BY plan_trips DESC
                LIMIT 30
            """)
            plan_only = cur.fetchall()
            print("\n  4) Top PLAN_ONLY (plan_trips DESC, límite 30):")
            for r in plan_only[:10]:
                print(f"      {r}")
            if len(plan_only) > 10:
                print(f"      ... y {len(plan_only) - 10} más")
        except Exception as e:
            print(f"  [ERROR] PLAN_ONLY: {e}")

        cur.close()

    # Salida final
    count_ok = next((r[1] for r in by_status if r[0] == "OK"), 0)
    count_homologation = next((r[1] for r in by_method if r[0] == "HOMOLOGATION"), 0)
    print("\n" + "=" * 50)
    if count_ok > 0:
        print("  PASO 3D OK (homologación activa)")
    elif count_ok == 0 and count_homologation == 0:
        print("  PASO 3D: OK=0 y HOMOLOGATION=0 => falta poblar ops.lob_homologation (paso 3E)")
    else:
        print("  PASO 3D: ejecutado; revisar conteos arriba")
    print("=" * 50)


if __name__ == "__main__":
    main()
