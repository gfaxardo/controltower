"""
PASO 4 E2E — Homologación final Plan ↔ Real.
Migración 034 + carga CSV + validaciones + reporte.
"""
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    os.chdir(BACKEND_DIR)

    # 1) Migración
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)

    # 2) Cargar CSV
    r = subprocess.run([sys.executable, os.path.join(BACKEND_DIR, "scripts", "load_lob_homologation_final.py")], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)
    print(r.stdout)

    # 3) Validaciones
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '180s'")

            print("\n=== resolved_lob, COUNT(*) ===\n")
            cur.execute("""
                SELECT resolved_lob, COUNT(*)
                FROM ops.v_real_lob_resolved_final
                GROUP BY 1
                ORDER BY 2 DESC
            """)
            for row in cur.fetchall():
                print(f"  {row[0]}: {row[1]}")

            print("\n=== COUNT(*) WHERE resolved_lob = 'UNMAPPED' ===\n")
            cur.execute("SELECT COUNT(*) FROM ops.v_real_lob_resolved_final WHERE resolved_lob = 'UNMAPPED'")
            total_unmapped = cur.fetchone()[0]
            print(f"  {total_unmapped}")

            print("\n=== COUNT(*) v_plan_vs_real_final ===\n")
            cur.execute("SELECT COUNT(*) FROM ops.v_plan_vs_real_final")
            total_lobs_final = cur.fetchone()[0]
            print(f"  {total_lobs_final}")

            cur.execute("SELECT COUNT(*) FROM ops.v_real_lob_resolved_final")
            total_real_rows = cur.fetchone()[0]

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

    # 4) Reporte final
    print("\n========== REPORTE FINAL PASO 4 ==========")
    print(f"  total_real_rows:   {total_real_rows}")
    print(f"  total_unmapped:    {total_unmapped}")
    print(f"  total_lobs_final:  {total_lobs_final}")
    print("  top 10 variance_trips desc: (ver bloque anterior)")
    print("==========================================\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
