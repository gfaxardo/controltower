"""
[YEGO CT] PASO 2.2 E2E — Cargar CSV Plan Projection a staging + validar.
- Preview del CSV (header + 5 filas, delimitador).
- TRUNCATE staging.plan_projection_raw.
- Ejecuta loader y validaciones SQL.

Uso: python paso2_2_cargar_csv_e2e.py [ruta_csv]
  Si no se pasa ruta, usa: c:\\Users\\Pc\\Downloads\\proyeccion simplificada - Hoja 2.csv
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

DEFAULT_CSV = r"c:\Users\Pc\Downloads\proyeccion simplificada - Hoja 2.csv"

def run(cur, conn, sql, desc=""):
    try:
        cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        print(f"  [ERROR] {desc}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        return None

def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV

    # --- 1) UBICAR CSV ---
    print("=== 1) UBICAR CSV ===\n")
    if not os.path.exists(csv_path):
        print(f"  [ERROR] Archivo no encontrado: {csv_path}")
        print("  Indica la ruta local absoluta del CSV de proyección.")
        sys.exit(1)
    if not csv_path.lower().endswith(".csv"):
        print(f"  [WARN] Extensión no es .csv: {csv_path}")
    print(f"  Ruta: {csv_path}")
    print(f"  Existe: Sí\n")

    # --- 2) PREVIEW ---
    print("=== 2) PREVIEW (header + 5 filas) ===\n")
    try:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            lines = [f.readline().strip() for _ in range(6)]
        for i, line in enumerate(lines):
            print(f"  {i+1}: {line[:120]}{'...' if len(line) > 120 else ''}")
        delimiter = ";" if lines[0].count(";") > lines[0].count(",") else ","
        print(f"\n  Delimitador detectado: '{delimiter}'\n")
    except Exception as e:
        print(f"  [ERROR] Preview: {e}\n")

    # --- 3) TRUNCATE STAGING ---
    print("=== 3) LIMPIEZA STAGING ===\n")
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("TRUNCATE staging.plan_projection_raw")
            conn.commit()
        except Exception as e:
            print(f"  [ERROR] truncate: {e}")
            conn.rollback()
        cur.close()
    print("  TRUNCATE staging.plan_projection_raw ejecutado.\n")

    # --- 4) LOADER ---
    print("=== 4) EJECUTAR LOADER ===\n")
    import subprocess
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    loader_script = os.path.join(backend_dir, "scripts", "load_plan_projection_csv.py")
    out = subprocess.run(
        [sys.executable, loader_script, csv_path],
        cwd=backend_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    print(out.stdout or "")
    if out.stderr:
        print(out.stderr)
    if out.returncode != 0:
        print(f"  [WARN] Loader salió con código {out.returncode}")
    print()

    # --- 5) VALIDACIONES SQL ---
    print("=== 5) VALIDACIONES SQL ===\n")
    with get_db() as conn:
        cur = conn.cursor()

        r = run(cur, conn, "SELECT COUNT(*) FROM staging.plan_projection_raw", "5.1 rows")
        rows_staging = r[0][0] if r else 0
        print(f"  5.1 rows_staging: {rows_staging}")

        r = run(cur, conn, """
            SELECT MIN(period_date), MAX(period_date)
            FROM staging.plan_projection_raw
        """, "5.2 rango fechas")
        min_period = r[0][0] if r and r[0][0] else None
        max_period = r[0][1] if r and r[0][1] else None
        if min_period is not None:
            print(f"  5.2 min_period: {min_period}, max_period: {max_period}")
        else:
            print("  5.2 min/max period_date: (vacío o NULL)")

        r = run(cur, conn, """
            SELECT
              SUM(CASE WHEN country IS NULL OR country='' THEN 1 ELSE 0 END),
              SUM(CASE WHEN lob_name IS NULL OR lob_name='' THEN 1 ELSE 0 END),
              SUM(CASE WHEN period_date IS NULL THEN 1 ELSE 0 END)
            FROM staging.plan_projection_raw
        """, "5.3 nulos")
        null_country = null_lob_name = null_period_date = 0
        if r and rows_staging > 0:
            null_country, null_lob_name, null_period_date = r[0][0] or 0, r[0][1] or 0, r[0][2] or 0
            print(f"  5.3 null_country: {null_country}, null_lob_name: {null_lob_name}, null_period_date: {null_period_date}")
        else:
            print("  5.3 (sin filas)")

        r = run(cur, conn, """
            SELECT country, city, COUNT(*) AS rows
            FROM staging.plan_projection_raw
            GROUP BY 1,2 ORDER BY rows DESC LIMIT 20
        """, "5.4 top country/city")
        print("  5.4 Top 20 country/city:")
        if r:
            for row in r:
                print(f"      {str(row[0]):<10} {str(row[1]):<20} {row[2]:>8}")

        r = run(cur, conn, """
            SELECT TRIM(LOWER(lob_name)) AS plan_lob_name, SUM(trips_plan) AS trips_plan
            FROM staging.plan_projection_raw
            WHERE lob_name IS NOT NULL AND lob_name <> ''
            GROUP BY 1 ORDER BY trips_plan DESC NULLS LAST LIMIT 30
        """, "5.5 top 30 LOB")
        print("  5.5 Top 30 LOB (plan):")
        if r:
            for row in r[:15]:
                print(f"      {str(row[0]):<35} {row[1]:>12,.0f}")
            if len(r) > 15:
                print(f"      ... y {len(r)-15} más")

        cur.close()

    # --- 6) CRITERIO DE ÉXITO ---
    print("\n" + "="*60)
    if rows_staging > 0 and null_lob_name == 0 and min_period and max_period:
        print("  CSV CARGADO OK")
        print(f"  - rows_staging: {rows_staging}")
        print(f"  - null_lob_name: {null_lob_name}")
        print(f"  - period_date: {min_period} .. {max_period}")
        print("\n  Siguiente paso: correr PASO 2.1 nuevamente:")
        print("    python scripts/paso2_1_verificacion_rapida.py")
    elif rows_staging == 0:
        print("  FALLO: rows_staging = 0. Revisar delimiter, headers o mapeo de columnas.")
    elif null_lob_name > 0:
        print(f"  FALLO: null_lob_name = {null_lob_name} (debe ser 0 o muy bajo). Revisar columna lob_name/lob_base.")
    else:
        print("  Revisar min/max period_date o criterios de éxito.")
    print("="*60)

if __name__ == "__main__":
    main()
