"""
[YEGO CT] E2E PASO A.2 — TRUNCATE staging.plan_projection_realkey_raw + load CSV + validaciones.
Uso: python pasoA2_load_plan_realkey.py --csv "C:\\ruta\\plan_realkey.csv"
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool


def run(cur, sql, desc=""):
    try:
        cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        print(f"  [ERROR] {desc}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="PASO A.2 — Cargar plan por llave real")
    parser.add_argument("--csv", required=True, help="Ruta al CSV plan_realkey (header: country,city,park_id,real_tipo_servicio,year,month,trips_plan,...)")
    args = parser.parse_args()
    csv_path = args.csv

    print("=== PASO A.2 — Carga plan realkey ===\n")

    if not os.path.exists(csv_path):
        print(f"  [ERROR] Archivo no encontrado: {csv_path}")
        sys.exit(1)
    print(f"  CSV: {csv_path}\n")

    init_db_pool()

    # 1) TRUNCATE
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '120s'")
            cur.execute("TRUNCATE staging.plan_projection_realkey_raw")
            conn.commit()
        finally:
            cur.close()
    print("  TRUNCATE staging.plan_projection_realkey_raw ejecutado.\n")

    # 2) Load
    print("  Ejecutando loader...")
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    loader_script = os.path.join(backend_dir, "scripts", "load_plan_projection_realkey.py")
    import subprocess
    out = subprocess.run(
        [sys.executable, loader_script, csv_path],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    print(out.stdout or "")
    if out.stderr:
        print(out.stderr)
    if out.returncode != 0:
        print("  [WARN] Loader salió con código", out.returncode)
    print()

    # 3) Validaciones
    print("=== Validaciones ===\n")
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SET statement_timeout = '60s'")
            r = run(cur, "SELECT COUNT(*) FROM staging.plan_projection_realkey_raw", "rows")
            rows_staging = r[0][0] if r else 0
            print(f"  rows_staging: {rows_staging}")

            r = run(cur, """
                SELECT MIN(period_date), MAX(period_date)
                FROM staging.plan_projection_realkey_raw
            """, "minmax")
            min_period = r[0][0] if r and r[0] else None
            max_period = r[0][1] if r and r[0] else None
            print(f"  min_period: {min_period}, max_period: {max_period}")

            r = run(cur, """
                SELECT
                    SUM(CASE WHEN country IS NULL OR TRIM(COALESCE(country,'')) = '' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN park_id IS NULL OR TRIM(COALESCE(park_id,'')) = '' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN period_date IS NULL THEN 1 ELSE 0 END)
                FROM staging.plan_projection_realkey_raw
            """, "nulls")
            if r and rows_staging > 0:
                print(f"  null_country: {r[0][0] or 0}, null_park_id: {r[0][1] or 0}, null_period_date: {r[0][2] or 0}")
        finally:
            cur.close()

    print("\n" + "=" * 60)
    if rows_staging > 0 and min_period and max_period:
        print("  CARGA OK")
        print(f"  - rows_staging: {rows_staging}")
        print(f"  - period_date: {min_period} .. {max_period}")
        print("\n  Siguiente: python scripts/pasoA3_smoke_plan_vs_real_realkey.py")
    else:
        print("  Revisar: rows_staging > 0 y period_date min/max válidos.")
    print("=" * 60)


if __name__ == "__main__":
    main()
