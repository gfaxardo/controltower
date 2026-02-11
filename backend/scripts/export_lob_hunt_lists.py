"""
[YEGO CT] E2E — Exportar listas para casar LOB (PLAN vs REAL) y cazar manual en Excel.

Genera:
  1) plan_lobs_export.csv desde ops.v_plan_lob_universe_for_hunt (o fallback)
  2) real_tiposerv_export.csv (por city; mv/vista)
  3) real_by_park_export.csv desde ops.v_real_universe_by_park_for_hunt (park_id/park_name)
  4) panel_city_export.csv (opcional): lado PLAN/REAL por ciudad
  5) lob_homologation_template.csv con park_id/park_name (country, city, park_id, park_name, real_tipo_servicio, plan_lob_name, confidence, notes)

Usa get_db() / settings existentes. Encoding UTF-8, delimiter coma, header incluido.
"""

import sys
import os
import csv
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")

FILE_PLAN = "plan_lobs_export.csv"
FILE_REAL = "real_tiposerv_export.csv"
FILE_REAL_BY_PARK = "real_by_park_export.csv"
FILE_PANEL = "panel_city_export.csv"
FILE_TEMPLATE = "lob_homologation_template.csv"

TEMPLATE_HEADERS = ["country", "city", "park_id", "park_name", "real_tipo_servicio", "plan_lob_name", "confidence", "notes"]


def _ensure_exports_dir():
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    return EXPORTS_DIR


def _view_exists(cursor, schema: str, name: str) -> bool:
    cursor.execute("""
        SELECT 1 FROM information_schema.views
        WHERE table_schema = %s AND table_name = %s
    """, (schema, name))
    return cursor.fetchone() is not None


