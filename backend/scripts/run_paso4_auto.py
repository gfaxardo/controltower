"""
PASO 4 — Ejecución automática sin validaciones pesadas (evita timeout).
Hace: alembic upgrade → export → carga. No consulta v_real_lob_resolved_final ni v_plan_vs_real_final.
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

    print("=== 1) Alembic upgrade head ===\n")
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)

    print("=== 2) Export listas ===\n")
    r = subprocess.run([sys.executable, os.path.join(BACKEND_DIR, "scripts", "export_lob_hunt_lists.py")], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)
    print(r.stdout)

    total_template = 0
    if os.path.isfile(CSV_TEMPLATE):
        with open(CSV_TEMPLATE, "r", encoding="utf-8-sig", errors="replace") as f:
            total_template = max(0, sum(1 for _ in f) - 1)

    print("=== 3) Carga ops.lob_homologation_final ===\n")
    r = subprocess.run([sys.executable, os.path.join(BACKEND_DIR, "scripts", "load_lob_homologation_final.py")], cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)
    print(r.stdout)

    total_insertadas = 0
    for line in (r.stdout or "").splitlines():
        if "insertadas" in line.lower() and ":" in line:
            try:
                total_insertadas = int(line.split(":")[-1].strip())
            except ValueError:
                pass
            break

    # Resumen rápido desde tabla (sin vistas pesadas)
    from app.db.connection import get_db, init_db_pool
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '30s'")
        cur.execute("SELECT COUNT(*) FROM ops.lob_homologation_final")
        n_table = cur.fetchone()[0]
        cur.execute("SELECT plan_lob_name, COUNT(*) FROM ops.lob_homologation_final GROUP BY 1 ORDER BY 2 DESC LIMIT 10")
        top_plan = cur.fetchall()
        cur.close()

    print("\n========== RESUMEN PASO 4 (auto) ==========")
    print(f"  total_filas_template:  {total_template}")
    print(f"  total_insertadas:      {total_insertadas}")
    print(f"  filas en tabla:        {n_table}")
    print("  Top plan_lob_name:")
    for row in top_plan:
        print(f"    {row[0]}: {row[1]}")
    print("==========================================\n")
    print("Para validaciones completas (UNMAPPED, variances) ejecuta en tu PC:")
    print("  python scripts/run_paso4_fix_unmapped_e2e.py")
    print("  (puede tardar varios minutos por las vistas pesadas)\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
