"""
Backfill de ops.real_drill_service_by_park desde ops.v_trips_real_canon por chunks.

Uso:
  python -m scripts.backfill_real_drill_service_by_park --from 2025-12-01 --to 2026-03-31 --chunk weekly --replace
  python -m scripts.backfill_real_drill_service_by_park --from 2025-01-01 --to 2025-12-31 --chunk monthly --dry-run
  python -m scripts.backfill_real_drill_service_by_park --from 2025-06-01 --to 2026-01-01 --country co

Flags:
  --from YYYY-MM-DD   Inicio del rango
  --to YYYY-MM-DD     Fin del rango
  --chunk weekly|monthly  Tamaño de chunk (default: weekly)
  --replace           Truncar tabla antes y rellenar (sin staging intermedio; con staging sería reemplazo al final)
  --dry-run           Solo mostrar rangos, no escribir en BD
  --country co|pe     Filtrar por país (opcional; si no se pasa, ambos)
"""
import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

TABLE_NAME = "ops.real_drill_service_by_park"
# Staging con PID para no colisionar si corren dos procesos a la vez
STAGING_TABLE_PREFIX = "ops._staging_backfill_real_drill_service_by_park"


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _week_range(from_d: date, to_d: date):
    cur = from_d
    while cur < to_d:
        week_start = cur - timedelta(days=cur.weekday())
        week_end = week_start + timedelta(days=7)
        yield (week_start, min(week_end, to_d))
        cur = week_end


def _month_range(from_d: date, to_d: date):
    cur = from_d.replace(day=1)
    while cur <= to_d:
        if cur.month == 12:
            next_month = cur.replace(year=cur.year + 1, month=1)
        else:
            next_month = cur.replace(month=cur.month + 1)
        end = next_month - timedelta(days=1)
        yield (cur, min(end, to_d))
        cur = next_month


