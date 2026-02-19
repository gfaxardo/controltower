"""
[YEGO CT] PASO 3D E2E — Fix export vacío: diagnóstico JOIN parks↔trips_all, vista y export.

- Diagnostica match A (LOWER/TRIM) vs B (+LOWER/TRIM+REPLACE '-').
- Re-crea ops.v_real_universe_by_park_for_hunt con el JOIN que matchee.
- Valida vista, aplica filtro anti-basura solo si no mata universo, ejecuta export.
- Sin pasos manuales. Exit 0 si real_by_park y template tienen filas > 0.
"""
import sys
import os
import csv
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
REAL_BY_PARK_CSV = os.path.join(EXPORTS_DIR, "real_by_park_export.csv")
TEMPLATE_CSV = os.path.join(EXPORTS_DIR, "lob_homologation_template.csv")

# trips_all puede ser muy grande: diagnóstico y vista necesitan tiempo
TIMEOUT_DIAG = "300s"
TIMEOUT_VIEW = "300s"


def _run(cur, sql: str, timeout: str, desc: str = ""):
    cur.execute(f"SET statement_timeout = '{timeout}'")
    cur.execute(sql)
    row = cur.fetchone()
    return row[0] if row is not None else None


def _run_approx_trips(cur) -> int:
    """Conteo aproximado de public.trips_all (evita full scan en tablas enormes)."""
    cur.execute("SET statement_timeout = '5s'")
    cur.execute("""
        SELECT COALESCE(reltuples::bigint, 0) FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = 'trips_all'
    """)
    row = cur.fetchone()
    return int(row[0] or 0)


def _diagnose(conn):
    import psycopg2
    cur = conn.cursor()
    out = {}
    try:
        try:
            out["total_trips_all"] = _run(cur, "SELECT COUNT(*) FROM public.trips_all", TIMEOUT_DIAG) or 0
        except psycopg2.errors.QueryCanceled:
            out["total_trips_all"] = _run_approx_trips(cur)
            print("  [info] total_trips_all por timeout -> uso aproximado (pg_class)")
        out["trips_all_con_park"] = _run(
            cur,
            "SELECT COUNT(*) FROM public.trips_all WHERE park_id IS NOT NULL AND TRIM(COALESCE(park_id::text,'')) != ''",
            TIMEOUT_DIAG,
        ) or 0
        out["distinct_trips_all_park_id_norm"] = _run(
            cur,
            "SELECT COUNT(DISTINCT REPLACE(LOWER(TRIM(COALESCE(park_id::text,''))), '-', '')) FROM public.trips_all WHERE park_id IS NOT NULL AND TRIM(COALESCE(park_id::text,'')) != ''",
            TIMEOUT_DIAG,
        ) or 0
        out["total_parks"] = _run(cur, "SELECT COUNT(*) FROM public.parks", TIMEOUT_DIAG) or 0
        out["distinct_parks_city_norm"] = _run(
            cur,
            "SELECT COUNT(DISTINCT REPLACE(LOWER(TRIM(COALESCE(city::text,''))), '-', '')) FROM public.parks WHERE city IS NOT NULL AND TRIM(COALESCE(city::text,'')) != ''",
            TIMEOUT_DIAG,
        ) or 0
        # match_A: join con LOWER+TRIM
        out["match_A"] = _run(
            cur,
            """
            SELECT COUNT(*) FROM public.trips_all t
            INNER JOIN public.parks p ON LOWER(TRIM(p.city::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
            """,
            TIMEOUT_DIAG,
        ) or 0
        # match_B: join con LOWER+TRIM+REPLACE '-'
        out["match_B"] = _run(
            cur,
            """
            SELECT COUNT(*) FROM public.trips_all t
            INNER JOIN public.parks p
              ON REPLACE(LOWER(TRIM(p.city::text)), '-', '') = REPLACE(LOWER(TRIM(t.park_id::text)), '-', '')
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
            """,
            TIMEOUT_DIAG,
        ) or 0
    finally:
        cur.close()
    return out


def _create_view_sql(join_b: bool):
    join_cond = (
        "REPLACE(LOWER(TRIM(p.city::text)), '-', '') = REPLACE(LOWER(TRIM(t.park_id::text)), '-', '')"
        if join_b
        else "LOWER(TRIM(p.city::text)) = LOWER(TRIM(t.park_id::text))"
    )
    return f"""
        DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE;
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.city::text AS park_id,
          COALESCE(
            NULLIF(TRIM(p.created_at::text), ''),
            NULLIF(TRIM(p.name::text), ''),
            NULLIF(TRIM(p.id::text), ''),
            p.city::text
          ) AS park_name,
          ''::text AS country,
          LOWER(TRIM(p.id::text)) AS city,
          LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p ON {join_cond}
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
        GROUP BY 1, 2, 3, 4, 5
    """


def _create_view_sql_with_filter(max_len: int = 80):
    return f"""
        DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE;
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.city::text AS park_id,
          COALESCE(
            NULLIF(TRIM(p.created_at::text), ''),
            NULLIF(TRIM(p.name::text), ''),
            NULLIF(TRIM(p.id::text), ''),
            p.city::text
          ) AS park_name,
          ''::text AS country,
          LOWER(TRIM(p.id::text)) AS city,
          LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p
          ON REPLACE(LOWER(TRIM(p.city::text)), '-', '') = REPLACE(LOWER(TRIM(t.park_id::text)), '-', '')
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
          AND LENGTH(TRIM(t.tipo_servicio)) <= {max_len}
        GROUP BY 1, 2, 3, 4, 5
    """


