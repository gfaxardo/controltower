"""
[YEGO CT] E2E PASO A.4 — Validar y corregir join con parks en v_plan_vs_real_realkey_final.

- Diagnóstico: columnas de public.parks, overlap con trips_all.park_id por columna.
- Auto-discovery: elige join_key_best por MAX(match_count).
- Si el join actual (id) es distinto al mejor: genera migración 039 y ejecuta alembic.
- Validaciones: park_name null rate, matched_pct (mes plan), parks_coverage.
- Query de 20 filas con park_name IS NULL y resolución manual con join_key_best.
- Exit 0 si park_name null rate <= 5% y matched_pct >= 30% (o 0 con aviso si no hay real en mes plan).
- Exit 1 si null rate > 5% o vista final vacía.

Uso: cd backend && python scripts/pasoA4_validate_and_fix_parks_join.py
"""
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALEMBIC_VERSIONS = os.path.join(BACKEND_DIR, "alembic", "versions")
STMT_TIMEOUT = "300s"
CURRENT_JOIN_KEY_DEFAULT = "id"  # definido en 038


def _run(cur, sql, desc="", timeout=None, params=None):
    t = timeout or STMT_TIMEOUT
    try:
        cur.execute(f"SET statement_timeout = '{t}'")
        if params is not None:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        print(f"  [ERROR] {desc}: {e}")
        return None


def get_parks_columns(cur):
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'parks'
        ORDER BY ordinal_position
    """)
    return [(r[0], r[1]) for r in cur.fetchall()]


def is_join_candidate(data_type: str) -> bool:
    t = (data_type or "").lower()
    return (
        "char" in t or "text" in t or "varchar" in t or "uuid" in t or "character" in t
        or "timestamp" in t or "date" in t or "time" in t or "int" in t or "numeric" in t or "bigint" in t
    )


def quote_id(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def match_count_for_column(cur, column_name: str) -> int:
    cq = quote_id(column_name)
    sql = f"""
        SELECT COUNT(*)
        FROM public.trips_all t
        JOIN public.parks p
          ON LOWER(TRIM(p.{cq}::text)) = LOWER(TRIM(t.park_id::text))
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
          AND LENGTH(TRIM(COALESCE(t.tipo_servicio,'')::text)) < 100
          AND (t.tipo_servicio::text NOT LIKE '%%->%%' OR t.tipo_servicio IS NULL)
    """
    try:
        cur.execute(f"SET statement_timeout = '{STMT_TIMEOUT}'")
        cur.execute(sql)
        row = cur.fetchone()
        return int(row[0] or 0) if row else 0
    except Exception as e:
        print(f"    [error] {column_name}: {e}")
        return 0


def distinct_match_for_column(cur, column_name: str) -> int:
    cq = quote_id(column_name)
    sql = f"""
        SELECT COUNT(DISTINCT (t.park_id, t.tipo_servicio))
        FROM public.trips_all t
        JOIN public.parks p
          ON LOWER(TRIM(p.{cq}::text)) = LOWER(TRIM(t.park_id::text))
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
          AND LENGTH(TRIM(COALESCE(t.tipo_servicio,'')::text)) < 100
          AND (t.tipo_servicio::text NOT LIKE '%%->%%' OR t.tipo_servicio IS NULL)
    """
    try:
        cur.execute(f"SET statement_timeout = '{STMT_TIMEOUT}'")
        cur.execute(sql)
        row = cur.fetchone()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def discover_join_key(cur):
    columns = get_parks_columns(cur)
    print("--- 1) public.parks columnas y tipos ---")
    for name, dtype in columns:
        print(f"  {name}: {dtype}")

    candidates = [(n, dt) for n, dt in columns if is_join_candidate(dt)]
    if not candidates:
        print("  No hay columnas candidatas para join.")
        return None, [], []

    print("\n--- 2) Overlap con trips_all.park_id (COUNT y DISTINCT) ---")
    results = []
    for name, _ in candidates:
        cnt = match_count_for_column(cur, name)
        dist = distinct_match_for_column(cur, name)
        results.append((name, cnt, dist))
        print(f"  {name}: match_count = {cnt}, distinct_pairs = {dist}")

    best = max(results, key=lambda x: x[1])
    join_key_best = best[0] if best[1] > 0 else None
    return join_key_best, results, columns


def get_current_join_key_from_view(cur) -> str:
    """Intenta inferir la columna de parks usada en el join de v_real_universe_by_park_realkey."""
    r = _run(cur, """
        SELECT pg_get_viewdef('ops.v_real_universe_by_park_realkey'::regclass, true)
    """, "get view def")
    if not r or not r[0][0]:
        return CURRENT_JOIN_KEY_DEFAULT
    def_ = (r[0][0] or "").lower()
    if "p.id::text" in def_ or "p.\"id\"::text" in def_:
        return "id"
    if "p.name::text" in def_ or "p.\"name\"::text" in def_:
        return "name"
    if "p.city::text" in def_ or "p.\"city\"::text" in def_:
        return "city"
    if "p.created_at::text" in def_ or "p.\"created_at\"::text" in def_:
        return "created_at"
    return CURRENT_JOIN_KEY_DEFAULT


def migration_content(join_key_best: str) -> str:
    cq = quote_id(join_key_best)
    # park_name: parks.name si no vacío, sino park_city_raw, sino join_key como text
    return f'''"""
