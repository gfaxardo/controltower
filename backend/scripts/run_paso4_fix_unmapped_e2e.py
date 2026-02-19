"""
PASO 4 FIX UNMAPPED E2E — Vista con city/country keys → export utf-8-sig → carga → validaciones.
a) Recrear vista (alembic upgrade head)
b) Export listas (export_lob_hunt_lists.py)
c) Carga + paso4 (load_lob_homologation_final + run_paso4_e2e validaciones)
d) Resumen: total template, insertadas, UNMAPPED count, top 10 variances.
statement_timeout = 600s en conexiones del runner.
"""
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
CSV_TEMPLATE = os.path.join(EXPORTS_DIR, "lob_homologation_template.csv")


def main():
    os.chdir(BACKEND_DIR)

    # a) Recrear vista (migración 035)
    print("=== a) Alembic upgrade head (vista real city/country keys) ===\n")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)

    # b) Export
    print("\n=== b) Export listas (utf-8-sig) ===\n")
    r = subprocess.run(
        [sys.executable, os.path.join(BACKEND_DIR, "scripts", "export_lob_hunt_lists.py")],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=600
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)
    print(r.stdout)

    # Total filas template (archivo recién exportado)
    total_template = 0
    if os.path.isfile(CSV_TEMPLATE):
        with open(CSV_TEMPLATE, "r", encoding="utf-8-sig", errors="replace") as f:
            total_template = sum(1 for _ in f) - 1  # menos header
        if total_template < 0:
            total_template = 0

    # c) Cargar CSV en ops.lob_homologation_final
    print("\n=== c) Carga ops.lob_homologation_final ===\n")
    r = subprocess.run(
        [sys.executable, os.path.join(BACKEND_DIR, "scripts", "load_lob_homologation_final.py")],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=300
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)
    print(r.stdout)
    # Parsear "Total filas insertadas ...: N"
    total_insertadas = 0
    for line in (r.stdout or "").splitlines():
        if "insertadas" in line.lower() and ":" in line:
            try:
                total_insertadas = int(line.split(":")[-1].strip())
            except ValueError:
                pass
            break

    # d) Validaciones (statement_timeout 600s)
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '900s'")

            print("\n=== Validación 1: resolved_lob, COUNT(*) (v_real_lob_resolved_final) ===\n")
            cur.execute("""
                SELECT resolved_lob, COUNT(*)
                FROM ops.v_real_lob_resolved_final
                GROUP BY 1
                ORDER BY 2 DESC
            """)
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]}")

            cur.execute("SELECT COUNT(*) FROM ops.v_real_lob_resolved_final WHERE resolved_lob = 'UNMAPPED'")
            total_unmapped = cur.fetchone()[0]
            print("\n=== Validación 2: COUNT(*) WHERE resolved_lob = 'UNMAPPED' ===\n")
            print(f"  {total_unmapped}")

            print("\n=== Validación 3: country, city, COUNT(*) WHERE plan_lob_name='UNMAPPED' (lob_homologation_final) ===\n")
            cur.execute("""
                SELECT country, city, COUNT(*)
                FROM ops.lob_homologation_final
                WHERE plan_lob_name = 'UNMAPPED'
                GROUP BY 1, 2
                ORDER BY 3 DESC
            """)
            unmapped_rows = cur.fetchall()
            for row in unmapped_rows:
                print(f"  {row}")
            if not unmapped_rows and total_unmapped == 0:
                print("  (vacío — esperado si todo mapeado)")

            print("\n=== Validación 4: v_plan_vs_real_final LIMIT 20 ===\n")
            cur.execute("SELECT * FROM ops.v_plan_vs_real_final ORDER BY variance_trips DESC NULLS LAST LIMIT 20")
            cols = [d[0] for d in cur.description]
            print("  ", cols)
            for row in cur.fetchall():
                print("  ", row)

            cur.execute("SELECT COUNT(*) FROM ops.v_plan_vs_real_final")
            total_lobs_final = cur.fetchone()[0]

            print("\n=== Top 10 variance_trips DESC ===\n")
            cur.execute("""
                SELECT country, city, lob, plan_trips, real_trips, variance_trips
                FROM ops.v_plan_vs_real_final
                ORDER BY variance_trips DESC NULLS LAST
                LIMIT 10
            """)
            for row in cur.fetchall():
                print(f"  {row}")
        finally:
            cur.close()

    # Resumen final
    print("\n========== RESUMEN FINAL PASO 4 FIX UNMAPPED ==========")
    print(f"  total_filas_template:  {total_template}")
    print(f"  total_insertadas:       {total_insertadas}")
    print(f"  UNMAPPED_count:        {total_unmapped}  (debe bajar; idealmente 0 si plan_lob lleno)")
    print(f"  total_lobs_final:       {total_lobs_final}")
    print("  top 10 variance_trips:  (ver bloque anterior)")
    print("========================================================\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
