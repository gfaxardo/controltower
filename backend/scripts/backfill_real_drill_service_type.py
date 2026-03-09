"""
Backfill de filas breakdown='service_type' en ops.real_drill_dim_fact con tipo_servicio_norm (valor real).

Uso:
  python -m scripts.backfill_real_drill_service_type --from 2025-12-01 --to 2026-03-31 --chunk weekly --replace
  python -m scripts.backfill_real_drill_service_type --from 2025-01-01 --to 2025-12-31 --chunk monthly --dry-run

Flags:
  --from YYYY-MM-DD   Inicio del rango
  --to YYYY-MM-DD     Fin del rango
  --chunk weekly|monthly  Tamaño de chunk (default: weekly)
  --replace           Borrar todas las filas service_type antes y rellenar (recomendado para primera carga)
  --dry-run           Solo mostrar rangos, no escribir en BD
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

TABLE_NAME = "ops.real_drill_dim_fact"


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
    params["options"] = (params.get("options") or "") + " -c application_name=ct_backfill_real_drill_service_type"
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


# CTE equivalente a la antigua migración 069: tipo_servicio_norm como dimension_key para service_type.
INSERT_CTE_SQL = """
    WITH base AS (
        SELECT t.fecha_inicio_viaje, NULLIF(TRIM(t.park_id::text), '') AS park_key,
            t.tipo_servicio, t.comision_empresa_asociada, t.distancia_km, t.pago_corporativo,
            p.id AS park_catalog_id, p.name AS park_name_raw, p.city AS park_city_raw
        FROM ops.v_trips_real_canon t
        LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')
        WHERE t.fecha_inicio_viaje IS NOT NULL
          AND t.fecha_inicio_viaje::date >= %(range_start)s AND t.fecha_inicio_viaje::date < %(range_end)s
          AND t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
          AND LENGTH(TRIM(t.tipo_servicio::text)) < 100 AND t.tipo_servicio::text NOT LIKE '%%->%%'
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
            ops.validated_service_type(w.tipo_servicio::text) AS tipo_servicio_norm
        FROM with_city w
        LEFT JOIN ops.dim_city_country d ON d.city_norm = NULLIF(TRIM(w.city_norm_raw), '')
        LEFT JOIN ops.park_country_fallback f ON f.park_id = w.park_key
    ),
    enriched AS (
        SELECT park_key, city_norm, country, tipo_servicio_norm,
               fecha_inicio_viaje, comision_empresa_asociada, distancia_km, pago_corporativo
        FROM with_country
        WHERE country IN ('co','pe')
    ),
    service_agg AS (
        SELECT country, 'month' AS period_grain, DATE_TRUNC('month', fecha_inicio_viaje)::date AS period_start,
            CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 'B2B' ELSE 'B2C' END AS segment,
            'service_type' AS breakdown, tipo_servicio_norm AS dimension_key,
            NULL::text AS dimension_id, NULL::text AS city,
            COUNT(*) AS trips,
            (-1) * SUM(comision_empresa_asociada)::numeric AS margin_total,
            (-1) * AVG(comision_empresa_asociada)::numeric AS margin_per_trip,
            (AVG(distancia_km)::numeric) / 1000.0 AS km_avg,
            SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END) AS b2b_trips,
            (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0)) AS b2b_share,
            MAX(fecha_inicio_viaje) AS last_trip_ts
        FROM enriched
        GROUP BY country, (CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 'B2B' ELSE 'B2C' END), tipo_servicio_norm, DATE_TRUNC('month', fecha_inicio_viaje)::date
        UNION ALL
        SELECT country, 'week', DATE_TRUNC('week', fecha_inicio_viaje)::date,
            CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 'B2B' ELSE 'B2C' END,
            'service_type', tipo_servicio_norm, NULL, NULL,
            COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
            (AVG(distancia_km)::numeric)/1000.0,
            SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
            (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
            MAX(fecha_inicio_viaje)
        FROM enriched
        GROUP BY country, (CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 'B2B' ELSE 'B2C' END), tipo_servicio_norm, DATE_TRUNC('week', fecha_inicio_viaje)::date
    )
    SELECT country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city,
           trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts
    FROM service_agg
    WHERE (period_grain = 'month' AND period_start >= %(range_start)s AND period_start < %(range_end)s)
       OR (period_grain = 'week' AND period_start >= %(range_start)s AND period_start < %(range_end)s)
"""


def _run_chunk(cur, range_start: date, range_end: date) -> int:
    params = {"range_start": range_start, "range_end": range_end}
    cur.execute(
        f"DELETE FROM {TABLE_NAME} WHERE breakdown = 'service_type' AND period_start >= %(range_start)s AND period_start < %(range_end)s",
        params,
    )
    sql = f"""
        INSERT INTO {TABLE_NAME}
        (country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city,
         trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts)
    """ + INSERT_CTE_SQL
    cur.execute(sql, params)
    return cur.rowcount


def main():
    parser = argparse.ArgumentParser(description="Backfill real_drill_dim_fact breakdown=service_type con tipo_servicio_norm")
    parser.add_argument("--from", dest="from_", required=True, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--to", required=True, help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--chunk", choices=["weekly", "monthly"], default="weekly", help="Tamaño de chunk")
    parser.add_argument("--replace", action="store_true", help="Borrar todas las filas service_type antes de insertar")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar rangos, no escribir")
    args = parser.parse_args()

    from_d = _parse_date(args.from_)
    to_d = _parse_date(args.to)
    if from_d >= to_d:
        logger.error("--from debe ser anterior a --to")
        sys.exit(1)

    chunks = list(_week_range(from_d, to_d) if args.chunk == "weekly" else _month_range(from_d, to_d))
    total = len(chunks)
    logger.info("Rango %s a %s, chunk=%s, total chunks=%s, replace=%s, dry_run=%s",
                from_d, to_d, args.chunk, total, args.replace, args.dry_run)
    if args.dry_run:
        for i, (a, b) in enumerate(chunks, 1):
            print(f"  {i}/{total} {a} .. {b}", flush=True)
        return

    conn, cur = _get_conn()
    try:
        if args.replace:
            cur.execute("DELETE FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type'")
            conn.commit()
            logger.info("Eliminadas filas existentes con breakdown='service_type'")

        total_rows = 0
        start_wall = time.perf_counter()
        for i, (range_start, range_end) in enumerate(chunks, start=1):
            chunk_start = time.perf_counter()
            rows = _run_chunk(cur, range_start, range_end)
            conn.commit()
            total_rows += rows
            elapsed = time.perf_counter() - chunk_start
            print(f"[backfill_real_drill_service_type] {i}/{total} {range_start} .. {range_end} rows=%s %.1fs" % (rows, elapsed), flush=True)
            logger.info("Chunk %s/%s %s..%s rows=%s %.1fs", i, total, range_start, range_end, rows, elapsed)

        wall = time.perf_counter() - start_wall
        print(f"[backfill_real_drill_service_type] Listo. Total filas=%s tiempo=%.1fs" % (total_rows, wall), flush=True)
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
