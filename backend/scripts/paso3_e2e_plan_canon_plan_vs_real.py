"""
[YEGO CT] PASO 3 E2E — Plan canónico en DB + Plan vs Real por LOB.
Ejecuta SQL (plan.plan_lob_long, lob_catalog, v_plan_vs_real_lob_check) y validaciones.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")
PASO3_SQL = os.path.join(SQL_DIR, "paso3_plan_canon_and_plan_vs_real.sql")

def run(cur, conn, sql, desc=""):
    try:
        cur.execute(sql)
        if sql.strip().upper().startswith("SELECT"):
            return cur.fetchall()
        return []
    except Exception as e:
        print(f"  [ERROR] {desc}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return None

def main():
    init_db_pool()

    # Ejecutar SQL del PASO 3 (sentencia por sentencia, omitir comentarios)
    print("=== PASO 3 — Ejecutando SQL ===\n")
    if not os.path.exists(PASO3_SQL):
        print(f"  [ERROR] No encontrado: {PASO3_SQL}")
        sys.exit(1)
    with open(PASO3_SQL, "r", encoding="utf-8") as f:
        content = f.read()
    # Quitar comentarios -- y bloques /* */
    lines = []
    for line in content.split("\n"):
        if "/*" in line:
            continue
        if "--" in line:
            line = line[: line.index("--")].strip()
        else:
            line = line.strip()
        if line:
            lines.append(line)
    full_sql = " ".join(lines)
    # Dividir por ; (sentencias)
    statements = [s.strip() for s in full_sql.split(";") if s.strip() and not s.strip().upper().startswith("/*")]
    with get_db() as conn:
        cur = conn.cursor()
        for st in statements:
            if not st:
                continue
            try:
                cur.execute(st)
            except Exception as e:
                print(f"  [ERROR] SQL: {e}")
                conn.rollback()
            else:
                conn.commit()
        cur.close()

    print("  SQL ejecutado.\n")

    # Validaciones
    print("=== Validaciones ===\n")
    with get_db() as conn:
        cur = conn.cursor()

        r = run(cur, conn, "SELECT COUNT(*) FROM plan.plan_lob_long", "plan_lob_long count")
        count_long = r[0][0] if r else 0
        print(f"  1) plan.plan_lob_long: {count_long} filas")
        r = run(cur, conn, "SELECT MIN(period_date), MAX(period_date) FROM plan.plan_lob_long", "period range")
        if r and r[0][0]:
            print(f"     min_period: {r[0][0]}, max_period: {r[0][1]}")

        r = run(cur, conn, "SELECT COUNT(*) FROM ops.lob_catalog WHERE source='plan'", "lob_catalog plan")
        count_catalog = r[0][0] if r else 0
        print(f"  2) ops.lob_catalog (source=plan): {count_catalog}")
        r = run(cur, conn, """
            SELECT lob_name, country, city, COUNT(*) c
            FROM ops.lob_catalog WHERE source='plan'
            GROUP BY 1,2,3 ORDER BY c DESC LIMIT 10
        """, "sample catalog")
        if r:
            for row in r[:5]:
                print(f"     {row[0]} | {row[1]} | {row[2]} | {row[3]}")

        r = run(cur, conn, """
            SELECT coverage_status, COUNT(*)
            FROM ops.v_plan_vs_real_lob_check
            GROUP BY 1 ORDER BY 2 DESC
        """, "coverage_status")
        print(f"  3) Cobertura (v_plan_vs_real_lob_check):")
        if r:
            for row in r:
                print(f"     {row[0]}: {row[1]}")
        else:
            print("     (sin datos o vista no disponible)")

        r = run(cur, conn, """
            SELECT * FROM ops.v_plan_vs_real_lob_check
            ORDER BY coverage_status, plan_trips DESC
            LIMIT 15
        """, "sample view")
        if r:
            print("     Sample filas (country, city, lob_name_norm, plan_trips, real_trips, coverage_status):")
            for row in r[:5]:
                print(f"       {row[:6]}...")

        cur.close()

    # Criterio de éxito: plan_lob_long > 0, lob_catalog(plan) > 0, vista creada
    view_exists = False
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 1 FROM information_schema.views
                WHERE table_schema = 'ops' AND table_name = 'v_plan_vs_real_lob_check'
            """)
            view_exists = cur.fetchone() is not None
            cur.close()
    except Exception:
        pass
    print("\n" + "="*60)
    if count_long > 0 and count_catalog > 0 and view_exists:
        print("  PASO 3 OK")
        print(f"  - plan.plan_lob_long: {count_long} filas")
        print(f"  - ops.lob_catalog(source='plan'): {count_catalog}")
        print("  - ops.v_plan_vs_real_lob_check creada (puede dar timeout al consultar si trips_all es muy grande)")
    else:
        print("  PASO 3: revisar errores arriba.")
        if count_long == 0:
            print("  - plan.plan_lob_long vacío")
        if count_catalog == 0:
            print("  - ops.lob_catalog(source='plan') vacío")
        if not view_exists:
            print("  - vista v_plan_vs_real_lob_check no existe")
    print("="*60)

if __name__ == "__main__":
    main()
