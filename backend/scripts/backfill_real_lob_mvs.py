"""
[DEPRECATED — camino principal REAL] Backfill Real LOB fact tables por rango (mes a mes).

El pipeline principal REAL ya no usa este script:
- real_rollup_day_fact es vista derivada de ops.mv_real_lob_day_v2 (migración 101).
- real_drill_dim_fact se puebla desde day_v2/week_v3 con scripts.populate_real_drill_from_hourly_chain.

Este script queda para compatibilidad/legacy (p. ej. repoblar drill/rollup desde fact solo si se
revierte la migración 101 o por recuperación puntual). No se ejecuta en run_pipeline_refresh_and_audit.

Uso (legacy):
  python -m scripts.backfill_real_lob_mvs --from 2025-01-01 --to 2025-12-01
  python -m scripts.backfill_real_lob_mvs --from 2025-01-01 --to 2025-12-01 --resume true --retries 5

Flags:
  --from YYYY-MM-01   Inicio del rango
  --to YYYY-MM-01     Fin del rango
  --resume            Reanudar desde checkpoint (default: true)
  --retries N         Intentos máximos por mes ante errores transitorios (default: 5)
  --sleep-base secs   Base para backoff exponencial en segundos (default: 2)

Checkpoint: backend/logs/backfill_real_lob_checkpoint.json
"""
import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, date, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

CHECKPOINT_DIR = os.path.join(BACKEND_DIR, "logs")
CHECKPOINT_FILE = os.path.join(CHECKPOINT_DIR, "backfill_real_lob_checkpoint.json")

# Errores transitorios que justifican retry
TRANSIENT_ERROR_PATTERNS = [
    "SSL connection has been closed",
    "server closed the connection unexpectedly",
    "could not receive data from server",
    "connection timed out",
    "connection reset",
    "connection already closed",
    "terminating connection due to administrator command",
    "FATAL: remaining connection slots reserved",
]


def _is_transient_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(p.lower() in msg for p in TRANSIENT_ERROR_PATTERNS)


def _parse_date(s: str) -> date:
    d = datetime.strptime(s, "%Y-%m-%d").date()
    return d.replace(day=1) if s.endswith("-01") else d


def _month_range(from_d: date, to_d: date):
    """Genera (start, end) por mes desde from_d hasta to_d."""
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
    """
    Conexión robusta: connect_timeout, keepalives, application_name.
    Usa parámetros individuales (DB_*) para evitar UnicodeDecodeError con DATABASE_URL.
    """
    from app.db.connection import _get_connection_params
    import psycopg2
    from psycopg2.extras import RealDictCursor

    params = dict(_get_connection_params())
    params["options"] = (params.get("options") or "").strip() + " -c application_name=ct_backfill_real_lob"
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
    cur.execute("SET idle_in_transaction_session_timeout = '0'")
    cur.execute("SET work_mem = '256MB'")
    cur.execute("SET maintenance_work_mem = '512MB'")
    return conn, cur


def _log_temp_or_fallback(cur) -> None:
    """Loguea temp usage; si no hay permisos, fallback a db_size."""
    try:
        cur.execute("""
            SELECT datname, temp_files, pg_size_pretty(temp_bytes) AS temp_bytes
            FROM pg_stat_database WHERE datname = current_database()
        """)
        r = cur.fetchone()
        if r:
            logger.info("TEMP: datname=%s temp_files=%s temp_bytes=%s", r.get("datname"), r.get("temp_files"), r.get("temp_bytes"))
            return
    except Exception:
        pass
    try:
        cur.execute("SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size")
        r = cur.fetchone()
        db_size = r.get("db_size", "?") if r else "?"
        logger.info("temp usage unavailable (insufficient permissions or stats disabled); db_size=%s", db_size)
    except Exception:
        logger.info("temp usage unavailable (insufficient permissions or stats disabled)")


def _safe_close(conn, cur) -> None:
    """Cierra cursor y conexión sin fallar si ya están cerrados."""
    try:
        if cur and not cur.closed:
            cur.close()
    except Exception:
        pass
    try:
        if conn and not conn.closed:
            conn.close()
    except Exception:
        pass


def _safe_rollback(conn) -> None:
    """Rollback solo si la conexión existe y está abierta."""
    if conn is None:
        return
    try:
        if hasattr(conn, "closed") and conn.closed == 0:
            conn.rollback()
    except Exception as e:
        logger.debug("rollback skipped or failed: %s", e)


