"""
Ejecuta solo el UPDATE de segmentación de conductores sobre ops.real_drill_dim_fact.
Usar cuando populate_real_drill_from_hourly_chain ya guardó los INSERTs pero el UPDATE
hizo timeout. La vista v_real_driver_segment_agg es pesada.

Uso:
  python -m scripts.update_real_drill_segmentation_only --batch
  python -m scripts.update_real_drill_segmentation_only --timeout 7200
  python -m scripts.update_real_drill_segmentation_only --batch --per-period-timeout 600

--batch: actualiza por (period_grain, period_start); cada periodo tiene su propio timeout.
        Usa una consulta que filtra viajes por ese periodo (trip_date/week_start/month_start)
        para que el planificador solo lea los viajes del periodo y no materialice toda la vista.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

UPDATE_SQL = """
    UPDATE ops.real_drill_dim_fact d
    SET
        active_drivers = a.active_drivers,
        cancel_only_drivers = a.cancel_only_drivers,
        activity_drivers = a.activity_drivers,
        cancel_only_pct = a.cancel_only_pct
    FROM ops.v_real_driver_segment_agg a
    WHERE d.country = a.country
      AND d.period_grain = a.period_grain
      AND d.period_start = a.period_start
      AND d.segment = a.segment_tag
      AND d.breakdown = a.breakdown
      AND COALESCE(TRIM(d.dimension_key), '') = COALESCE(TRIM(a.dimension_key), '')
      AND COALESCE(TRIM(d.dimension_id), '') = COALESCE(TRIM(a.dimension_id), '')
      AND COALESCE(TRIM(d.city), '') = COALESCE(TRIM(a.city), '')