def _apply_view(conn, sql: str):
    cur = conn.cursor()
    try:
        for stmt in sql.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        conn.commit()
    finally:
        cur.close()


def _validate_view(conn):
    cur = conn.cursor()
    cur.execute(f"SET statement_timeout = '{TIMEOUT_VIEW}'")
    cur.execute("SELECT COUNT(*) FROM ops.v_real_universe_by_park_for_hunt")
    count_view = cur.fetchone()[0] or 0
    cur.execute("""
        SELECT park_id, park_name, country, city, real_tipo_servicio, real_trips
        FROM ops.v_real_universe_by_park_for_hunt
        ORDER BY real_trips DESC NULLS LAST
        LIMIT 20
    """)
    top20 = cur.fetchall()
    cur.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN park_name = park_id::text OR TRIM(COALESCE(park_name,'')) = TRIM(COALESCE(park_id::text,'')) THEN 1 ELSE 0 END)
        FROM ops.v_real_universe_by_park_for_hunt
    """)
    row = cur.fetchone()
    name_equals_id = (row[1] or 0) if row else 0
    cur.close()
    return count_view, top20, name_equals_id


def _count_csv_rows(path: str) -> int:
    if not os.path.isfile(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # minus header


def main() -> int:
    init_db_pool()
    print("=== PASO 3D E2E — Fix export vacío ===\n")

    with get_db() as conn:
        cur = conn.cursor()
        print("--- 1) Diagnóstico ---")
        diag = _diagnose(conn)
        print(f"  total_trips_all              = {diag['total_trips_all']}")
        print(f"  trips_all_con_park           = {diag['trips_all_con_park']}")
        print(f"  distinct_trips_all_park_id_norm = {diag['distinct_trips_all_park_id_norm']}")
        print(f"  total_parks                  = {diag['total_parks']}")
        print(f"  distinct_parks_city_norm     = {diag['distinct_parks_city_norm']}")
        print(f"  match_A (LOWER/TRIM)         = {diag['match_A']}")
        print(f"  match_B (LOWER/TRIM/REPLACE -)= {diag['match_B']}")
        cur.close()

        join_strategy = None
        if diag["match_A"] > 0:
            join_strategy = "A"
        elif diag["match_B"] > 0:
            join_strategy = "B"
        else:
            print("\n[ABORTO] match_A=0 y match_B=0. JOIN no matchea.")
            print("  Posible causa: parks.city no contiene park_id, o columnas equivocadas.")
            print("  Diagnóstico: no se puede re-crear vista con filas.")
            return 1

        print(f"\n--- 2) Join strategy: {join_strategy} ---")
        view_sql = _create_view_sql(join_b=(join_strategy == "B"))
        _apply_view(conn, view_sql)

        print("--- 3) Validar vista ---")
        count_view, top20, name_equals_id = _validate_view(conn)
        print(f"  count_view = {count_view}")
        print(f"  name_equals_id = {name_equals_id}")
        for i, r in enumerate(top20[:10], 1):
            print(f"    {i}. {r[1]!r} | {r[3]} | {r[4]!r} | {r[5]}")
        if count_view == 0:
            print("\n[ABORTO] Vista sigue con 0 filas tras re-crear.")
            return 1

        print("\n--- 4) Filtro anti-basura (solo si count_view > 0) ---")
        filtered_sql = _create_view_sql_with_filter(80)
        _apply_view(conn, filtered_sql)
        count_filtered, _, _ = _validate_view(conn)
        print(f"  count_view_filtered (LENGTH tipo_servicio <= 80) = {count_filtered}")
        if count_filtered == 0:
            print("  Filtro mató universo, se deja sin filtro.")
            view_sql = _create_view_sql(join_b=(join_strategy == "B"))
            _apply_view(conn, view_sql)
        else:
            print("  Filtro aplicado.")

    print("\n--- 5) Export (export_lob_hunt_lists) ---")
    script_export = os.path.join(BACKEND_DIR, "scripts", "export_lob_hunt_lists.py")
    r = subprocess.run(
        [sys.executable, script_export],
        cwd=BACKEND_DIR,
        timeout=620,
        capture_output=False,
    )
    if r.returncode != 0:
        print(f"  [AVISO] export_lob_hunt_lists.py terminó con código {r.returncode}")

    print("\n--- 6) Criterio de éxito ---")
    filas_real = _count_csv_rows(REAL_BY_PARK_CSV)
    filas_template = _count_csv_rows(TEMPLATE_CSV)
    print(f"  real_by_park_export.csv        = {filas_real} filas")
    print(f"  lob_homologation_template.csv  = {filas_template} filas")

    if filas_real > 0 and filas_template > 0:
        print("\n[OK] Export con filas > 0.")
        return 0

    print("\n[FALLO] Export sigue con 0 en real_by_park o template.")
    print("  Diagnóstico final:")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SET statement_timeout = '{TIMEOUT_VIEW}'")
        cur.execute("SELECT COUNT(*) FROM ops.v_real_universe_by_park_for_hunt")
        cv = cur.fetchone()[0] or 0
        cur.close()
    print(f"    count_view actual = {cv}")
    print(f"    match_A = {diag['match_A']}, match_B = {diag['match_B']}")
    print("  El export lee ops.v_real_universe_by_park_for_hunt; si count_view>0 y export=0, revisar ruta/permisos de exports/.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
