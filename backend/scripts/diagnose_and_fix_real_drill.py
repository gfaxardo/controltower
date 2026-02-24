"""
[YEGO CT] Autodiagnóstico + Auto-fix Real LOB Drill.
- Detecta columnas de trips_all (schema variable entre entornos)
- Mapea a nombres canónicos
- Ejecuta diagnóstico
- Genera y aplica FIX SQL (CREATE OR REPLACE VIEW)

Uso: cd backend && python -m scripts.diagnose_and_fix_real_drill [--diagnose-only] [--no-apply]
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Candidatos para auto-mapeo (primer match gana)
TS_COL_CANDIDATES = ["trip_ts", "fecha_inicio_viaje", "start_time", "created_at", "pickup_datetime"]
COUNTRY_COL_CANDIDATES = ["country", "pais", "country_code"]
CITY_COL_CANDIDATES = ["city", "ciudad", "city_name"]
PARK_ID_COL_CANDIDATES = ["park_id", "id_park", "park", "parkid"]
PARK_NAME_COL_CANDIDATES = ["park_name", "nombre_park", "park"]
TIPO_SERVICIO_COL_CANDIDATES = ["tipo_servicio", "real_tipo_servicio", "service_type", "service_class"]
B2B_COL_CANDIDATES = ["pago_corporativo", "corporate_payment", "is_corporate", "corporativo"]
MARGIN_COL_CANDIDATES = ["comision_empresa_asociada", "commission_partner", "partner_commission", "comision_partner"]
DIST_M_COL_CANDIDATES = ["distancia_km", "distance_meters", "distance", "trip_distance_m"]
CONDICION_COL_CANDIDATES = ["condicion", "status", "condition", "trip_status"]


def _pick_column(cols_lower_to_actual: dict[str, str], candidates: list[str]) -> str | None:
    """Primer candidato que exista en la tabla. Retorna nombre real (case-sensitive)."""
    for c in candidates:
        key = c.lower()
        if key in cols_lower_to_actual:
            return cols_lower_to_actual[key]
    return None


def discover_columns(conn) -> dict[str, str | None]:
    """Descubre columnas de trips_all y mapea a canónicos."""
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'trips_all'
        ORDER BY ordinal_position
    """)
    rows = cur.fetchall()
    cur.close()

    cols = {r[0].lower(): r[0] for r in rows}

    mapping = {
        "ts_col": _pick_column(cols, TS_COL_CANDIDATES),
        "country_col": _pick_column(cols, COUNTRY_COL_CANDIDATES),
        "city_col": _pick_column(cols, CITY_COL_CANDIDATES),
        "park_id_col": _pick_column(cols, PARK_ID_COL_CANDIDATES),
        "park_name_col": _pick_column(cols, PARK_NAME_COL_CANDIDATES),
        "tipo_servicio_col": _pick_column(cols, TIPO_SERVICIO_COL_CANDIDATES),
        "b2b_col": _pick_column(cols, B2B_COL_CANDIDATES),
        "margin_col": _pick_column(cols, MARGIN_COL_CANDIDATES),
        "dist_m_col": _pick_column(cols, DIST_M_COL_CANDIDATES),
        "condicion_col": _pick_column(cols, CONDICION_COL_CANDIDATES),
    }

    return mapping