def _get_conn():
    from app.db.connection import _get_connection_params
    import psycopg2
    from psycopg2.extras import RealDictCursor

    params = _get_connection_params()
    params["options"] = (params.get("options") or "") + " -c application_name=ct_backfill_real_drill_service_by_park"
    conn = psycopg2.connect(
        **params,
        connect_timeout=15,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SET statement_timeout = '0'")
    cur.execute("SET lock_timeout = '5min'")
    cur.execute("SET work_mem = '256MB'")
    return conn, cur


# CTE igual a la lógica de la antigua migración 068, parametrizada por rango de fechas.
INSERT_CTE_SQL = """
    WITH base AS (
        SELECT
            t.fecha_inicio_viaje,
            NULLIF(TRIM(t.park_id::text), '') AS park_key,
            t.tipo_servicio,
            t.comision_empresa_asociada,
            t.distancia_km,
            t.pago_corporativo,
            p.id AS park_catalog_id,
            p.name AS park_name_raw,
            p.city AS park_city_raw
        FROM ops.v_trips_real_canon t
        LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')
        WHERE t.fecha_inicio_viaje IS NOT NULL
          AND t.fecha_inicio_viaje::date >= %(range_start)s
          AND t.fecha_inicio_viaje::date < %(range_end)s
          AND t.tipo_servicio IS NOT NULL
          AND t.condicion = 'Completado'
          AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
          AND t.tipo_servicio::text NOT LIKE '%%->%%'
    ),
    with_city AS (
        SELECT b.*,
            CASE
                WHEN b.park_city_raw::text ILIKE '%%cali%%' THEN 'cali'
                WHEN b.park_city_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                WHEN b.park_city_raw::text ILIKE '%%medell%%' THEN 'medellin'
                WHEN b.park_city_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                WHEN b.park_city_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                WHEN b.park_city_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                WHEN b.park_city_raw::text ILIKE '%%lima%%' OR TRIM(COALESCE(b.park_name_raw::text,'')) = 'Yego' THEN 'lima'
                WHEN b.park_city_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                WHEN b.park_city_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                ELSE LOWER(TRIM(COALESCE(b.park_city_raw::text, '')))
            END AS city_norm_raw
        FROM base b
    ),
    with_country AS (
        SELECT w.*,
            COALESCE(NULLIF(TRIM(w.city_norm_raw), ''), 'sin_city') AS city_norm,
            COALESCE(d.country, f.country, 'unk') AS country,
            CASE
                WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                WHEN LOWER(TRIM(w.tipo_servicio::text)) = 'confort+' THEN 'confort+'
                WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(w.tipo_servicio::text))
                WHEN LOWER(TRIM(w.tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                WHEN LENGTH(TRIM(w.tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                ELSE LOWER(TRIM(w.tipo_servicio::text))
            END AS tipo_servicio_norm,
            CASE WHEN w.pago_corporativo IS NOT NULL AND (w.pago_corporativo::numeric) <> 0 THEN 'B2B' ELSE 'B2C' END AS segment
        FROM with_city w
        LEFT JOIN ops.dim_city_country d ON d.city_norm = NULLIF(TRIM(w.city_norm_raw), '')
        LEFT JOIN ops.park_country_fallback f ON f.park_id = w.park_key
    ),
    enriched AS (
        SELECT park_key, city_norm, country, tipo_servicio_norm, segment, fecha_inicio_viaje, comision_empresa_asociada, distancia_km, pago_corporativo
        FROM with_country
        WHERE country IN ('co','pe')
    ),
    agg_month AS (
        SELECT country, 'month'::text AS period_grain, DATE_TRUNC('month', fecha_inicio_viaje)::date AS period_start,
            segment, park_key AS park_id, city_norm AS city, tipo_servicio_norm,
            COUNT(*)::bigint AS trips,
            (-1) * SUM(comision_empresa_asociada)::numeric AS margin_total,
            (-1) * AVG(comision_empresa_asociada)::numeric AS margin_per_trip,
            (AVG(distancia_km)::numeric) / 1000.0 AS km_avg,
            SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::bigint AS b2b_trips,
            (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0)) AS b2b_share,
            MAX(fecha_inicio_viaje) AS last_trip_ts
        FROM enriched
        GROUP BY country, segment, park_key, city_norm, tipo_servicio_norm, DATE_TRUNC('month', fecha_inicio_viaje)::date
    ),
    agg_week AS (
        SELECT country, 'week'::text AS period_grain, DATE_TRUNC('week', fecha_inicio_viaje)::date AS period_start,
            segment, park_key AS park_id, city_norm AS city, tipo_servicio_norm,
            COUNT(*)::bigint AS trips,
            (-1) * SUM(comision_empresa_asociada)::numeric AS margin_total,
            (-1) * AVG(comision_empresa_asociada)::numeric AS margin_per_trip,
            (AVG(distancia_km)::numeric) / 1000.0 AS km_avg,
            SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::bigint AS b2b_trips,
            (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0)) AS b2b_share,
            MAX(fecha_inicio_viaje) AS last_trip_ts
        FROM enriched
        GROUP BY country, segment, park_key, city_norm, tipo_servicio_norm, DATE_TRUNC('week', fecha_inicio_viaje)::date
    )
    SELECT * FROM agg_month
    UNION ALL
    SELECT * FROM agg_week
"""


def _run_chunk(cur, range_start: date, range_end: date, target_table: str, country_filter: str | None, upsert: bool) -> int:
    params = {"range_start": range_start, "range_end": range_end}
    if country_filter:
        # Filtrar en enriched ya está por country IN ('co','pe'); restringir a uno si se pide
        params["country_filter"] = country_filter

    params = {"range_start": range_start, "range_end": range_end}
    if country_filter:
        params["country_filter"] = country_filter
    # Filtro país en CTE enriched
    if country_filter:
        insert_cte = INSERT_CTE_SQL.replace(
            "WHERE country IN ('co','pe')",
            "WHERE country = %(country_filter)s"
        )
    else:
        insert_cte = INSERT_CTE_SQL

    # Idempotencia sin --replace: borrar rango que vamos a rellenar y luego INSERT
    if upsert:
        cur.execute(
            f"DELETE FROM {target_table} WHERE period_start >= %(range_start)s AND period_start < %(range_end)s",
            params,
        )

    full_sql = f"""
        INSERT INTO {target_table}
        (country, period_grain, period_start, segment, park_id, city, tipo_servicio_norm, trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts)
    """ + insert_cte
    cur.execute(full_sql, params)
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(description="Backfill ops.real_drill_service_by_park desde v_trips_real_canon")
    parser.add_argument("--from", dest="from_", required=True, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--to", required=True, help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--chunk", choices=["weekly", "monthly"], default="weekly", help="Tamaño de chunk")
    parser.add_argument("--replace", action="store_true", help="Truncar tabla antes de insertar")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar rangos, no escribir")
    parser.add_argument("--country", choices=["co", "pe"], default=None, help="Filtrar por país (opcional)")
    args = parser.parse_args()

    from_d = _parse_date(args.from_)
    to_d = _parse_date(args.to)
    if from_d >= to_d:
        logger.error("--from debe ser anterior a --to")
        sys.exit(1)

    chunks = list(_week_range(from_d, to_d) if args.chunk == "weekly" else _month_range(from_d, to_d))
    total = len(chunks)
    logger.info("Rango %s a %s, chunk=%s, total chunks=%s, replace=%s, dry_run=%s, country=%s",
                from_d, to_d, args.chunk, total, args.replace, args.dry_run, args.country)
    if args.dry_run:
        for i, (a, b) in enumerate(chunks, 1):
            print(f"  {i}/{total} {a} .. {b}", flush=True)
        return

    conn, cur = _get_conn()
    try:
        target_table = TABLE_NAME
        use_staging = args.replace
        staging_table = f"{STAGING_TABLE_PREFIX}_{os.getpid()}" if use_staging else None
        if use_staging:
            cur.execute(f"DROP TABLE IF EXISTS {staging_table} CASCADE")
            cur.execute(f"""
                CREATE TABLE {staging_table} (
                    country text NOT NULL,
                    period_grain text NOT NULL,
                    period_start date NOT NULL,
                    segment text NOT NULL,
                    park_id text,
                    city text,
                    tipo_servicio_norm text,
                    trips bigint NOT NULL,
                    margin_total numeric,
                    margin_per_trip numeric,
                    km_avg numeric,
                    b2b_trips bigint,
                    b2b_share numeric,
                    last_trip_ts timestamptz
                )
            """)
            target_table = staging_table
            conn.commit()

        total_rows = 0
        start_wall = time.perf_counter()
        for i, (range_start, range_end) in enumerate(chunks, start=1):
            chunk_start = time.perf_counter()
            rows = _run_chunk(cur, range_start, range_end, target_table, args.country, upsert=not use_staging)
            conn.commit()
            total_rows += rows
            elapsed = time.perf_counter() - chunk_start
            print(f"[backfill_real_drill_service_by_park] {i}/{total} {range_start} .. {range_end} rows=%s %.1fs" % (rows, elapsed), flush=True)
            logger.info("Chunk %s/%s %s..%s rows=%s %.1fs", i, total, range_start, range_end, rows, elapsed)

        if use_staging:
            print("[backfill_real_drill_service_by_park] Reemplazando tabla final desde staging (dedup por clave única)...", flush=True)
            cur.execute(f"TRUNCATE {TABLE_NAME}")
            # Staging puede tener duplicados: mismo mes aparece en varios chunks semanales; dedup por clave única.
            cur.execute(f"""
                INSERT INTO {TABLE_NAME}
                (country, period_grain, period_start, segment, park_id, city, tipo_servicio_norm, trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts)
                SELECT country, period_grain, period_start, segment, park_id, city, tipo_servicio_norm, trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts
                FROM (
                    SELECT DISTINCT ON (country, period_grain, period_start, segment, COALESCE(park_id,''), COALESCE(city,''), COALESCE(tipo_servicio_norm,''))
                        country, period_grain, period_start, segment, park_id, city, tipo_servicio_norm, trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts
                    FROM {staging_table}
                    ORDER BY country, period_grain, period_start, segment, COALESCE(park_id,''), COALESCE(city,''), COALESCE(tipo_servicio_norm,''), last_trip_ts DESC NULLS LAST
                ) sub
            """)
            cur.execute(f"DROP TABLE {staging_table}")
            conn.commit()

        wall = time.perf_counter() - start_wall
        print(f"[backfill_real_drill_service_by_park] Listo. Total filas=%s tiempo=%.1fs" % (total_rows, wall), flush=True)
        logger.info("Backfill listo. Total filas=%s tiempo=%.1fs", total_rows, wall)
    except Exception as e:
        conn.rollback()
        logger.exception("Backfill falló: %s", e)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
