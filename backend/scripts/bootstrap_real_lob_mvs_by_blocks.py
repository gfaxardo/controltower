#!/usr/bin/env python3
"""
FASE C — Bootstrap controlado por bloques temporales.

Pobla ops.mv_real_lob_month_v2 y ops.mv_real_lob_week_v2 sin un solo REFRESH gigante:
- Por mes: inserta en tabla staging bloque por bloque (ventana 120 días).
- Por semana: igual por rango de semanas.
- Al final: reemplaza la MV por los datos de staging e índices.

Registra progreso por bloque, duración, filas, errores y opcionalmente
observability_refresh_log (trigger_type='bootstrap').

Uso:
  cd backend && python scripts/bootstrap_real_lob_mvs_by_blocks.py
  python scripts/bootstrap_real_lob_mvs_by_blocks.py --only-month
  python scripts/bootstrap_real_lob_mvs_by_blocks.py --only-week
  python scripts/bootstrap_real_lob_mvs_by_blocks.py --dry-run
"""
import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass

try:
    from app.services.observability_service import log_refresh as _log_refresh
except ImportError:
    _log_refresh = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

WINDOW_DAYS = 120
SUB_BLOCK_DAYS = 15  # sub-bloques mensuales (días) para evitar timeout
SUB_BLOCK_DAYS_WEEK = 4  # sub-bloques semanales (días) para evitar timeout
STAGING_MONTH = "ops.staging_bootstrap_mv_real_lob_month_v2"
STAGING_WEEK = "ops.staging_bootstrap_mv_real_lob_week_v2"
SCRIPT_NAME = "bootstrap_real_lob_mvs_by_blocks.py"
# Vista index-friendly (098): usar _120d si existe para que el planner use índices
VIEW_BASE = "ops.v_real_trips_with_lob_v2"
VIEW_BASE_120D = "ops.v_real_trips_with_lob_v2_120d"

# Timeout por bloque/sub-bloque (ms). Variable de entorno: REAL_LOB_BOOTSTRAP_TIMEOUT_MS
def _bootstrap_timeout_ms() -> int:
    try:
        return int(os.environ.get("REAL_LOB_BOOTSTRAP_TIMEOUT_MS", "1800000"))
    except (TypeError, ValueError):
        return 1800000


def _real_lob_base_view(cur) -> str:
    """Devuelve la vista base a usar: _120d si existe (post-098), sino la estándar."""
    try:
        cur.execute(
            "SELECT 1 FROM pg_views WHERE schemaname = 'ops' AND viewname = 'v_real_trips_with_lob_v2_120d'"
        )
        if cur.fetchone():
            return VIEW_BASE_120D
    except Exception:
        pass
    return VIEW_BASE


def _get_global_max_date(cur, base_view: str | None = None) -> date:
    """Max fecha en ventana; si la vista tarda o falla, usa date.today() como cota."""
    view = base_view or VIEW_BASE
    try:
        cur.execute("SET statement_timeout = '120000'")  # 2 min max
        if view == VIEW_BASE_120D:
            cur.execute("SELECT (MAX(fecha_inicio_viaje))::date FROM " + view)
        else:
            cur.execute("""
                SELECT (MAX(fecha_inicio_viaje))::date
                FROM """ + view + """
                WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
            """)
        row = cur.fetchone()
        if row and row[0]:
            v = row[0]
            return v if hasattr(v, "year") else (v.date() if hasattr(v, "date") else v)
    except Exception as e:
        logger.warning("_get_global_max_date falló (%s), usando date.today()", e)
    return date.today()


def _month_starts() -> List[date]:
    end = date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    out = []
    d = date(start.year, start.month, 1)
    while d <= end:
        out.append(d)
        if d.month == 12:
            d = date(d.year + 1, 1, 1)
        else:
            d = date(d.year, d.month + 1, 1)
    return out


def _month_subblock_ranges(month_start: date, sub_block_days: int = SUB_BLOCK_DAYS) -> List[Tuple[date, date]]:
    """Rangos (inicio, fin) de sub_bloque_days dentro del mes. fin es exclusivo."""
    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)
    out = []
    d = month_start
    while d < month_end:
        end_d = min(d + timedelta(days=sub_block_days), month_end)
        out.append((d, end_d))
        d = end_d
    return out