def run_diagnosis(conn, m: dict) -> None:
    """Ejecuta diagnósticos y reporta."""
    cur = conn.cursor()

    ts_col = m.get("ts_col") or "fecha_inicio_viaje"
    country_col = m.get("country_col")  # None si no existe (se deriva de parks)
    city_col = m.get("city_col")
    park_id_col = m.get("park_id_col") or "park_id"
    park_name_col = m.get("park_name_col")

    logger.info("\n" + "=" * 60)
    logger.info("PASO 1: COLUMNAS ENCONTRADAS")
    logger.info("=" * 60)
    for k, v in m.items():
        logger.info(f"  {k}: {v or 'NO ENCONTRADA'}")

    logger.info("\n" + "=" * 60)
    logger.info("PASO 1.2: COVERAGE REAL (última fecha por país)")
    logger.info("=" * 60)
    if not country_col:
        logger.info("  (country no existe en trips_all; se deriva de parks.city)")
    else:
        try:
            cur.execute(f"""
                SELECT
                    {country_col}::text as country,
                    MIN(({ts_col})::date) as min_date,
                    MAX(({ts_col})::date) as last_date,
                    MAX({ts_col}) as last_ts
                FROM public.trips_all
                WHERE {country_col} IS NOT NULL
                GROUP BY 1
                ORDER BY 1
            """)
            for r in cur.fetchall():
                logger.info("  %s", r)
        except Exception as e:
            logger.warning("  Error: %s", e)
            conn.rollback()

    logger.info("\n" + "=" * 60)
    logger.info("PASO 1.3: TOP park_id (si country existe)")
    logger.info("=" * 60)
    if country_col and city_col:
        try:
            cur.execute(f"""
                SELECT {country_col} as country, {city_col} as city, {park_id_col} as park_id, COUNT(*) trips
                FROM public.trips_all
                WHERE LOWER(TRIM({country_col}::text)) = 'co' OR {country_col} IS NULL
                GROUP BY 1, 2, 3
                ORDER BY trips DESC
                LIMIT 20
            """)
            for r in cur.fetchall():
                logger.info("  %s", r)
        except Exception as e:
            logger.warning("  Error: %s", e)
            conn.rollback()
    else:
        logger.info("  (country/city no en trips_all; se deriva de parks)")

    tipo_col = m.get("tipo_servicio_col") or "tipo_servicio"
    logger.info("\n" + "=" * 60)
    logger.info("PASO 1.3: COVERAGE CATÁLOGO PARKS (CO)")
    logger.info("=" * 60)
    try:
        cur.execute(f"""
            SELECT t.park_id,
                   COUNT(*) trips,
                   MAX(p.id) IS NOT NULL as in_catalog
            FROM (
              SELECT NULLIF(TRIM({park_id_col}::text), '') as park_id
              FROM public.trips_all
              WHERE {tipo_col} IS NOT NULL
              LIMIT 50000
            ) t
            LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(t.park_id)
            WHERE t.park_id IS NOT NULL
            GROUP BY 1
            ORDER BY trips DESC
            LIMIT 30
        """)
        for r in cur.fetchall():
            logger.info(f"  {r}")
    except Exception as e:
        logger.warning("  Error: %s", e)
        conn.rollback()

    logger.info("\n" + "=" * 60)
    logger.info("PASO 1.3: park_id nulls y spaces")
    logger.info("=" * 60)
    try:
        cur.execute("SET statement_timeout = '15s'")
        cur.execute(f"""
            SELECT
              COUNT(*) FILTER (WHERE {park_id_col} IS NULL) as park_id_nulls,
              COUNT(*) FILTER (WHERE TRIM({park_id_col}::text) <> {park_id_col}::text AND {park_id_col} IS NOT NULL) as park_id_with_spaces
            FROM public.trips_all
        """)
        r = cur.fetchone()
        logger.info("  park_id_nulls: %s, park_id_with_spaces: %s", r[0], r[1])
    except Exception as e:
        logger.warning("  Error (puede timeout en tablas grandes): %s", e)
        conn.rollback()

    cur.close()


def _quote(col: str) -> str:
    return f'"{col}"' if col and " " in col else (col or "")