def _load_checkpoint() -> dict | None:
    if not os.path.exists(CHECKPOINT_FILE):
        return None
    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("No se pudo leer checkpoint: %s", e)
        return None


def _save_checkpoint(month_str: str) -> None:
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    data = {"last_success_month": month_str, "timestamp": datetime.utcnow().isoformat()}
    try:
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("No se pudo guardar checkpoint: %s", e)


def _run_month(start_d: date, end_d: date, cur) -> None:
    """Ejecuta el backfill para un mes (drill_dim + rollup_day). Muestra filas insertadas/actualizadas."""
    cutoff_start = start_d.isoformat()
    cutoff_end = end_d.isoformat()

    cur.execute("""
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
              AND t.fecha_inicio_viaje::date >= %s::date
              AND t.fecha_inicio_viaje::date <= %s::date
              AND t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT b.*,
                CASE
                    WHEN b.park_city_raw::text ILIKE '%%%%cali%%%%' THEN 'cali'
                    WHEN b.park_city_raw::text ILIKE '%%%%bogot%%%%' THEN 'bogota'
                    WHEN b.park_city_raw::text ILIKE '%%%%medell%%%%' THEN 'medellin'
                    WHEN b.park_city_raw::text ILIKE '%%%%barranquilla%%%%' THEN 'barranquilla'
                    WHEN b.park_city_raw::text ILIKE '%%%%cucut%%%%' THEN 'cucuta'
                    WHEN b.park_city_raw::text ILIKE '%%%%bucaramanga%%%%' THEN 'bucaramanga'
                    WHEN b.park_city_raw::text ILIKE '%%%%lima%%%%' OR TRIM(COALESCE(b.park_name_raw::text,'')) = 'Yego' THEN 'lima'
                    WHEN b.park_city_raw::text ILIKE '%%%%arequip%%%%' THEN 'arequipa'
                    WHEN b.park_city_raw::text ILIKE '%%%%trujill%%%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(b.park_city_raw::text, '')))
                END AS city_norm_raw
            FROM base b
        ),
        with_country AS (
            SELECT w.*,
                COALESCE(NULLIF(TRIM(w.city_norm_raw), ''), 'sin_city') AS city_norm,
                COALESCE(d.country, f.country, 'unk') AS country,
                CASE WHEN w.park_key IS NULL THEN 'SIN_PARK'
                    ELSE COALESCE(NULLIF(TRIM(w.park_name_raw::text), ''), 'UNKNOWN_PARK (' || w.park_key::text || ')')
                END AS park_name,
                CASE WHEN w.park_catalog_id IS NOT NULL THEN
                    COALESCE(NULLIF(TRIM(w.park_name_raw::text), ''), 'Sin nombre') || ' — ' || COALESCE(NULLIF(TRIM(w.park_city_raw::text), ''), 'Sin ciudad')
                    ELSE COALESCE(NULLIF(TRIM(w.park_name_raw::text), ''), 'UNKNOWN_PARK (' || w.park_key::text || ')')
                END AS park_display_key,
                ops.validated_service_type(w.tipo_servicio::text) AS service_type_norm,
                canon.normalize_real_tipo_servicio(w.tipo_servicio::text) AS tipo_servicio_norm
            FROM with_city w
            LEFT JOIN ops.dim_city_country d ON d.city_norm = NULLIF(TRIM(w.city_norm_raw), '')
            LEFT JOIN ops.park_country_fallback f ON f.park_id = w.park_key
        ),
        with_lob AS (
            SELECT v.fecha_inicio_viaje, v.park_key, v.city_norm, v.park_display_key, v.service_type_norm, v.tipo_servicio_norm,
                v.comision_empresa_asociada, v.distancia_km, v.pago_corporativo,
                COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
                CASE WHEN v.pago_corporativo IS NOT NULL AND (v.pago_corporativo::numeric) <> 0 THEN 'B2B' ELSE 'B2C' END AS segment,
                v.country
            FROM with_country v
            LEFT JOIN canon.dim_real_service_type_lob m ON m.service_type_norm = v.tipo_servicio_norm AND m.is_active = true
        ),
        enriched AS (SELECT * FROM with_lob WHERE country IN ('co','pe')),
        all_agg AS (
            SELECT country, 'month' AS period_grain, DATE_TRUNC('month', fecha_inicio_viaje)::date AS period_start,
                segment, 'lob' AS breakdown, lob_group AS dimension_key, NULL::text AS dimension_id, NULL::text AS city,
                COUNT(*) AS trips, (-1)*SUM(comision_empresa_asociada)::numeric AS margin_total,
                (-1)*AVG(comision_empresa_asociada)::numeric AS margin_per_trip,
                (AVG(distancia_km)::numeric)/1000.0 AS km_avg,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END) AS b2b_trips,
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)) AS b2b_share,
                MAX(fecha_inicio_viaje) AS last_trip_ts
            FROM enriched GROUP BY country, segment, lob_group, DATE_TRUNC('month', fecha_inicio_viaje)::date
            UNION ALL
            SELECT country, 'week', DATE_TRUNC('week', fecha_inicio_viaje)::date, segment, 'lob', lob_group, NULL, NULL,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM enriched GROUP BY country, segment, lob_group, DATE_TRUNC('week', fecha_inicio_viaje)::date
            UNION ALL
            SELECT country, 'month', DATE_TRUNC('month', fecha_inicio_viaje)::date, segment, 'park', park_display_key, park_key, city_norm,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM enriched GROUP BY country, segment, city_norm, park_key, park_display_key, DATE_TRUNC('month', fecha_inicio_viaje)::date
            UNION ALL
            SELECT country, 'week', DATE_TRUNC('week', fecha_inicio_viaje)::date, segment, 'park', park_display_key, park_key, city_norm,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM enriched GROUP BY country, segment, city_norm, park_key, park_display_key, DATE_TRUNC('week', fecha_inicio_viaje)::date
            UNION ALL
            SELECT country, 'month', DATE_TRUNC('month', fecha_inicio_viaje)::date, segment, 'service_type', tipo_servicio_norm, NULL, NULL,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM enriched GROUP BY country, segment, tipo_servicio_norm, DATE_TRUNC('month', fecha_inicio_viaje)::date
            UNION ALL
            SELECT country, 'week', DATE_TRUNC('week', fecha_inicio_viaje)::date, segment, 'service_type', tipo_servicio_norm, NULL, NULL,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM enriched GROUP BY country, segment, tipo_servicio_norm, DATE_TRUNC('week', fecha_inicio_viaje)::date
        )
        INSERT INTO ops.real_drill_dim_fact (
            country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city,
            trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts
        )
        SELECT country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city,
            trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts
        FROM all_agg
        ON CONFLICT (country, period_grain, period_start, segment, breakdown, COALESCE(dimension_key,''), COALESCE(dimension_id,''), COALESCE(city,''))
        DO UPDATE SET
            trips = EXCLUDED.trips,
            margin_total = EXCLUDED.margin_total,
            margin_per_trip = EXCLUDED.margin_per_trip,
            km_avg = EXCLUDED.km_avg,
            b2b_trips = EXCLUDED.b2b_trips,
            b2b_share = EXCLUDED.b2b_share,
            last_trip_ts = EXCLUDED.last_trip_ts
    """, (cutoff_start, cutoff_end))
    drill_rows = cur.rowcount
    logger.info("Mes %s .. %s: real_drill_dim_fact filas insertadas/actualizadas = %s", cutoff_start, cutoff_end, drill_rows)

    cur.execute("""
        WITH base AS (
            SELECT (t.fecha_inicio_viaje)::date AS trip_day, t.fecha_inicio_viaje AS trip_ts,
                NULLIF(TRIM(t.park_id::text), '') AS park_id_norm, t.tipo_servicio, t.pago_corporativo,
                t.comision_empresa_asociada, t.distancia_km, p.id AS park_catalog_id, p.name AS park_name,
                p.city AS park_city, LOWER(TRIM(COALESCE(p.city,'')::text)) AS city_norm
            FROM ops.v_trips_real_canon t
            LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
              AND t.fecha_inicio_viaje::date >= %s::date AND t.fecha_inicio_viaje::date <= %s::date
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100 AND t.tipo_servicio::text NOT LIKE '%%%%->%%%%'
        ),
        with_country AS (
            SELECT b.*, COALESCE(d.country, f.country, 'unk') AS country,
                COALESCE(NULLIF(TRIM(b.park_city::text), ''), 'SIN_CITY') AS city,
                CASE WHEN b.park_id_norm IS NULL THEN 'SIN_PARK'
                    ELSE COALESCE(NULLIF(TRIM(b.park_name::text), ''), 'UNKNOWN_PARK (' || b.park_id_norm::text || ')')
                END AS park_name_resolved,
                CASE WHEN b.park_id_norm IS NULL THEN 'SIN_PARK_ID'
                    WHEN b.park_catalog_id IS NULL THEN 'PARK_NO_CATALOG' ELSE 'OK'
                END AS park_bucket,
                canon.normalize_real_tipo_servicio(b.tipo_servicio::text) AS real_tipo_norm
            FROM base b
            LEFT JOIN ops.dim_city_country d ON d.city_norm = b.city_norm
            LEFT JOIN ops.park_country_fallback f ON f.park_id = b.park_id_norm
        ),
        agg AS (
            SELECT v.trip_day, v.country, v.city, v.park_id_norm AS park_id, v.park_name_resolved, v.park_bucket,
                COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
                CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
                COUNT(*) AS trips, SUM(CASE WHEN v.pago_corporativo IS NOT NULL THEN 1 ELSE 0 END) AS b2b_trips,
                SUM(v.comision_empresa_asociada) AS margin_total_raw, ABS(SUM(v.comision_empresa_asociada)) AS margin_total_pos,
                SUM(COALESCE(v.distancia_km::numeric, 0)) / 1000.0 AS distance_total_km, MAX(v.trip_ts) AS last_trip_ts
            FROM with_country v
            LEFT JOIN canon.dim_real_service_type_lob m ON m.service_type_norm = v.real_tipo_norm AND m.is_active = true
            GROUP BY v.trip_day, v.country, v.city, v.park_id_norm, v.park_name_resolved, v.park_bucket,
                COALESCE(m.lob_group, 'UNCLASSIFIED'), CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END
        )
        INSERT INTO ops.real_rollup_day_fact (
            trip_day, country, city, park_id, park_name_resolved, park_bucket, lob_group, segment_tag,
            trips, b2b_trips, margin_total_raw, margin_total_pos, margin_unit_pos, distance_total_km, km_prom, last_trip_ts
        )
        SELECT a.trip_day, a.country, a.city, a.park_id, a.park_name_resolved, a.park_bucket, a.lob_group, a.segment_tag,
            a.trips, a.b2b_trips, a.margin_total_raw, a.margin_total_pos,
            CASE WHEN a.trips > 0 THEN a.margin_total_pos / a.trips ELSE NULL END,
            a.distance_total_km,
            CASE WHEN a.trips > 0 AND a.distance_total_km IS NOT NULL THEN a.distance_total_km / a.trips ELSE NULL END,
            a.last_trip_ts
        FROM agg a
        ON CONFLICT (trip_day, country, COALESCE(city,''), COALESCE(park_id,''), lob_group, segment_tag)
        DO UPDATE SET
            trips = EXCLUDED.trips, b2b_trips = EXCLUDED.b2b_trips,
            margin_total_raw = EXCLUDED.margin_total_raw, margin_total_pos = EXCLUDED.margin_total_pos,
            margin_unit_pos = EXCLUDED.margin_unit_pos, distance_total_km = EXCLUDED.distance_total_km,
            km_prom = EXCLUDED.km_prom, last_trip_ts = EXCLUDED.last_trip_ts
    """, (cutoff_start, cutoff_end))
    rollup_rows = cur.rowcount
    logger.info("Mes %s .. %s: real_rollup_day_fact filas insertadas/actualizadas = %s", cutoff_start, cutoff_end, rollup_rows)