"""


def _segment_agg_for_period_sql(period_filter_column: str) -> str:
    """SQL que computa segment_agg solo para un periodo, filtrando viajes por columna.
    Así el planificador solo lee los viajes de ese periodo (trip_date/week_start/month_start).
    """
    return """
    WITH trips_filtered AS (
        SELECT * FROM ops.v_real_driver_segment_trips t
        WHERE t.{period_filter_column} = %s
    ),
    agg AS (
        SELECT
            driver_key,
            country,
            segment_tag,
            park_id,
            park_name,
            city,
            lob_group,
            service_type_norm,
            COUNT(*) FILTER (WHERE condicion = 'Completado') AS completed_cnt,
            COUNT(*) FILTER (WHERE condicion = 'Cancelado' OR condicion ILIKE '%%cancel%%') AS cancelled_cnt
        FROM trips_filtered
        GROUP BY driver_key, country, segment_tag, park_id, park_name, city, lob_group, service_type_norm
    ),
    tot AS (
        SELECT
            driver_key,
            country,
            segment_tag,
            SUM(completed_cnt) AS completed_cnt,
            SUM(cancelled_cnt) AS cancelled_cnt
        FROM agg
        GROUP BY driver_key, country, segment_tag
    ),
    park_rank AS (
        SELECT
            driver_key, country, segment_tag,
            park_id, park_name, city,
            SUM(completed_cnt + cancelled_cnt) AS activity,
            ROW_NUMBER() OVER (PARTITION BY driver_key, country, segment_tag ORDER BY SUM(completed_cnt + cancelled_cnt) DESC, park_id) AS rn
        FROM agg
        GROUP BY driver_key, country, segment_tag, park_id, park_name, city
    ),
    lob_rank AS (
        SELECT
            driver_key, country, segment_tag,
            lob_group,
            SUM(completed_cnt + cancelled_cnt) AS activity,
            ROW_NUMBER() OVER (PARTITION BY driver_key, country, segment_tag ORDER BY SUM(completed_cnt + cancelled_cnt) DESC, lob_group) AS rn
        FROM agg
        GROUP BY driver_key, country, segment_tag, lob_group
    ),
    svc_rank AS (
        SELECT
            driver_key, country, segment_tag,
            service_type_norm,
            SUM(completed_cnt + cancelled_cnt) AS activity,
            ROW_NUMBER() OVER (PARTITION BY driver_key, country, segment_tag ORDER BY SUM(completed_cnt + cancelled_cnt) DESC, service_type_norm) AS rn
        FROM agg
        GROUP BY driver_key, country, segment_tag, service_type_norm
    ),
    driver_period AS (
        SELECT
            t.driver_key,
            %s::text AS period_grain,
            %s AS period_start,
            t.country,
            t.segment_tag,
            p.park_id AS park_id_dom,
            p.park_name AS park_name_dom,
            p.city AS city_dom,
            l.lob_group AS lob_dom,
            s.service_type_norm AS service_type_dom,
            t.completed_cnt,
            t.cancelled_cnt,
            (t.completed_cnt > 0) AS is_active,
            (t.completed_cnt = 0 AND t.cancelled_cnt > 0) AS is_cancel_only,
            (t.completed_cnt > 0 OR t.cancelled_cnt > 0) AS is_activity
        FROM tot t
        LEFT JOIN (SELECT * FROM park_rank WHERE rn = 1) p ON p.driver_key = t.driver_key AND p.country = t.country AND p.segment_tag = t.segment_tag
        LEFT JOIN (SELECT * FROM lob_rank WHERE rn = 1) l ON l.driver_key = t.driver_key AND l.country = t.country AND l.segment_tag = t.segment_tag
        LEFT JOIN (SELECT * FROM svc_rank WHERE rn = 1) s ON s.driver_key = t.driver_key AND s.country = t.country AND s.segment_tag = t.segment_tag
    ),
    segment_agg AS (
        SELECT country, period_grain, period_start, segment_tag, 'lob'::text AS breakdown,
               lob_dom AS dimension_key, NULL::text AS dimension_id, NULL::text AS city,
               COUNT(DISTINCT driver_key) FILTER (WHERE is_active) AS active_drivers,
               COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only) AS cancel_only_drivers,
               COUNT(DISTINCT driver_key) FILTER (WHERE is_activity) AS activity_drivers,
               ROUND(100.0 * COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only) / NULLIF(COUNT(DISTINCT driver_key) FILTER (WHERE is_activity), 0), 4) AS cancel_only_pct
        FROM driver_period
        WHERE lob_dom IS NOT NULL
        GROUP BY country, period_grain, period_start, segment_tag, lob_dom
        UNION ALL
        SELECT country, period_grain, period_start, segment_tag, 'park'::text,
               COALESCE(NULLIF(TRIM(park_name_dom::text), ''), park_id_dom::text), park_id_dom, city_dom,
               COUNT(DISTINCT driver_key) FILTER (WHERE is_active),
               COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only),
               COUNT(DISTINCT driver_key) FILTER (WHERE is_activity),
               ROUND(100.0 * COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only) / NULLIF(COUNT(DISTINCT driver_key) FILTER (WHERE is_activity), 0), 4)
        FROM driver_period
        WHERE park_id_dom IS NOT NULL
        GROUP BY country, period_grain, period_start, segment_tag, park_id_dom, park_name_dom, city_dom
        UNION ALL
        SELECT country, period_grain, period_start, segment_tag, 'service_type'::text,
               COALESCE(service_type_dom, 'unknown'), NULL::text, NULL::text,
               COUNT(DISTINCT driver_key) FILTER (WHERE is_active),
               COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only),
               COUNT(DISTINCT driver_key) FILTER (WHERE is_activity),
               ROUND(100.0 * COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only) / NULLIF(COUNT(DISTINCT driver_key) FILTER (WHERE is_activity), 0), 4)
        FROM driver_period
        WHERE service_type_dom IS NOT NULL
        GROUP BY country, period_grain, period_start, segment_tag, service_type_dom
    )
    SELECT * FROM segment_agg
    """.format(period_filter_column=period_filter_column)


def run(timeout_sec: int = 3600, batch: bool = False, per_period_timeout: int = 600) -> bool:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    if batch:
        return _run_batch(per_period_timeout)
    logger.info("Actualizando segmentación en un solo UPDATE (timeout=%ss)...", timeout_sec)
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(timeout_sec * 1000),))
            cur.execute(UPDATE_SQL)
            n = cur.rowcount
            cur.close()
        logger.info("Segmentación actualizada: %s filas.", n)
        return True
    except Exception as e:
        logger.error("Segmentación no aplicada: %s", e)
        return False


def _run_batch(per_period_timeout_sec: int) -> bool:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT DISTINCT period_grain, period_start
            FROM ops.real_drill_dim_fact
            ORDER BY period_grain, period_start
        """)
        periods = cur.fetchall()
        cur.close()

    if not periods:
        logger.info("No hay periodos en real_drill_dim_fact.")
        return True

    logger.info("Actualizando segmentación por lotes (%s periodos, timeout %ss por periodo)...",
                len(periods), per_period_timeout_sec)
    total_updated = 0
    failed = []

    # Columna de filtro en v_real_driver_segment_trips para restringir a un solo periodo
    period_filter_col = {"day": "trip_date", "week": "week_start", "month": "month_start"}
    subquery_sql = _segment_agg_for_period_sql

    for i, row in enumerate(periods):
        pg, ps = row["period_grain"], row["period_start"]
        filter_col = period_filter_col.get(pg)
        if not filter_col:
            failed.append((pg, ps, "period_grain no soportado: " + str(pg)))
            continue
        try:
            with get_db() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SET statement_timeout = %s", (str(per_period_timeout_sec * 1000),))
                # Parámetros: filtro viajes (ps), period_grain y period_start en driver_period (pg, ps)
                subquery = subquery_sql(filter_col)
                cur.execute("""
                    UPDATE ops.real_drill_dim_fact d
                    SET
                        active_drivers = a.active_drivers,
                        cancel_only_drivers = a.cancel_only_drivers,
                        activity_drivers = a.activity_drivers,
                        cancel_only_pct = a.cancel_only_pct
                    FROM (""" + subquery + """) a
                    WHERE d.country = a.country
                      AND d.period_grain = a.period_grain
                      AND d.period_start = a.period_start
                      AND d.segment = a.segment_tag
                      AND d.breakdown = a.breakdown
                      AND COALESCE(TRIM(d.dimension_key), '') = COALESCE(TRIM(a.dimension_key), '')
                      AND COALESCE(TRIM(d.dimension_id), '') = COALESCE(TRIM(a.dimension_id), '')
                      AND COALESCE(TRIM(d.city), '') = COALESCE(TRIM(a.city), '')
                """, (ps, pg, ps))
                n = cur.rowcount
                cur.close()
            total_updated += n
            if (i + 1) % 20 == 0 or n > 0:
                logger.info("  %s/%s %s %s -> %s filas", i + 1, len(periods), pg, ps, n)
        except Exception as e:
            failed.append((pg, ps, str(e)))
            logger.warning("  %s %s falló: %s", pg, ps, e)

    if failed:
        logger.warning("%s periodos fallaron de %s.", len(failed), len(periods))
    logger.info("Segmentación por lotes: %s filas actualizadas en total.", total_updated)
    return len(failed) == 0


def main():
    ap = argparse.ArgumentParser(description="Solo UPDATE de segmentación en real_drill_dim_fact")
    ap.add_argument("--timeout", type=int, default=3600, help="Timeout para UPDATE único (segundos)")
    ap.add_argument("--batch", action="store_true", help="Actualizar por periodo (recomendado si el UPDATE único hace timeout)")
    ap.add_argument("--per-period-timeout", type=int, default=600, help="Timeout por periodo en --batch (segundos, default 600=10min)")
    args = ap.parse_args()
    ok = run(timeout_sec=args.timeout, batch=args.batch, per_period_timeout=args.per_period_timeout)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