def generate_fix_sql(m: dict) -> str:
    """Genera SQL de FIX con las columnas mapeadas."""
    ts_col = m.get("ts_col") or "fecha_inicio_viaje"
    country_col = m.get("country_col")
    city_col = m.get("city_col")
    park_id_col = m.get("park_id_col") or "park_id"
    park_name_col = m.get("park_name_col")
    tipo_col = m.get("tipo_servicio_col") or "tipo_servicio"
    b2b_col = m.get("b2b_col") or "pago_corporativo"
    margin_col = m.get("margin_col") or "comision_empresa_asociada"
    dist_col = m.get("dist_m_col") or "distancia_km"
    cond_col = m.get("condicion_col") or "condicion"

    ts_q = _quote(ts_col)
    park_id_q = _quote(park_id_col)
    tipo_q = _quote(tipo_col)
    b2b_q = _quote(b2b_col)
    margin_q = _quote(margin_col)
    dist_q = _quote(dist_col)
    cond_q = _quote(cond_col)

    raw_park_name = f"t.{_quote(park_name_col)}" if park_name_col else "NULL::text"

    # distancia: si viene en metros, /1000; si ya es km, no dividir
    # Por convención: distancia_km en trips_all viene en metros (según docs)
    dist_km_expr = f"CASE WHEN {dist_q} IS NULL THEN NULL ELSE ({dist_q}::numeric)/1000.0 END"

    # Condición: filtrar Completado si existe
    cond_filter = f"AND t.{cond_q} = 'Completado'" if cond_col else ""

    base_select = f"""
        SELECT
            t.{ts_q} AS trip_ts,
            (t.{ts_q})::date AS trip_date,
            NULLIF(TRIM(t.{park_id_q}::text), '') AS park_id_norm,
            t.{park_id_q} AS park_id,
            t.{tipo_q},
            t.{b2b_q},
            t.{margin_q},
            t.{dist_q},
            p.id AS park_catalog_id,
            p.name AS park_catalog_name,
            p.city AS park_city,
            {raw_park_name} AS raw_park_name
        FROM public.trips_all t
        LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(NULLIF(TRIM(t.{park_id_q}::text), ''))
        WHERE t.{tipo_q} IS NOT NULL
          {cond_filter}
          AND LENGTH(TRIM(t.{tipo_q}::text)) < 100
          AND t.{tipo_q}::text NOT LIKE '%->%'
    """

    with_city = """
        WITH base AS (
            """ + base_select + """
        ),
        with_norm AS (
            SELECT
                trip_ts, trip_date, park_id_norm, park_id, tipo_servicio, pago_corporativo,
                comision_empresa_asociada, distancia_km, park_catalog_id, park_catalog_name, park_city, raw_park_name,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(tipo_servicio::text))
                END AS real_tipo_servicio_norm
            FROM base
        ),
        city_key AS (
            SELECT
                v.*,
                CASE
                    WHEN park_catalog_name::text ILIKE '%cali%' OR park_city::text ILIKE '%cali%' THEN 'cali'
                    WHEN park_catalog_name::text ILIKE '%bogot%' OR park_city::text ILIKE '%bogot%' THEN 'bogota'
                    WHEN park_catalog_name::text ILIKE '%barranquilla%' OR park_city::text ILIKE '%barranquilla%' THEN 'barranquilla'
                    WHEN park_catalog_name::text ILIKE '%medell%' OR park_city::text ILIKE '%medell%' THEN 'medellin'
                    WHEN park_catalog_name::text ILIKE '%cucut%' OR park_city::text ILIKE '%cucut%' THEN 'cucuta'
                    WHEN park_catalog_name::text ILIKE '%bucaramanga%' OR park_city::text ILIKE '%bucaramanga%' THEN 'bucaramanga'
                    WHEN park_catalog_name::text ILIKE '%lima%' OR park_city::text ILIKE '%lima%' OR TRIM(COALESCE(park_catalog_name::text,'')) = 'Yego' THEN 'lima'
                    WHEN park_catalog_name::text ILIKE '%arequip%' OR park_city::text ILIKE '%arequip%' THEN 'arequipa'
                    WHEN park_catalog_name::text ILIKE '%trujill%' OR park_city::text ILIKE '%trujill%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city::text, '')))
                END AS city_norm
            FROM with_norm v
        )
        SELECT
            v.trip_ts,
            v.trip_date,
            CASE
                WHEN v.city_norm IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                WHEN v.city_norm IN ('lima','arequipa','trujillo') THEN 'pe'
                ELSE ''
            END AS country,
            COALESCE(NULLIF(TRIM(v.city_norm), ''), 'unknown') AS city,
            v.park_id,
            NULL::text AS park_name_raw,
            v.tipo_servicio,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
            CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            v.pago_corporativo,
            v.comision_empresa_asociada,
            """ + dist_km_expr.replace(dist_q, "v.distancia_km").replace("distancia_km", "v.distancia_km") + """ AS distancia_km,
            COALESCE(NULLIF(TRIM(v.park_catalog_name::text), ''), COALESCE(NULLIF(TRIM(v.raw_park_name::text), ''), 'PARK ' || COALESCE(v.park_id::text, 'NULL'))) AS park_name_resolved,
            CASE
                WHEN v.park_id_norm IS NULL THEN 'SIN_PARK_ID'
                WHEN v.park_catalog_id IS NULL THEN 'PARK_NO_CATALOG'
                ELSE 'OK'
            END AS park_bucket
        FROM city_key v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_servicio_norm
    """

    # Corregir referencia a distancia en la expresión
    dist_km_inner = f"CASE WHEN v.distancia_km IS NULL THEN NULL ELSE (v.distancia_km::numeric)/1000.0 END"
    with_city = with_city.replace(
        dist_km_expr.replace(dist_q, "v.distancia_km").replace("distancia_km", "v.distancia_km"),
        dist_km_inner
    )

    # La base usa t.distancia_km - en la base_select ya está como distancia_km
    # Necesitamos que with_norm tenga distancia_km (alias de dist_col)
    # En base_select: t.{dist_q} -> en base será distancia_km
    base_select_fixed = base_select.replace(f"t.{dist_q}", "t.distancia_km" if dist_col != "distancia_km" else f"t.{dist_q}")
    # Mejor: usar alias en base
    base_select = base_select.replace(f"t.{dist_q}", f"t.{dist_q} AS distancia_km")

    # Corregir - en base_select tenemos t.distancia_km si dist_col=distancia_km, sino t.dist_col
    if dist_col not in ("distancia_km",):
        base_select = base_select.replace(f"t.{dist_q}", f"t.{dist_q} AS distancia_km")

    # Simplificar: la base siempre devuelve distancia_km como alias
    base_select = base_select.replace(f"t.{dist_q}", f"t.{dist_q} AS distancia_km")

    # Rebuild - the base_select string has the column names. Let me simplify.
    # The issue is that we're building SQL with variable column names. The base table has dist_col (e.g. distancia_km).
    # We select it as distancia_km for the rest of the chain. So:
    # base: SELECT ... t.distancia_km AS distancia_km ... (if dist_col=distancia_km)
    # or:   SELECT ... t.distance_meters AS distancia_km ... (if dist_col=distance_meters)
    base_select = base_select.replace(f"t.{dist_q}", f"t.{dist_q} AS distancia_km")

    # Actually the replace is wrong - we're replacing the same thing. Let me use a cleaner approach.
    # In base_select we have: t.{dist_q} - we need to add AS distancia_km
    # The base_select string has: ... t.{dist_q}, ... in the SELECT list
    # So we need: ... t.{dist_q} AS distancia_km, ...
    # The current base_select has: t.{dist_q} in the list. So the replacement would make it t.distancia_km AS distancia_km when dist_col=distancia_km.
    # That's redundant but correct. When dist_col=distance_meters, we'd have t.distance_meters AS distancia_km. Good.

    # Fix the with_city - the dist_km_expr replacement was wrong. The inner select uses v.distancia_km from the base.
    # And we need to convert to km: if the column is already in km, we don't divide. The prompt says DIST_M_COL = distance in meters.
    # So we always divide by 1000. Good.

    # Let me rebuild the SQL more carefully. The base_select needs to select the distance column.
    base_select = f"""
        SELECT
            t.{ts_q} AS trip_ts,
            (t.{ts_q})::date AS trip_date,
            NULLIF(TRIM(t.{park_id_q}::text), '') AS park_id_norm,
            t.{park_id_q} AS park_id,
            t.{tipo_q} AS tipo_servicio,
            t.{b2b_q} AS pago_corporativo,
            t.{margin_q} AS comision_empresa_asociada,
            t.{dist_q} AS distancia_raw,
            p.id AS park_catalog_id,
            p.name AS park_catalog_name,
            p.city AS park_city,
            {raw_park_name} AS raw_park_name
        FROM public.trips_all t
        LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(NULLIF(TRIM(t.{park_id_q}::text), ''))
        WHERE t.{tipo_q} IS NOT NULL
          {cond_filter}
          AND LENGTH(TRIM(t.{tipo_q}::text)) < 100
          AND t.{tipo_q}::text NOT LIKE '%->%'
    """

    # distancia_km: raw in meters, convert to km
    dist_km_select = "CASE WHEN b.distancia_raw IS NULL THEN NULL ELSE (b.distancia_raw::numeric)/1000.0 END AS distancia_km"

    with_city = """
        WITH base AS (
            """ + base_select + """
        ),
        with_norm AS (
            SELECT
                trip_ts, trip_date, park_id_norm, park_id, tipo_servicio, pago_corporativo,
                comision_empresa_asociada, distancia_raw, park_catalog_id, park_catalog_name, park_city, raw_park_name,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(tipo_servicio::text))
                END AS real_tipo_servicio_norm
            FROM base
        ),
        city_key AS (
            SELECT
                v.*,
                CASE
                    WHEN park_catalog_name::text ILIKE '%cali%' OR park_city::text ILIKE '%cali%' THEN 'cali'
                    WHEN park_catalog_name::text ILIKE '%bogot%' OR park_city::text ILIKE '%bogot%' THEN 'bogota'
                    WHEN park_catalog_name::text ILIKE '%barranquilla%' OR park_city::text ILIKE '%barranquilla%' THEN 'barranquilla'
                    WHEN park_catalog_name::text ILIKE '%medell%' OR park_city::text ILIKE '%medell%' THEN 'medellin'
                    WHEN park_catalog_name::text ILIKE '%cucut%' OR park_city::text ILIKE '%cucut%' THEN 'cucuta'
                    WHEN park_catalog_name::text ILIKE '%bucaramanga%' OR park_city::text ILIKE '%bucaramanga%' THEN 'bucaramanga'
                    WHEN park_catalog_name::text ILIKE '%lima%' OR park_city::text ILIKE '%lima%' OR TRIM(COALESCE(park_catalog_name::text,'')) = 'Yego' THEN 'lima'
                    WHEN park_catalog_name::text ILIKE '%arequip%' OR park_city::text ILIKE '%arequip%' THEN 'arequipa'
                    WHEN park_catalog_name::text ILIKE '%trujill%' OR park_city::text ILIKE '%trujill%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city::text, '')))
                END AS city_norm
            FROM with_norm v
        )
        SELECT
            v.trip_ts,
            v.trip_date,
            CASE
                WHEN v.city_norm IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                WHEN v.city_norm IN ('lima','arequipa','trujillo') THEN 'pe'
                ELSE ''
            END AS country,
            COALESCE(NULLIF(TRIM(v.city_norm), ''), 'unknown') AS city,
            v.park_id,
            NULL::text AS park_name_raw,
            v.tipo_servicio,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
            CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            v.pago_corporativo,
            v.comision_empresa_asociada,
            CASE WHEN v.distancia_raw IS NULL THEN NULL ELSE (v.distancia_raw::numeric)/1000.0 END AS distancia_km,
            COALESCE(NULLIF(TRIM(v.park_catalog_name::text), ''), COALESCE(NULLIF(TRIM(v.raw_park_name::text), ''), 'PARK ' || COALESCE(v.park_id::text, 'NULL'))) AS park_name_resolved,
            CASE
                WHEN v.park_id_norm IS NULL THEN 'SIN_PARK_ID'
                WHEN v.park_catalog_id IS NULL THEN 'PARK_NO_CATALOG'
                ELSE 'OK'
            END AS park_bucket
        FROM city_key v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_servicio_norm
    """

    sql_base = f"""
-- Auto-generated from diagnose_and_fix_real_drill.py
-- Mapped columns: ts={ts_col}, park_id={park_id_col}, tipo={tipo_col}, b2b={b2b_col}, margin={margin_col}, dist={dist_col}

DROP VIEW IF EXISTS ops.v_real_trips_base_drill CASCADE;
CREATE VIEW ops.v_real_trips_base_drill AS
""" + with_city.rstrip() + ";\n"

    sql_coverage = """
CREATE VIEW ops.v_real_data_coverage AS
SELECT
    country,
    MAX(trip_ts)::date AS last_trip_date,
    MAX(trip_ts) AS last_trip_ts,
    MIN(trip_ts)::date AS min_trip_date,
    date_trunc('month', MIN(trip_ts))::date AS min_month,
    date_trunc('week', MIN(trip_ts))::date AS min_week,
    date_trunc('month', MAX(trip_ts))::date AS last_month_with_data,
    date_trunc('week', MAX(trip_ts))::date AS last_week_with_data
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> ''
GROUP BY country;
"""

    sql_country_month = """
DROP VIEW IF EXISTS ops.v_real_drill_country_month CASCADE;
CREATE VIEW ops.v_real_drill_country_month AS
WITH
countries AS (
    SELECT country FROM (VALUES ('co'),('pe')) v(country)
    UNION
    SELECT DISTINCT country FROM ops.v_real_trips_base_drill
    WHERE country IS NOT NULL AND TRIM(country) <> ''
),
bounds AS (
    SELECT
        COALESCE((SELECT MIN(min_month) FROM ops.v_real_data_coverage WHERE min_month IS NOT NULL), date_trunc('month', CURRENT_DATE)::date) AS min_month,
        date_trunc('month', CURRENT_DATE)::date AS current_month
),
month_calendar AS (
    SELECT (generate_series(b.min_month, b.current_month, '1 month'::interval))::date AS period_start
    FROM bounds b
),
country_months AS (
    SELECT c.country, m.period_start
    FROM countries c
    CROSS JOIN month_calendar m
    WHERE c.country IN ('co','pe')
),
real_month AS (
    SELECT
        country,
        date_trunc('month', trip_ts)::date AS period_start,
        COUNT(*) AS trips,
        SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
        SUM(comision_empresa_asociada) AS margin_total,
        SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
        MAX(trip_ts) AS last_trip_ts
    FROM ops.v_real_trips_base_drill
    WHERE country IS NOT NULL AND TRIM(country) <> ''
    GROUP BY country, date_trunc('month', trip_ts)::date
),
combined AS (
    SELECT
        cm.country,
        cm.period_start,
        COALESCE(r.trips, 0) AS trips,
        COALESCE(r.b2b_trips, 0) AS b2b_trips,
        r.margin_total,
        r.distance_total_km,
        r.last_trip_ts,
        (cm.period_start = (SELECT current_month FROM bounds LIMIT 1)) AS period_is_current,
        (cm.period_start < (SELECT current_month FROM bounds LIMIT 1)) AS period_closed,
        LEAST(CURRENT_DATE - 1, (cm.period_start + interval '1 month' - interval '1 day')::date) AS expected_last_date
    FROM country_months cm
    LEFT JOIN real_month r ON r.country = cm.country AND r.period_start = cm.period_start
)
SELECT
    c.country,
    c.period_start,
    c.trips,
    c.b2b_trips,
    c.margin_total,
    CASE WHEN c.trips > 0 AND c.margin_total IS NOT NULL THEN c.margin_total / c.trips ELSE NULL END AS margin_unit_avg,
    c.distance_total_km,
    CASE WHEN c.trips > 0 AND c.distance_total_km IS NOT NULL THEN c.distance_total_km / c.trips ELSE NULL END AS distance_km_avg,
    CASE WHEN c.trips > 0 THEN c.b2b_trips::numeric / c.trips ELSE 0 END AS b2b_pct,
    c.last_trip_ts,
    c.expected_last_date,
    (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) AS falta_data,
    CASE
        WHEN c.period_is_current AND (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) THEN 'FALTA_DATA'
        WHEN c.period_is_current THEN 'ABIERTO'
        WHEN c.period_closed AND c.trips = 0 THEN 'VACIO'
        ELSE 'CERRADO'
    END AS estado
FROM combined c;
"""

    sql_country_week = """
DROP VIEW IF EXISTS ops.v_real_drill_country_week CASCADE;
CREATE VIEW ops.v_real_drill_country_week AS
WITH
countries AS (
    SELECT country FROM (VALUES ('co'),('pe')) v(country)
    UNION
    SELECT DISTINCT country FROM ops.v_real_trips_base_drill
    WHERE country IS NOT NULL AND TRIM(country) <> ''
),
bounds AS (
    SELECT
        COALESCE((SELECT MIN(min_week) FROM ops.v_real_data_coverage WHERE min_week IS NOT NULL), date_trunc('week', CURRENT_DATE)::date) AS min_week,
        date_trunc('week', CURRENT_DATE)::date AS current_week
),
week_calendar AS (
    SELECT (generate_series(b.min_week, b.current_week, '1 week'::interval))::date AS period_start
    FROM bounds b
),
country_weeks AS (
    SELECT c.country, w.period_start
    FROM countries c
    CROSS JOIN week_calendar w
    WHERE c.country IN ('co','pe')
),
real_week AS (
    SELECT
        country,
        date_trunc('week', trip_ts)::date AS period_start,
        COUNT(*) AS trips,
        SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
        SUM(comision_empresa_asociada) AS margin_total,
        SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
        MAX(trip_ts) AS last_trip_ts
    FROM ops.v_real_trips_base_drill
    WHERE country IS NOT NULL AND TRIM(country) <> ''
    GROUP BY country, date_trunc('week', trip_ts)::date
),
combined AS (
    SELECT
        cw.country,
        cw.period_start,
        COALESCE(r.trips, 0) AS trips,
        COALESCE(r.b2b_trips, 0) AS b2b_trips,
        r.margin_total,
        r.distance_total_km,
        r.last_trip_ts,
        (cw.period_start = (SELECT current_week FROM bounds LIMIT 1)) AS period_is_current,
        (cw.period_start < (SELECT current_week FROM bounds LIMIT 1)) AS period_closed,
        LEAST(CURRENT_DATE - 1, cw.period_start + 6) AS expected_last_date
    FROM country_weeks cw
    LEFT JOIN real_week r ON r.country = cw.country AND r.period_start = cw.period_start
)
SELECT
    c.country,
    c.period_start,
    c.trips,
    c.b2b_trips,
    c.margin_total,
    CASE WHEN c.trips > 0 AND c.margin_total IS NOT NULL THEN c.margin_total / c.trips ELSE NULL END AS margin_unit_avg,
    c.distance_total_km,
    CASE WHEN c.trips > 0 AND c.distance_total_km IS NOT NULL THEN c.distance_total_km / c.trips ELSE NULL END AS distance_km_avg,
    CASE WHEN c.trips > 0 THEN c.b2b_trips::numeric / c.trips ELSE 0 END AS b2b_pct,
    c.last_trip_ts,
    c.expected_last_date,
    (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) AS falta_data,
    CASE
        WHEN c.period_is_current AND (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) THEN 'FALTA_DATA'
        WHEN c.period_is_current THEN 'ABIERTO'
        WHEN c.period_closed AND c.trips = 0 THEN 'VACIO'
        ELSE 'CERRADO'
    END AS estado
FROM combined c;
"""

    sql_lob_month = """
DROP VIEW IF EXISTS ops.v_real_drill_lob_month CASCADE;
CREATE VIEW ops.v_real_drill_lob_month AS
SELECT
    country,
    lob_group,
    date_trunc('month', trip_ts)::date AS period_start,
    COUNT(*) AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
    SUM(comision_empresa_asociada) AS margin_total,
    CASE WHEN COUNT(*) > 0 AND SUM(comision_empresa_asociada) IS NOT NULL THEN SUM(comision_empresa_asociada) / COUNT(*) ELSE NULL END AS margin_unit_avg,
    SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
    CASE WHEN COUNT(*) > 0 THEN SUM(COALESCE(distancia_km::numeric, 0)) / COUNT(*) ELSE NULL END AS distance_km_avg,
    MAX(trip_ts) AS last_trip_ts,
    'Todos'::text AS segment_tag
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
GROUP BY country, lob_group, date_trunc('month', trip_ts)::date;
"""

    sql_lob_week = """
DROP VIEW IF EXISTS ops.v_real_drill_lob_week CASCADE;
CREATE VIEW ops.v_real_drill_lob_week AS
SELECT
    country,
    lob_group,
    date_trunc('week', trip_ts)::date AS period_start,
    COUNT(*) AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
    SUM(comision_empresa_asociada) AS margin_total,
    CASE WHEN COUNT(*) > 0 AND SUM(comision_empresa_asociada) IS NOT NULL THEN SUM(comision_empresa_asociada) / COUNT(*) ELSE NULL END AS margin_unit_avg,
    SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
    CASE WHEN COUNT(*) > 0 THEN SUM(COALESCE(distancia_km::numeric, 0)) / COUNT(*) ELSE NULL END AS distance_km_avg,
    MAX(trip_ts) AS last_trip_ts,
    'Todos'::text AS segment_tag
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
GROUP BY country, lob_group, date_trunc('week', trip_ts)::date;
"""

    sql_park_month = """
DROP VIEW IF EXISTS ops.v_real_drill_park_month CASCADE;
CREATE VIEW ops.v_real_drill_park_month AS
SELECT
    country,
    city,
    park_id,
    park_name_resolved,
    park_bucket,
    date_trunc('month', trip_ts)::date AS period_start,
    COUNT(*) AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
    SUM(comision_empresa_asociada) AS margin_total,
    CASE WHEN COUNT(*) > 0 AND SUM(comision_empresa_asociada) IS NOT NULL THEN SUM(comision_empresa_asociada) / COUNT(*) ELSE NULL END AS margin_unit_avg,
    SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
    CASE WHEN COUNT(*) > 0 THEN SUM(COALESCE(distancia_km::numeric, 0)) / COUNT(*) ELSE NULL END AS distance_km_avg,
    MAX(trip_ts) AS last_trip_ts
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> ''
GROUP BY country, city, park_id, park_name_resolved, park_bucket, date_trunc('month', trip_ts)::date;
"""

    sql_park_week = """
DROP VIEW IF EXISTS ops.v_real_drill_park_week CASCADE;
CREATE VIEW ops.v_real_drill_park_week AS
SELECT
    country,
    city,
    park_id,
    park_name_resolved,
    park_bucket,
    date_trunc('week', trip_ts)::date AS period_start,
    COUNT(*) AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
    SUM(comision_empresa_asociada) AS margin_total,
    CASE WHEN COUNT(*) > 0 AND SUM(comision_empresa_asociada) IS NOT NULL THEN SUM(comision_empresa_asociada) / COUNT(*) ELSE NULL END AS margin_unit_avg,
    SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
    CASE WHEN COUNT(*) > 0 THEN SUM(COALESCE(distancia_km::numeric, 0)) / COUNT(*) ELSE NULL END AS distance_km_avg,
    MAX(trip_ts) AS last_trip_ts
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> ''
GROUP BY country, city, park_id, park_name_resolved, park_bucket, date_trunc('week', trip_ts)::date;
"""

    full_sql = sql_base + sql_coverage + sql_country_month + sql_country_week + sql_lob_month + sql_lob_week + sql_park_month + sql_park_week
    return full_sql