def _week_starts() -> List[date]:
    end = date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    out = []
    # Lunes como inicio de semana (PostgreSQL DATE_TRUNC('week') usa lunes)
    d = start
    while d.weekday() != 0:
        d = d - timedelta(days=1)
    while d <= end:
        out.append(d)
        d = d + timedelta(days=7)
    return out


def _week_subblock_ranges(week_start: date, sub_block_days: int = SUB_BLOCK_DAYS_WEEK) -> List[Tuple[date, date]]:
    """Rangos (inicio, fin) de sub_block_days dentro de la semana. Fin exclusivo."""
    week_end = week_start + timedelta(days=7)
    out = []
    d = week_start
    while d < week_end:
        end_d = min(d + timedelta(days=sub_block_days), week_end)
        out.append((d, end_d))
        d = end_d
    return out


def _create_staging_month(cur) -> None:
    cur.execute("DROP TABLE IF EXISTS " + STAGING_MONTH)
    cur.execute("""
        CREATE TABLE %s AS
        SELECT
            a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
            a.month_start, a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            false AS is_open
        FROM (
            SELECT
                country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*)::bigint AS trips,
                SUM(revenue) AS revenue,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM ops.v_real_trips_with_lob_v2
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '1 day'
              AND fecha_inicio_viaje <  CURRENT_DATE - INTERVAL '0 days'
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                     (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        ) a
        LIMIT 0
    """ % (STAGING_MONTH,))
    cur.execute("""
        ALTER TABLE %s ADD CONSTRAINT uq_staging_month_v2_key
        UNIQUE (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)
    """ % (STAGING_MONTH,))


def _create_staging_week(cur) -> None:
    cur.execute("DROP TABLE IF EXISTS " + STAGING_WEEK)
    cur.execute("""
        CREATE TABLE %s AS
        SELECT
            a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
            a.week_start, a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            false AS is_open
        FROM (
            SELECT
                country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
                COUNT(*)::bigint AS trips,
                SUM(revenue) AS revenue,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM ops.v_real_trips_with_lob_v2
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '1 day'
              AND fecha_inicio_viaje <  CURRENT_DATE
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                     (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
        ) a
        LIMIT 0
    """ % (STAGING_WEEK,))
    cur.execute("""
        ALTER TABLE %s ADD CONSTRAINT uq_staging_week_v2_key
        UNIQUE (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)
    """ % (STAGING_WEEK,))


def _insert_month_subblock(
    cur, range_start: date, range_end: date, global_max_date, base_view: str
) -> int:
    """Inserta un sub-bloque [range_start, range_end) en staging; fusiona por mes con ON CONFLICT.
    Devuelve filas afectadas (insert + update)."""
    gmax = global_max_date or range_end
    cur.execute("""
        INSERT INTO """ + STAGING_MONTH + """
        WITH base AS (
            SELECT * FROM """ + base_view + """
            WHERE fecha_inicio_viaje >= %s
              AND fecha_inicio_viaje <  %s
        ),
        agg AS (
            SELECT
                country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*)::bigint AS trips,
                SUM(revenue) AS revenue,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                     (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        )
        SELECT
            a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
            a.month_start, a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            (a.month_start = DATE_TRUNC('month', %s::date)::DATE) AS is_open
        FROM agg a
        ON CONFLICT (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)
        DO UPDATE SET
            trips = """ + STAGING_MONTH + """.trips + EXCLUDED.trips,
            revenue = """ + STAGING_MONTH + """.revenue + EXCLUDED.revenue,
            margin_total = """ + STAGING_MONTH + """.margin_total + EXCLUDED.margin_total,
            distance_total_km = """ + STAGING_MONTH + """.distance_total_km + EXCLUDED.distance_total_km,
            max_trip_ts = GREATEST(""" + STAGING_MONTH + """.max_trip_ts, EXCLUDED.max_trip_ts),
            is_open = EXCLUDED.is_open
    """, (range_start, range_end, gmax))
    return cur.rowcount


