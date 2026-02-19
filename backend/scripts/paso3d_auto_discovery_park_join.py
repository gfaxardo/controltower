"""
[YEGO CT] PASO 3D — Auto-discovery: qué columna de public.parks contiene park_id.

- Inspecciona public.parks (columnas y tipos).
- Para cada columna candidata (text/varchar/character), calcula match_count con trips_all.park_id.
- Elige la columna con mayor match_count como join_key.
- Re-crea ops.v_real_universe_by_park_for_hunt con join_key detectado.
- Valida, ejecuta export, reporta.
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

TIMEOUT_MATCH = "120s"
TIMEOUT_VIEW = "300s"


def _get_parks_columns(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'parks'
        ORDER BY ordinal_position
    """)
    rows = cur.fetchall()
    cur.close()
    return [(r[0], r[1]) for r in rows]


def _is_join_candidate(data_type: str) -> bool:
    """Cualquier tipo que se pueda castear a text y comparar (incl. timestamp por si la columna tiene datos rotos)."""
    t = (data_type or "").lower()
    return (
        "char" in t or "text" in t or "varchar" in t or "uuid" in t or "character" in t
        or "timestamp" in t or "date" in t or "time" in t or "int" in t or "numeric" in t or "bigint" in t
    )


def _match_count_for_column(conn, column_name: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SET statement_timeout = '{TIMEOUT_MATCH}'")
    # Identificador entre comillas dobles para evitar SQL injection (column_name viene de information_schema)
    col_quoted = '"' + column_name.replace('"', '""') + '"'
    sql = f"""
        SELECT COUNT(*)
        FROM public.trips_all t
        JOIN public.parks p
          ON LOWER(TRIM(p.{col_quoted}::text)) = LOWER(TRIM(t.park_id::text))
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
    """
    try:
        cur.execute(sql)
        row = cur.fetchone()
        return int(row[0] or 0) if row else 0
    except Exception as e:
        print(f"    [error] {column_name}: {e}")
        return 0
    finally:
        cur.close()


def _discover_join_key(conn):
    columns = _get_parks_columns(conn)
    print("--- 1) public.parks columnas ---")
    for name, dtype in columns:
        print(f"  {name}: {dtype}")

    candidates = [(name, dtype) for name, dtype in columns if _is_join_candidate(dtype)]
    if not candidates:
        print("  No hay columnas tipo text/varchar/uuid.")
        return None, []

    print("\n--- 2) Overlap con trips_all.park_id por columna ---")
    results = []
    for name, dtype in candidates:
        cnt = _match_count_for_column(conn, name)
        results.append((name, cnt))
        print(f"  {name}: match_count = {cnt}")

    best = max(results, key=lambda x: x[1])
    join_key = best[0] if best[1] > 0 else None
    return join_key, results


def _quote_id(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _build_view_sql(join_key: str, other_string_columns: list) -> str:
    """Construye vista: park_id=join_key, park_name=COALESCE(otras), city=primera otra, country=''."""
    jq = _quote_id(join_key)
    # park_name: COALESCE de todas las demás columnas string, luego join_key
    coalesce_parts = [f"NULLIF(TRIM(p.{_quote_id(c)}::text), '')" for c in other_string_columns]
    coalesce_parts.append(f"p.{jq}::text")
    park_name_expr = "COALESCE(" + ", ".join(coalesce_parts) + ")"
    # city: primera columna que no es join_key
    city_col = other_string_columns[0] if other_string_columns else join_key
    city_expr = f"LOWER(TRIM(p.{_quote_id(city_col)}::text))"

    return f"""
        DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE;
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.{jq}::text AS park_id,
          {park_name_expr} AS park_name,
          ''::text AS country,
          {city_expr} AS city,
          LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p
          ON LOWER(TRIM(p.{jq}::text)) = LOWER(TRIM(t.park_id::text))
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
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


def _count_view(conn) -> int:
    cur = conn.cursor()
    cur.execute(f"SET statement_timeout = '{TIMEOUT_VIEW}'")
    cur.execute("SELECT COUNT(*) FROM ops.v_real_universe_by_park_for_hunt")
    row = cur.fetchone()
    cur.close()
    return int(row[0] or 0) if row else 0


def _count_csv_rows(path: str) -> int:
    if not os.path.isfile(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def main() -> int:
    init_db_pool()
    print("=== PASO 3D — Auto-discovery park join ===\n")

    with get_db() as conn:
        join_key, match_results = _discover_join_key(conn)
        if not join_key:
            print("\n[ABORTO] Ninguna columna tiene match_count > 0.")
            print("  Diagnóstico: la columna que contiene park_id no está en public.parks o el formato no coincide.")
            return 1

        match_count = next(m for c, m in match_results if c == join_key)
        print(f"\n--- 3) join_key elegida: {join_key} (match_count = {match_count}) ---")

        columns = _get_parks_columns(conn)
        other_string = [
            c for c, _ in columns
            if _is_join_candidate(_) and c != join_key
        ]
        view_sql = _build_view_sql(join_key, other_string)
        print("--- 4) Re-crear vista ---")
        _apply_view(conn, view_sql)

    print("--- 5) Validar ---")
    with get_db() as conn:
        count_view = _count_view(conn)
        print(f"  COUNT(vista) = {count_view}")
        if count_view == 0:
            print("[ABORTO] Vista con 0 filas.")
            return 1

    print("\n--- 6) Export ---")
    script_export = os.path.join(BACKEND_DIR, "scripts", "export_lob_hunt_lists.py")
    r = subprocess.run(
        [sys.executable, script_export],
        cwd=BACKEND_DIR,
        timeout=620,
        capture_output=False,
    )
    if r.returncode != 0:
        print(f"  [AVISO] export_lob_hunt_lists.py terminó con código {r.returncode}")

    filas_real = _count_csv_rows(REAL_BY_PARK_CSV)
    filas_template = _count_csv_rows(TEMPLATE_CSV)

    print("\n--- 7) Reporte ---")
    print(f"  columna join_key:        {join_key}")
    print(f"  match_count:             {match_count}")
    print(f"  filas vista:             {count_view}")
    print(f"  filas real_by_park:      {filas_real}")
    print(f"  filas lob_homologation_template: {filas_template}")

    if filas_real > 0 and filas_template > 0:
        print("\n[OK] Export con filas > 0.")
        return 0
    print("\n[FALLO] Export con 0 filas en real_by_park o template.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