def apply_fix(conn, sql: str) -> None:
    """Ejecuta el SQL de fix (cada statement por separado)."""
    # Quitar líneas que son solo comentarios
    sql_clean = "\n".join(
        line for line in sql.split("\n")
        if line.strip() and not line.strip().startswith("--")
    )
    statements = [s.strip() for s in sql_clean.split(";") if s.strip()]
    cur = conn.cursor()
    for stmt in statements:
        if not stmt:
            continue
        stmt = stmt if stmt.rstrip().endswith(";") else stmt + ";"
        try:
            cur.execute(stmt)
            logger.info("  OK: %s...", (stmt[:70] + "..").replace("\n", " "))
        except Exception as e:
            conn.rollback()
            logger.error("  ERROR: %s", e)
            logger.error("  Statement: %s", stmt[:250])
            raise
    cur.close()


def run_validation(conn) -> None:
    """
    Ejecuta checklist de validación post-fix.
    Usa MV o vistas drill (rápidas), sin fullscan. Timeout 120s solo para validaciones.
    """
    cur = conn.cursor()
    cur.execute("SET LOCAL statement_timeout = '120s'")
    logger.info("\n" + "=" * 60)
    logger.info("PASO 4: VALIDACIÓN POST-FIX (rápida, desde MV/vistas)")
    logger.info("=" * 60)

    logger.info("\nA) park_name_resolved nunca null (desde MV, LIMIT):")
    try:
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM ops.mv_real_rollup_day
                WHERE park_name_resolved IS NULL
                LIMIT 1
            ) x
        """)
        r = cur.fetchone()
        logger.info("  null_names: %s", r[0])
    except Exception as e:
        logger.warning("  Error (puede que MV no exista): %s", e)
        conn.rollback()

    logger.info("\nB) bucket CO (desde MV, últimos 30 días):")
    try:
        cur.execute("""
            SELECT park_bucket, SUM(trips) trips
            FROM ops.mv_real_rollup_day
            WHERE country='co' AND trip_day >= CURRENT_DATE - 30
            GROUP BY 1
            ORDER BY 2 DESC
        """)
        for r in cur.fetchall():
            logger.info("  %s: %s", r[0], r[1])
    except Exception as e:
        logger.warning("  Error: %s", e)
        conn.rollback()

    logger.info("\nC) summary max period (v_real_drill_country_month):")
    try:
        cur.execute("""
            SELECT country, MAX(period_start) as max_period
            FROM ops.v_real_drill_country_month
            GROUP BY 1
        """)
        for r in cur.fetchall():
            logger.info("  %s: %s", r[0], r[1])
    except Exception as e:
        logger.warning("  Error: %s", e)
        conn.rollback()

    logger.info("\nD) estado FALTA_DATA (mes actual):")
    try:
        cur.execute("""
            SELECT country, period_start, trips, estado, expected_last_date
            FROM ops.v_real_drill_country_month
            WHERE period_start = date_trunc('month', CURRENT_DATE)::date
            ORDER BY country
        """)
        for r in cur.fetchall():
            logger.info("  %s", r)
    except Exception as e:
        logger.warning("  Error: %s", e)
        conn.rollback()

    logger.info("\nE) ejemplo drill park CO (v_real_drill_park_month, LIMIT 50):")
    try:
        cur.execute("""
            SELECT city, park_id, park_name_resolved, park_bucket, trips
            FROM ops.v_real_drill_park_month
            WHERE country='co'
            ORDER BY period_start DESC, trips DESC
            LIMIT 50
        """)
        for r in cur.fetchall():
            logger.info("  %s", r)
    except Exception as e:
        logger.warning("  Error: %s", e)
        conn.rollback()

    cur.close()


def main():
    parser = argparse.ArgumentParser(description="Diagnose and fix Real LOB Drill views")
    parser.add_argument("--diagnose-only", action="store_true", help="Solo ejecutar diagnóstico, no aplicar fix")
    parser.add_argument("--no-apply", action="store_true", help="Generar SQL pero no ejecutarlo")
    parser.add_argument("--output-sql", type=str, default="", help="Ruta para guardar SQL generado")
    args = parser.parse_args()

    init_db_pool()
    with get_db() as conn:
        m = discover_columns(conn)
        run_diagnosis(conn, m)

        if args.diagnose_only:
            logger.info("\n[--diagnose-only] No se aplica fix.")
            return 0

        sql = generate_fix_sql(m)
        if args.output_sql:
            out_path = os.path.join(os.path.dirname(__file__), "..", args.output_sql)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(sql)
            logger.info("\nSQL guardado en: %s", out_path)

        if not args.no_apply:
            logger.info("\n" + "=" * 60)
            logger.info("PASO 2: APLICANDO FIX")
            logger.info("=" * 60)
            apply_fix(conn, sql)
            run_validation(conn)
        else:
            logger.info("\n[--no-apply] SQL no ejecutado.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