def _table_exists(cursor, schema: str, name: str) -> bool:
    cursor.execute("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
    """, (schema, name))
    return cursor.fetchone() is not None


def _mv_exists(cursor, schema: str, name: str) -> bool:
    cursor.execute("""
        SELECT 1 FROM pg_matviews
        WHERE schemaname = %s AND matviewname = %s
    """, (schema, name))
    return cursor.fetchone() is not None


def _fetch_plan_for_hunt(cursor):
    """PLAN para caza: ops.v_plan_lob_universe_for_hunt o fallback."""
    if _view_exists(cursor, "ops", "v_plan_lob_universe_for_hunt"):
        cursor.execute("""
            SELECT country, city, plan_lob, plan_trips, plan_revenue
            FROM ops.v_plan_lob_universe_for_hunt
            ORDER BY country, city, plan_trips DESC NULLS LAST
        """)
        return cursor.fetchall(), ["country", "city", "plan_lob", "plan_trips", "plan_revenue"]
    if _table_exists(cursor, "plan", "plan_lob_long"):
        cursor.execute("""
            SELECT country, city, TRIM(LOWER(plan_lob_base)) AS plan_lob,
                   SUM(trips_plan) AS plan_trips, SUM(revenue_plan) AS plan_revenue
            FROM plan.plan_lob_long
            GROUP BY 1, 2, 3
            ORDER BY country, city, plan_trips DESC NULLS LAST
        """)
        return cursor.fetchall(), ["country", "city", "plan_lob", "plan_trips", "plan_revenue"]
    cursor.execute("""
        SELECT 1 FROM information_schema.views
        WHERE table_schema = 'ops' AND table_name = 'v_plan_lob_universe_raw'
    """)
    if cursor.fetchone():
        cursor.execute("""
            SELECT country, city, plan_lob_name AS plan_lob,
                   COALESCE(trips_plan, 0), COALESCE(revenue_plan, 0)
            FROM ops.v_plan_lob_universe_raw
            ORDER BY country, city, trips_plan DESC NULLS LAST
        """)
        return cursor.fetchall(), ["country", "city", "plan_lob", "plan_trips", "plan_revenue"]
    return [], ["country", "city", "plan_lob", "plan_trips", "plan_revenue"]


def _fetch_real_by_park(cursor):
    """REAL por park: ops.v_real_universe_by_park_for_hunt (ordenado por real_trips DESC)."""
    if _view_exists(cursor, "ops", "v_real_universe_by_park_for_hunt"):
        cursor.execute("""
            SELECT park_id, park_name, country, city, real_tipo_servicio, real_trips, first_seen_date, last_seen_date
            FROM ops.v_real_universe_by_park_for_hunt
            ORDER BY real_trips DESC NULLS LAST, country, city
        """)
        return cursor.fetchall(), ["park_id", "park_name", "country", "city", "real_tipo_servicio", "real_trips", "first_seen_date", "last_seen_date"]
    return [], ["park_id", "park_name", "country", "city", "real_tipo_servicio", "real_trips", "first_seen_date", "last_seen_date"]


def _fetch_real_agg(cursor):
    """REAL agregada por city (para real_tiposerv_export y panel)."""
    if _mv_exists(cursor, "ops", "mv_real_tipo_servicio_universe_fast"):
        cursor.execute("""
            SELECT country, city, TRIM(LOWER(real_tipo_servicio)) AS real_tipo_servicio, SUM(trips_count) AS real_trips
            FROM ops.mv_real_tipo_servicio_universe_fast
            GROUP BY 1, 2, 3
            ORDER BY country, city, real_trips DESC NULLS LAST
        """)
        return cursor.fetchall(), ["country", "city", "real_tipo_servicio", "real_trips"]
    if _view_exists(cursor, "ops", "v_real_tipo_servicio_universe"):
        cursor.execute("""
            SELECT country, city, TRIM(LOWER(real_tipo_servicio)) AS real_tipo_servicio, SUM(trips_count) AS real_trips
            FROM ops.v_real_tipo_servicio_universe
            GROUP BY 1, 2, 3
            ORDER BY country, city, real_trips DESC NULLS LAST
        """)
        return cursor.fetchall(), ["country", "city", "real_tipo_servicio", "real_trips"]
    return [], ["country", "city", "real_tipo_servicio", "real_trips"]


def _write_csv(path: str, headers: list, rows: list):
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=",")
            w.writerow(headers)
            for row in rows:
                w.writerow([x if x is not None else "" for x in row])
        return path
    except PermissionError:
        # Windows: archivo abierto en Excel/IDE; guardar en alternativo
        base, ext = os.path.splitext(path)
        alt = f"{base}_new{ext}"
        with open(alt, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=",")
            w.writerow(headers)
            for row in rows:
                w.writerow([x if x is not None else "" for x in row])
        print(f"  [AVISO] No se pudo escribir en {path} (archivo en uso). Guardado en {alt}")
        return alt


def _print_top(rows: list, headers: list, title: str, n: int = 10):
    print(f"\n--- Top {n} {title} ---")
    if not rows:
        print("(sin filas)")
        return
    col_len = min(18, max(len(str(h)) for h in headers) + 2)
    print("  " + "  ".join(str(h)[:col_len].ljust(col_len) for h in headers))
    print("  " + "-" * (len(headers) * (col_len + 2)))
    for row in rows[:n]:
        print("  " + "  ".join(str(x)[:col_len].ljust(col_len) for x in row))


def main():
    _ensure_exports_dir()
    init_db_pool()

    path_plan = os.path.join(EXPORTS_DIR, FILE_PLAN)
    path_real = os.path.join(EXPORTS_DIR, FILE_REAL)
    path_real_park = os.path.join(EXPORTS_DIR, FILE_REAL_BY_PARK)
    path_panel = os.path.join(EXPORTS_DIR, FILE_PANEL)
    path_template = os.path.join(EXPORTS_DIR, FILE_TEMPLATE)

    with get_db() as conn:
        cursor = conn.cursor()
        # Evitar timeout en vistas pesadas (p. ej. v_real_universe_by_park_for_hunt sobre trips_all)
        cursor.execute("SET statement_timeout = '600s'")

        # 1) PLAN
        plan_rows, plan_headers = _fetch_plan_for_hunt(cursor)
        _write_csv(path_plan, plan_headers, plan_rows)
        n_plan = len(plan_rows)

        # 2) REAL por city (real_tiposerv_export)
        real_rows, real_headers = _fetch_real_agg(cursor)
        _write_csv(path_real, real_headers, real_rows)
        n_real = len(real_rows)

        # 3) REAL por park
        real_park_rows, real_park_headers = _fetch_real_by_park(cursor)
        _write_csv(path_real_park, real_park_headers, real_park_rows)
        n_real_park = len(real_park_rows)

        # 4) Panel (PLAN + REAL por ciudad)
        panel_rows = []
        panel_headers = ["side", "country", "city", "name", "metric_trips", "metric_revenue"]
        for r in plan_rows:
            panel_rows.append(("PLAN", r[0], r[1], r[2], r[3], r[4]))
        for r in real_rows:
            panel_rows.append(("REAL", r[0], r[1], r[2], r[3], None))
        def _panel_key(x):
            side, country, city, name, metric_trips, metric_revenue = x
            mt = (metric_trips or 0) if isinstance(metric_trips, (int, float)) else 0
            return (country or "", city or "", side, -mt)
        panel_rows.sort(key=_panel_key)
        _write_csv(path_panel, panel_headers, panel_rows)
        n_panel = len(panel_rows)

        # 5) Template homologación (con park): country, city, park_id, park_name, real_tipo_servicio, plan_lob_name, confidence, notes
        # Ordenar por impacto: country, city, real_trips DESC
        sorted_park = sorted(
            real_park_rows,
            key=lambda r: (r[2] or "", r[3] or "", -(r[5] if isinstance(r[5], (int, float)) else 0))
        )
        template_rows = []
        for r in sorted_park:
            template_rows.append((r[2], r[3], r[0], r[1], r[4], "", "", ""))
        _write_csv(path_template, TEMPLATE_HEADERS, template_rows)
        n_template = len(template_rows)

        cursor.close()

    # Post-check
    print("\n" + "=" * 60)
    print("Export OK")
    print("=" * 60)
    print("Filas exportadas:")
    print(f"  - plan_lobs_export.csv:      {n_plan}")
    print(f"  - real_tiposerv_export.csv: {n_real}")
    print(f"  - real_by_park_export.csv:   {n_real_park}")
    print(f"  - panel_city_export.csv:     {n_panel}")
    print(f"  - lob_homologation_template.csv: {n_template}")
    print("\nRutas absolutas:")
    print(f"  - {os.path.abspath(path_plan)}")
    print(f"  - {os.path.abspath(path_real)}")
    print(f"  - {os.path.abspath(path_real_park)}")
    print(f"  - {os.path.abspath(path_panel)}")
    print(f"  - {os.path.abspath(path_template)}")

    _print_top(plan_rows, plan_headers, "plan_lobs_export.csv")
    _print_top(real_park_rows, real_park_headers, "real_by_park_export.csv", n=20)
    _print_top(panel_rows[:15], panel_headers, "panel_city_export.csv", n=15)

    # F) Post-check obligatorio: top 30 REAL y verificación park_name no UUID (sin nueva query, usa datos ya exportados)
    print("\n--- Post-check: top 30 REAL (real_trips DESC) ---")
    top30 = real_park_rows[:30]
    for r in top30:
        park_name = (r[1] or "")[:40]
        print(f"  {park_name!r} | {r[2]} | {r[3]} | {r[4]!r} | {r[5]}")
    uuid_re = re.compile(r"^[0-9a-f]{32}$")
    total = len(real_park_rows)
    looks_uuid = sum(1 for row in real_park_rows if uuid_re.match((row[1] or "").lower()))
    print(f"\n  Total filas: {total}  |  park_name parece UUID: {looks_uuid}")
    if total > 0 and looks_uuid == total:
        print("  [AVISO] Todos los park_name parecen UUID; revisar origen (yego_integral.parks vs dim.dim_park).")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