def _insert_week_subblock(
    cur, range_start: date, range_end: date, global_max_date, base_view: str
) -> int:
    """Inserta un sub-bloque [range_start, range_end) en staging semana; fusiona por week con ON CONFLICT."""
    gmax = global_max_date or range_end
    cur.execute("""
        INSERT INTO """ + STAGING_WEEK + """
        WITH base AS (
            SELECT * FROM """ + base_view + """
            WHERE fecha_inicio_viaje >= %s
              AND fecha_inicio_viaje <  %s
        ),
        agg AS (
            SELECT
                country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
                COUNT(*)::bigint AS trips,
                SUM(revenue) AS revenue,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                     (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
        )
        SELECT
            a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
            a.week_start, a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            (a.week_start = DATE_TRUNC('week', %s::timestamp)::DATE) AS is_open
        FROM agg a
        ON CONFLICT (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)
        DO UPDATE SET
            trips = """ + STAGING_WEEK + """.trips + EXCLUDED.trips,
            revenue = """ + STAGING_WEEK + """.revenue + EXCLUDED.revenue,
            margin_total = """ + STAGING_WEEK + """.margin_total + EXCLUDED.margin_total,
            distance_total_km = """ + STAGING_WEEK + """.distance_total_km + EXCLUDED.distance_total_km,
            max_trip_ts = GREATEST(""" + STAGING_WEEK + """.max_trip_ts, EXCLUDED.max_trip_ts),
            is_open = EXCLUDED.is_open
    """, (range_start, range_end, gmax))
    return cur.rowcount


def bootstrap_month(dry_run: bool) -> Tuple[bool, str, int]:
    from app.db.connection import get_db, init_db_pool
    init_db_pool()
    total_rows = 0
    timeout_ms = _bootstrap_timeout_ms()
    try:
        if dry_run:
            months = _month_starts()
            sub_count = sum(len(_month_subblock_ranges(m)) for m in months)
            logger.info("DRY-RUN month_v2: %s meses, %s sub-bloques de %s días (sin conectar a BD)", len(months), sub_count, SUB_BLOCK_DAYS)
            return True, "dry_run", 0
        if _log_refresh:
            _log_refresh("ops.mv_real_lob_month_v2", status="running", script_name=SCRIPT_NAME, trigger_type="bootstrap")
        with get_db() as conn:
            conn.autocommit = True
            cur = conn.cursor()
            base_view = _real_lob_base_view(cur)
            global_max = _get_global_max_date(cur, base_view)
            logger.info("Bootstrap month_v2: global_max=%s, base_view=%s, timeout_ms=%s", global_max, base_view, timeout_ms)
            cur.execute("SET statement_timeout = %s", (str(timeout_ms),))
            _create_staging_month(cur)
            sub_idx = 0
            for i, month_start in enumerate(_month_starts()):
                for range_start, range_end in _month_subblock_ranges(month_start):
                    sub_idx += 1
                    t0 = time.monotonic()
                    try:
                        cur.execute("SET statement_timeout = %s", (str(timeout_ms),))
                        n = _insert_month_subblock(cur, range_start, range_end, global_max, base_view)
                        total_rows += n
                        logger.info(
                            "Sub-bloque %s [%s, %s): %s filas en %.1fs",
                            sub_idx, range_start, range_end, n, time.monotonic() - t0,
                        )
                    except Exception as e:
                        err_msg = "Sub-bloque fallido rango [%s, %s): %s" % (range_start, range_end, str(e)[:300])
                        logger.exception("%s", err_msg)
                        if _log_refresh:
                            _log_refresh("ops.mv_real_lob_month_v2", status="error", script_name=SCRIPT_NAME,
                                         trigger_type="bootstrap", error_message=err_msg)
                        raise RuntimeError(err_msg) from e
            # Reemplazar MV por staging
            cur.execute("SET statement_timeout = %s", (str(timeout_ms),))
            cur.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")
            cur.execute("CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS SELECT * FROM %s" % STAGING_MONTH)
            cur.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
            cur.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
            cur.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_lookup ON ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)")
            cur.execute("DROP TABLE IF EXISTS " + STAGING_MONTH)
            cur.close()
        if _log_refresh:
            _log_refresh("ops.mv_real_lob_month_v2", status="ok", script_name=SCRIPT_NAME, trigger_type="bootstrap",
                         rows_after=total_rows)
        return True, "ok", total_rows
    except Exception as e:
        if _log_refresh:
            _log_refresh("ops.mv_real_lob_month_v2", status="error", script_name=SCRIPT_NAME,
                         trigger_type="bootstrap", error_message=str(e)[:500])
        return False, str(e), total_rows