def main() -> None:
    import psycopg2

    parser = argparse.ArgumentParser(description="Backfill Real LOB fact tables por rango")
    parser.add_argument("--from", dest="from_date", required=True, help="YYYY-MM-01 inicio")
    parser.add_argument("--to", dest="to_date", required=True, help="YYYY-MM-01 fin")
    parser.add_argument("--grain", default="month", choices=["month"], help="Granularidad (solo month)")
    parser.add_argument("--resume", type=lambda x: str(x).lower() in ("true", "1", "yes"), default=True, help="Reanudar desde checkpoint (default: true)")
    parser.add_argument("--retries", type=int, default=5, help="Intentos máximos por mes (default: 5)")
    parser.add_argument("--sleep-base", type=float, default=2.0, help="Base backoff en segundos (default: 2)")
    args = parser.parse_args()

    from_d = _parse_date(args.from_date)
    to_d = _parse_date(args.to_date)
    if from_d > to_d:
        logger.error("--from debe ser <= --to")
        sys.exit(1)

    months = list(_month_range(from_d, to_d))
    if not months:
        logger.info("No hay meses en el rango")
        return

    # Resolución de inicio con checkpoint
    start_from = from_d
    if args.resume:
        cp = _load_checkpoint()
        if cp and cp.get("last_success_month"):
            try:
                last = datetime.strptime(cp["last_success_month"], "%Y-%m-%d").date()
                if last.month == 12:
                    next_month = last.replace(year=last.year + 1, month=1)
                else:
                    next_month = last.replace(month=last.month + 1)
                if next_month <= to_d and next_month >= from_d:
                    start_from = next_month
                    logger.info("Reanudando desde %s (checkpoint: %s)", start_from, cp["last_success_month"])
            except Exception as e:
                logger.warning("Checkpoint inválido, empezando desde --from: %s", e)

    months_to_run = [(s, e) for s, e in months if s >= start_from]
    if not months_to_run:
        logger.info("Todos los meses ya procesados (checkpoint al día)")
        return

    total_start = time.time()
    ok_count = 0
    fail_count = 0
    failed_months = []

    for start_d, end_d in months_to_run:
        month_str = start_d.strftime("%Y-%m-01")
        last_attempt_error = None

        for attempt in range(1, args.retries + 1):
            conn = None
            cur = None
            t0 = time.time()
            logger.info("START mes %s attempt %d/%d", month_str, attempt, args.retries)

            try:
                conn, cur = _get_conn()
                _run_month(start_d, end_d, cur)
                conn.commit()
                duration = time.time() - t0
                _log_temp_or_fallback(cur)
                _save_checkpoint(month_str)
                ok_count += 1
                logger.info("OK mes %s duración %.1fs", month_str, duration)
                break
            except psycopg2.OperationalError as e:
                last_attempt_error = e
                if _is_transient_error(e):
                    logger.warning("FAIL mes %s attempt %d: %s (transitorio, reintentando)", month_str, attempt, str(e))
                    _safe_rollback(conn)
                    _safe_close(conn, cur)
                    if attempt < args.retries:
                        backoff = args.sleep_base * (2 ** (attempt - 1)) + random.uniform(0, 1)
                        logger.info("Backoff %.1fs antes de reintento", backoff)
                        time.sleep(backoff)
                else:
                    logger.exception("FAIL mes %s: %s (no transitorio)", month_str, str(e))
                    fail_count += 1
                    failed_months.append((month_str, str(e)))
                    _safe_rollback(conn)
                    _safe_close(conn, cur)
                    raise
            except psycopg2.InterfaceError as e:
                last_attempt_error = e
                if "connection already closed" in str(e).lower() or _is_transient_error(e):
                    logger.warning("FAIL mes %s attempt %d: %s (conexión cerrada, reintentando)", month_str, attempt, str(e))
                    _safe_close(conn, cur)
                    if attempt < args.retries:
                        backoff = args.sleep_base * (2 ** (attempt - 1)) + random.uniform(0, 1)
                        logger.info("Backoff %.1fs antes de reintento", backoff)
                        time.sleep(backoff)
                else:
                    logger.exception("FAIL mes %s: %s", month_str, str(e))
                    fail_count += 1
                    failed_months.append((month_str, str(e)))
                    _safe_close(conn, cur)
                    raise
            except Exception as e:
                logger.exception("FAIL mes %s: %s", month_str, str(e))
                fail_count += 1
                failed_months.append((month_str, str(e)))
                _safe_rollback(conn)
                _safe_close(conn, cur)
                raise
            finally:
                _safe_close(conn, cur)
        else:
            # Agotados todos los intentos: registrar y continuar al siguiente mes
            fail_count += 1
            err_msg = str(last_attempt_error or "unknown")
            failed_months.append((month_str, err_msg))
            logger.error("FAIL mes %s tras %d intentos: %s", month_str, args.retries, err_msg)

    total_duration = time.time() - total_start
    logger.info("Backfill completado: %d meses OK, %d fallidos, tiempo total %.1fs", ok_count, fail_count, total_duration)
    if failed_months:
        for m, err in failed_months:
            logger.info("  Fallido: %s — %s", m, err[:100])
        sys.exit(1)


if __name__ == "__main__":
    main()
