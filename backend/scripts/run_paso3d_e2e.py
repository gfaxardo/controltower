"""
PASO 3D E2E — Migraciones 032/033 + carga homologación + validación + export + resumen.
Sin pasos manuales. Exit 0 si homologation_total > 0 y vista tiene filas; si no exit 1.
"""
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")


def _run(cmd: list, cwd: str, desc: str) -> bool:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"[ERROR] {desc}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}")
        return False
    if r.stdout.strip():
        print(r.stdout)
    return True


def main():
    os.chdir(BACKEND_DIR)

    # 1) Alembic upgrade head
    if not _run([sys.executable, "-m", "alembic", "upgrade", "head"], BACKEND_DIR, "alembic upgrade head"):
        sys.exit(1)

    # 2) Detección CSV y loader
    csv_candidates = [
        os.path.join(EXPORTS_DIR, "lob_homologation_filled.csv"),
        os.path.join(EXPORTS_DIR, "lob_homologation_template_filled.csv"),
        os.path.join(EXPORTS_DIR, "lob_homologation_template.csv"),
    ]
    csv_path = None
    for p in csv_candidates:
        if os.path.isfile(p):
            csv_path = p
            break
    if not csv_path:
        print("ERROR: No se encontró CSV. Rutas esperadas:")
        for p in csv_candidates:
            print(f"  - {p}")
        sys.exit(1)
    print(f"CSV: {csv_path}")
    r = subprocess.run([sys.executable, os.path.join(BACKEND_DIR, "scripts", "load_lob_homologation_csv.py")], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"ERROR loader:\n{r.stdout}\n{r.stderr}")
        sys.exit(1)
    print(r.stdout)

    # 3) Validaciones (statement_timeout)
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '300s'")
            cur.execute("SELECT COUNT(*) FROM ops.lob_homologation")
            homologation_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM ops.lob_homologation WHERE confidence = 'unmapped'")
            unmapped_count = cur.fetchone()[0]
            cur.execute("SELECT confidence, COUNT(*) FROM ops.lob_homologation GROUP BY 1")
            by_confidence = cur.fetchall()
            cur.execute("SELECT coverage_status, COUNT(*) FROM ops.v_plan_vs_real_lob_check_resolved GROUP BY 1")
            by_coverage = cur.fetchall()
            cur.execute("""
                SELECT * FROM ops.v_plan_vs_real_lob_check_resolved
                WHERE coverage_status IN ('PLAN_ONLY','REAL_ONLY','PARTIAL')
                ORDER BY COALESCE(real_trips,0)+COALESCE(plan_trips,0) DESC
                LIMIT 30
            """)
            top_rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        finally:
            cur.close()

    print("\n=== Validación ===\n")
    print(f"ops.lob_homologation: {homologation_total}")
    print("Por confidence:", by_confidence)
    print("Por coverage_status:", by_coverage)
    if top_rows:
        print("\nTop 30 PLAN_ONLY/REAL_ONLY/PARTIAL (columnas):", cols)
        for r in top_rows[:10]:
            print(r)

    # 4) Export
    if not _run([sys.executable, os.path.join(BACKEND_DIR, "scripts", "export_lob_hunt_lists.py")], BACKEND_DIR, "export_lob_hunt_lists"):
        sys.exit(1)

    # 5) Resumen ejecutivo
    print("\n========== RESUMEN EJECUTIVO PASO 3D ==========")
    print(f"  filas_homologation:    {homologation_total}")
    print(f"  unmapped_count:        {unmapped_count}")
    print("  coverage_status counts:", dict(by_coverage))
    print("  exports path:          ", EXPORTS_DIR)
    print("================================================\n")

    if homologation_total > 0 and by_coverage:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