def bootstrap_week(dry_run: bool) -> Tuple[bool, str, int]:
    from app.db.connection import get_db, init_db_pool
    init_db_pool()
    total_rows = 0
    timeout_ms = _bootstrap_timeout_ms()
    try:
        if dry_run:
            weeks = _week_starts()
            sub_count = sum(len(_week_subblock_ranges(w)) for w in weeks)
            logger.info("DRY-RUN week_v2: %s semanas, %s sub-bloques de %s días (sin conectar a BD)", len(weeks), sub_count, SUB_BLOCK_DAYS_WEEK)
            return True, "dry_run", 0
        if _log_refresh:
            _log_refresh("ops.mv_real_lob_week_v2", status="running", script_name=SCRIPT_NAME, trigger_type="bootstrap")
        with get_db() as conn:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SET statement_timeout = %s", (str(timeout_ms),))
            base_view = _real_lob_base_view(cur)
            global_max = _get_global_max_date(cur, base_view)
            logger.info("Bootstrap week_v2: base_view=%s, timeout_ms=%s", base_view, timeout_ms)
            _create_staging_week(cur)
            sub_idx = 0
            for i, week_start in enumerate(_week_starts()):
                for range_start, range_end in _week_subblock_ranges(week_start):
                    sub_idx += 1
                    t0 = time.monotonic()
                    try:
                        cur.execute("SET statement_timeout = %s", (str(timeout_ms),))
                        n = _insert_week_subblock(cur, range_start, range_end, global_max, base_view)
                        total_rows += n
                        logger.info(
                            "Sub-bloque semana %s [%s, %s): %s filas en %.1fs",
                            sub_idx, range_start, range_end, n, time.monotonic() - t0,
                        )
                    except Exception as e:
                        err_msg = "Sub-bloque semana fallido rango [%s, %s): %s" % (range_start, range_end, str(e)[:300])
                        logger.exception("%s", err_msg)
                        if _log_refresh:
                            _log_refresh("ops.mv_real_lob_week_v2", status="error", script_name=SCRIPT_NAME,
                                         trigger_type="bootstrap", error_message=err_msg)
                        raise RuntimeError(err_msg) from e
            cur.execute("SET statement_timeout = %s", (str(timeout_ms),))
            cur.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
            cur.execute("CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS SELECT * FROM %s" % STAGING_WEEK)
            cur.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
            cur.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
            cur.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_week_lookup ON ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)")
            cur.execute("DROP TABLE IF EXISTS " + STAGING_WEEK)
            cur.close()
        if _log_refresh:
            _log_refresh("ops.mv_real_lob_week_v2", status="ok", script_name=SCRIPT_NAME, trigger_type="bootstrap",
                         rows_after=total_rows)
        return True, "ok", total_rows
    except Exception as e:
        if _log_refresh:
            _log_refresh("ops.mv_real_lob_week_v2", status="error", script_name=SCRIPT_NAME,
                         trigger_type="bootstrap", error_message=str(e)[:500])
        return False, str(e), total_rows


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Real LOB MVs por bloques temporales")
    parser.add_argument("--only-month", action="store_true")
    parser.add_argument("--only-week", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar bloques, no escribir")
    args = parser.parse_args()

    do_month = not args.only_week
    do_week = not args.only_month

    ok_month, msg_month, rows_month = True, "skipped", 0
    ok_week, msg_week, rows_week = True, "skipped", 0

    if do_month:
        logger.info("Iniciando bootstrap mensual por bloques (ventana %s días)", WINDOW_DAYS)
        ok_month, msg_month, rows_month = bootstrap_month(args.dry_run)
    if do_week:
        logger.info("Iniciando bootstrap semanal por bloques (ventana %s días)", WINDOW_DAYS)
        ok_week, msg_week, rows_week = bootstrap_week(args.dry_run)

    print("\n--- Bootstrap por bloques ---")
    print("month_v2: ok=%s msg=%s rows=%s" % (ok_month, msg_month, rows_month))
    print("week_v2:  ok=%s msg=%s rows=%s" % (ok_week, msg_week, rows_week))
    sys.exit(0 if (ok_month and ok_week) else 1)


if __name__ == "__main__":
    main()