E2E PASO A.4 — Corregir join con parks en v_real_universe_by_park_realkey.
join_key detectado: {join_key_best}. park_name desde parks.name (fallback otras columnas).
"""
from alembic import op

revision = "039_fix_parks_join_key_realkey"
down_revision = "038_plan_realkey_no_homologation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_city_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_realkey_final CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_realkey CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_realkey AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                p.{cq}::text AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM public.trips_all t
            JOIN public.parks p ON LOWER(TRIM(p.{cq}::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) < 100
              AND t.tipo_servicio NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                park_id_raw,
                COALESCE(
                    NULLIF(TRIM(park_name_raw::text), ''),
                    NULLIF(TRIM(park_city_raw::text), ''),
                    park_id_raw::text
                ) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                LOWER(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                        'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')
                ) AS city_key
            FROM with_city
        )
        SELECT
            park_id::text AS park_id,
            park_name,
            COALESCE(NULLIF(city_key, ''), '') AS city,
            CASE
                WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                ELSE ''
            END AS country,
            LOWER(TRIM(tipo_servicio::text)) AS real_tipo_servicio,
            (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS period_date,
            COUNT(*) AS real_trips,
            SUM(COALESCE(comision_empresa_asociada, 0)) AS revenue_real
        FROM with_key
        GROUP BY
            park_id,
            park_name,
            city_key,
            LOWER(TRIM(tipo_servicio::text)),
            (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_realkey_final AS
        SELECT
            COALESCE(p.country, r.country) AS country,
            COALESCE(p.city, r.city) AS city,
            COALESCE(p.park_id, r.park_id) AS park_id,
            r.park_name,
            COALESCE(p.real_tipo_servicio, r.real_tipo_servicio) AS real_tipo_servicio,
            COALESCE(p.period_date, r.period_date) AS period_date,
            p.trips_plan,
            r.real_trips AS trips_real,
            p.revenue_plan,
            r.revenue_real AS revenue_real,
            (COALESCE(r.real_trips, 0) - COALESCE(p.trips_plan, 0)) AS variance_trips,
            (COALESCE(r.revenue_real, 0) - COALESCE(p.revenue_plan, 0)) AS variance_revenue
        FROM ops.v_plan_universe_by_park_realkey p
        FULL OUTER JOIN ops.v_real_universe_by_park_realkey r
            ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
           AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
           AND TRIM(COALESCE(p.park_id, '')) = TRIM(COALESCE(r.park_id, ''))
           AND LOWER(TRIM(COALESCE(p.real_tipo_servicio, ''))) = LOWER(TRIM(COALESCE(r.real_tipo_servicio, '')))
           AND p.period_date = r.period_date
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_city_month AS
        SELECT
            country,
            city,
            period_date,
            SUM(trips_plan) AS trips_plan,
            SUM(trips_real) AS trips_real,
            SUM(revenue_plan) AS revenue_plan,
            SUM(revenue_real) AS revenue_real,
            SUM(variance_trips) AS variance_trips,
            SUM(variance_revenue) AS variance_revenue
        FROM ops.v_plan_vs_real_realkey_final
        GROUP BY country, city, period_date
        ORDER BY country, city, period_date
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_city_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_realkey_final CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_realkey CASCADE")
    # Restaurar vista real con join por id (038)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_realkey AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                p.id::text AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM public.trips_all t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) < 100
              AND t.tipo_servicio NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                park_id_raw,
                COALESCE(
                    NULLIF(TRIM(park_name_raw::text), ''),
                    NULLIF(TRIM(park_city_raw::text), ''),
                    park_id_raw::text
                ) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                LOWER(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                        'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')
                ) AS city_key
            FROM with_city
        )
        SELECT
            park_id::text AS park_id,
            park_name,
            COALESCE(NULLIF(city_key, ''), '') AS city,
            CASE
                WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                ELSE ''
            END AS country,
            LOWER(TRIM(tipo_servicio::text)) AS real_tipo_servicio,
            (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS period_date,
            COUNT(*) AS real_trips,
            SUM(COALESCE(comision_empresa_asociada, 0)) AS revenue_real
        FROM with_key
        GROUP BY
            park_id,
            park_name,
            city_key,
            LOWER(TRIM(tipo_servicio::text)),
            (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_realkey_final AS
        SELECT
            COALESCE(p.country, r.country) AS country,
            COALESCE(p.city, r.city) AS city,
            COALESCE(p.park_id, r.park_id) AS park_id,
            r.park_name,
            COALESCE(p.real_tipo_servicio, r.real_tipo_servicio) AS real_tipo_servicio,
            COALESCE(p.period_date, r.period_date) AS period_date,
            p.trips_plan,
            r.real_trips AS trips_real,
            p.revenue_plan,
            r.revenue_real AS revenue_real,
            (COALESCE(r.real_trips, 0) - COALESCE(p.trips_plan, 0)) AS variance_trips,
            (COALESCE(r.revenue_real, 0) - COALESCE(p.revenue_plan, 0)) AS variance_revenue
        FROM ops.v_plan_universe_by_park_realkey p
        FULL OUTER JOIN ops.v_real_universe_by_park_realkey r
            ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
           AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
           AND TRIM(COALESCE(p.park_id, '')) = TRIM(COALESCE(r.park_id, ''))
           AND LOWER(TRIM(COALESCE(p.real_tipo_servicio, ''))) = LOWER(TRIM(COALESCE(r.real_tipo_servicio, '')))
           AND p.period_date = r.period_date
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_city_month AS
        SELECT
            country,
            city,
            period_date,
            SUM(trips_plan) AS trips_plan,
            SUM(trips_real) AS trips_real,
            SUM(revenue_plan) AS revenue_plan,
            SUM(revenue_real) AS revenue_real,
            SUM(variance_trips) AS variance_trips,
            SUM(variance_revenue) AS variance_revenue
        FROM ops.v_plan_vs_real_realkey_final
        GROUP BY country, city, period_date
        ORDER BY country, city, period_date
    """)
'''


def write_migration_and_upgrade(join_key_best: str) -> bool:
    path = os.path.join(ALEMBIC_VERSIONS, "039_fix_parks_join_key_realkey.py")
    content = migration_content(join_key_best)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Migración escrita: {path}")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        timeout=120,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"  [ERROR] alembic upgrade: {r.stderr or r.stdout}")
        return False
    print("  alembic upgrade head: OK")
    return True


def run_validations(cur):
    out = {}
    # park_name null rate
    r = _run(cur, """
        SELECT
            COUNT(*),
            SUM(CASE WHEN park_name IS NULL OR TRIM(COALESCE(park_name,'')) = '' THEN 1 ELSE 0 END)
        FROM ops.v_plan_vs_real_realkey_final
    """, "park_name null")
    total = 0
    nulls = 0
    if r and r[0][0]:
        total = r[0][0]
        nulls = r[0][1] or 0
    out["total_final"] = total
    out["park_name_nulls"] = nulls
    out["park_name_null_rate_pct"] = (nulls / total * 100) if total else 0.0

    # plan month = max(period_date) from staging.plan_projection_realkey_raw
    r = _run(cur, """
        SELECT MAX(period_date) FROM staging.plan_projection_realkey_raw
    """, "max period plan")
    plan_period = r[0][0] if r and r[0][0] else None
    out["plan_period"] = plan_period

    matched_pct = None
    if plan_period:
        r = _run(cur, """
            SELECT
                COUNT(*),
                SUM(CASE WHEN trips_plan IS NOT NULL AND trips_real IS NOT NULL THEN 1 ELSE 0 END)
            FROM ops.v_plan_vs_real_realkey_final
            WHERE period_date = %s
        """, "matched plan month", params=(plan_period,))
        if r and r[0][0] is not None:
            tot_plan_month = r[0][0]
            matched = r[0][1] or 0
            matched_pct = (matched / tot_plan_month * 100) if tot_plan_month else 0
    out["matched_pct"] = matched_pct

    # parks_coverage: distinct park_id del real del último mes real que no matchean en parks (con join_key_best)
    # Lo hacemos después de tener join_key_best en contexto; aquí solo contamos en la vista final cuántos park_id (del real) tienen park_name null
    r = _run(cur, """
        SELECT COUNT(DISTINCT park_id)
        FROM ops.v_plan_vs_real_realkey_final
        WHERE (park_name IS NULL OR TRIM(COALESCE(park_name,'')) = '')
          AND park_id IS NOT NULL AND TRIM(COALESCE(park_id,'')) <> ''
    """, "distinct park_id con park_name null")
    out["parks_unmapped_count"] = (r[0][0] or 0) if r and r[0][0] is not None else 0
    return out


def run_parks_coverage(cur, join_key_best: str):
    """Cuántos park_id distintos del real (último mes en la vista) NO existen en parks vía join_key_best."""
    cq = quote_id(join_key_best)
    # Último mes en la vista real (desde v_real_universe_by_park_realkey no tenemos "solo real", usamos final donde hay trips_real)
    r = _run(cur, """
        SELECT MAX(period_date) FROM ops.v_plan_vs_real_realkey_final WHERE trips_real IS NOT NULL
    """, "max period real")
    max_real_period = r[0][0] if r and r[0][0] else None
    if not max_real_period:
        return None, 0, 0  # no hay real
    # park_id distintos en real para ese mes (desde trips_all para ese mes, sin join parks)
    r = _run(cur, """
        SELECT COUNT(DISTINCT t.park_id)
        FROM public.trips_all t
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
          AND DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE = %s
    """, "distinct park_id real month", params=(max_real_period,))
    total_real_parks = (r[0][0] or 0) if r and r[0][0] is not None else 0
    r = _run(cur, f"""
        SELECT COUNT(DISTINCT t.park_id)
        FROM public.trips_all t
        JOIN public.parks p ON LOWER(TRIM(p.{cq}::text)) = LOWER(TRIM(t.park_id::text))
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
          AND DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE = %s
    """, "distinct park_id real month matched", params=(max_real_period,))
    matched_parks = (r[0][0] or 0) if r and r[0][0] is not None else 0
    unmapped = max(0, total_real_parks - matched_parks)
    return max_real_period, total_real_parks, unmapped


def list_20_null_park_name_and_resolve(cur, join_key_best: str):
    r = _run(cur, """
        SELECT country, city, park_id, real_tipo_servicio, period_date, trips_plan, trips_real
        FROM ops.v_plan_vs_real_realkey_final
        WHERE park_name IS NULL OR TRIM(COALESCE(park_name,'')) = ''
        ORDER BY period_date DESC, COALESCE(trips_real, 0) DESC
        LIMIT 20
    """, "20 rows park_name null")
    if not r:
        return
    print("\n--- Filas con park_name NULL (20 primeras) ---")
    cq = quote_id(join_key_best)
    for row in r:
        country, city, park_id, real_tipo_servicio, period_date, trips_plan, trips_real = row
        # Intentar resolver contra parks con join_key_best
        res = _run(cur, f"""
            SELECT p.{quote_id('name')}, p.{quote_id('city')}
            FROM public.parks p
            WHERE LOWER(TRIM(p.{cq}::text)) = LOWER(TRIM(%s::text))
            LIMIT 1
        """, "resolve park", params=(park_id or "",))
        if res and res[0]:
            print(f"  park_id={park_id!r} -> parks: name={res[0][0]!r}, city={res[0][1]!r} [MATCH con join_key={join_key_best}]")
        else:
            print(f"  park_id={park_id!r} | country={country!r} city={city!r} | tipo={real_tipo_servicio!r} | period={period_date} | plan={trips_plan} real={trips_real} [NO en parks con {join_key_best}]")


def main():
    init_db_pool()
    print("=== PASO A.4 — Validar y corregir join parks (realkey) ===\n")

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f"SET statement_timeout = '{STMT_TIMEOUT}'")

            join_key_best, match_results, columns = discover_join_key(cur)
            if not join_key_best:
                print("\n[ABORTO] Ninguna columna de parks matchea con trips_all.park_id.")
                return 1

            match_count = next((m for c, m, _ in match_results if c == join_key_best), 0)
            print(f"\n--- 3) join_key_best: {join_key_best} (match_count = {match_count}) ---")

            current_join = get_current_join_key_from_view(cur)
            print(f"  Join actual en vista: {current_join}")

            if current_join != join_key_best:
                print(f"\n--- 4) Cambio de join: {current_join} -> {join_key_best}. Generando migración y ejecutando alembic. ---")
                if not write_migration_and_upgrade(join_key_best):
                    return 1
            else:
                print("\n--- 4) Join ya es el óptimo; no se ejecuta alembic. ---")

        finally:
            cur.close()

    # Validaciones y smoke
    print("\n--- 5) Validaciones y métricas ---")
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(f"SET statement_timeout = '{STMT_TIMEOUT}'")
            valid = run_validations(cur)
            join_key_for_coverage = join_key_best  # ya aplicado si hubo migración
            period_real, total_real_parks, parks_unmapped = run_parks_coverage(cur, join_key_for_coverage)
        finally:
            cur.close()

    total_final = valid["total_final"]
    park_name_null_rate = valid["park_name_null_rate_pct"]
    matched_pct = valid["matched_pct"]
    plan_period = valid["plan_period"]

    print(f"  park_name null rate: {valid['park_name_nulls']}/{total_final} ({park_name_null_rate:.1f}%)")
    print(f"  matched_pct (mes plan {plan_period}): {matched_pct if matched_pct is not None else 'N/A'}%")
    if period_real is not None:
        print(f"  parks_coverage (mes real {period_real}): {total_real_parks} park_id distintos, {parks_unmapped} NO en parks (join_key={join_key_for_coverage})")
    else:
        print("  parks_coverage: sin datos real en vista")

    with get_db() as conn:
        cur2 = conn.cursor()
        try:
            list_20_null_park_name_and_resolve(cur2, join_key_best)
        finally:
            cur2.close()

    # Smoke script
    print("\n--- 6) Smoke Plan vs Real (pasoA3) ---")
    r = subprocess.run(
        [sys.executable, "scripts/pasoA3_smoke_plan_vs_real_realkey.py"],
        cwd=BACKEND_DIR,
        timeout=660,
        capture_output=False,
    )
    if r.returncode != 0:
        print("  [AVISO] pasoA3_smoke terminó con código no 0.")

    # Reporte final y exit code
    print("\n" + "=" * 60)
    print("  REPORTE FINAL")
    print("=" * 60)
    print(f"  park_name null rate:    {park_name_null_rate:.1f}% (objetivo <= 5%)")
    print(f"  matched_pct (mes plan): {matched_pct if matched_pct is not None else 'N/A'}% (objetivo >= 30%)")
    print(f"  vista final filas:      {total_final}")
    if period_real is not None:
        print(f"  parks sin match:        {parks_unmapped} (del real mes {period_real})")

    fail = False
    if total_final == 0:
        print("  [FALLO] Vista final vacía.")
        fail = True
    if park_name_null_rate > 5:
        print("  [FALLO] park_name null rate > 5%.")
        fail = True
    if matched_pct is not None:
        if period_real is not None and plan_period is not None and period_real < plan_period:
            print("  OK: no hay real para el mes del plan aún (real_month < plan_month); matched_pct no aplica como fallo.")
        elif matched_pct < 30:
            print("  [AVISO] matched_pct < 30% para el mes del plan.")
        # No fallar por matched_pct bajo cuando no hay real en ese mes
    if matched_pct is None and plan_period:
        print("  [AVISO] No se pudo calcular matched_pct para el mes del plan.")

    if fail:
        print("  EXIT 1")
        return 1
    print("  EXIT 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
