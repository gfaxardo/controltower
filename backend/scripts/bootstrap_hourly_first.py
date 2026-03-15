#!/usr/bin/env python3
"""
CT-REAL-HOURLY-FIRST — Bootstrap por bloques de la nueva arquitectura.

Flujo:
  1. Bootstrap de ops.mv_real_lob_hour_v2 por sub-bloques diarios
  2. Derivar ops.mv_real_lob_day_v2 desde hourly (directo)
  3. Derivar ops.mv_real_lob_week_v3 desde hourly (directo)
  4. Derivar ops.mv_real_lob_month_v3 desde hourly (directo)

Uso:
  cd backend && python scripts/bootstrap_hourly_first.py
  python scripts/bootstrap_hourly_first.py --only-hour
  python scripts/bootstrap_hourly_first.py --only-day
  python scripts/bootstrap_hourly_first.py --only-week
  python scripts/bootstrap_hourly_first.py --only-month
  python scripts/bootstrap_hourly_first.py --dry-run
"""
import argparse
import logging
import os
import sys
import time
from datetime import date, timedelta
from typing import List, Tuple

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
SUB_BLOCK_DAYS = 7
SCRIPT_NAME = "bootstrap_hourly_first.py"

STAGING_HOUR = "ops.staging_bootstrap_mv_real_lob_hour_v2"

MV_HOUR = "ops.mv_real_lob_hour_v2"
MV_DAY = "ops.mv_real_lob_day_v2"
MV_WEEK = "ops.mv_real_lob_week_v3"
MV_MONTH = "ops.mv_real_lob_month_v3"


def _timeout_ms() -> int:
    try:
        return int(os.environ.get("REAL_LOB_BOOTSTRAP_TIMEOUT_MS", "1800000"))
    except (TypeError, ValueError):
        return 1800000


def _date_ranges(days: int = WINDOW_DAYS, block: int = SUB_BLOCK_DAYS) -> List[Tuple[date, date]]:
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=days)
    out = []
    d = start
    while d < end:
        e = min(d + timedelta(days=block), end)
        out.append((d, e))
        d = e
    return out


def _set_timeout(cur, ms: int):
    cur.execute("SET statement_timeout = %s", (str(ms),))


def bootstrap_hour(dry_run: bool) -> Tuple[bool, str, int]:
    from app.db.connection import get_db, init_db_pool
    init_db_pool()
    ranges = _date_ranges()
    if dry_run:
        logger.info("DRY-RUN hour: %d bloques de %d días", len(ranges), SUB_BLOCK_DAYS)
        return True, "dry_run", 0

    total_rows = 0
    timeout_ms = _timeout_ms()
    if _log_refresh:
        _log_refresh(MV_HOUR, status="running", script_name=SCRIPT_NAME, trigger_type="bootstrap")

    try:
        with get_db() as conn:
            conn.autocommit = True
            cur = conn.cursor()
            _set_timeout(cur, timeout_ms)

            cur.execute("DROP TABLE IF EXISTS " + STAGING_HOUR)
            cur.execute("""
                CREATE TABLE {stg} (
                    trip_date DATE,
                    trip_hour INT,
                    country TEXT,
                    city TEXT,
                    park_id TEXT,
                    park_name TEXT,
                    lob_group TEXT,
                    real_tipo_servicio_norm TEXT,
                    segment_tag TEXT,
                    trip_outcome_norm TEXT,
                    cancel_reason_norm TEXT,
                    cancel_reason_group TEXT,
                    requested_trips BIGINT DEFAULT 0,
                    completed_trips BIGINT DEFAULT 0,
                    cancelled_trips BIGINT DEFAULT 0,
                    unknown_outcome_trips BIGINT DEFAULT 0,
                    gross_revenue NUMERIC DEFAULT 0,
                    margin_total NUMERIC DEFAULT 0,
                    distance_total_km NUMERIC DEFAULT 0,
                    duration_total_minutes NUMERIC DEFAULT 0,
                    duration_avg_minutes NUMERIC,
                    cancellation_rate NUMERIC DEFAULT 0,
                    completion_rate NUMERIC DEFAULT 0,
                    max_trip_ts TIMESTAMP
                )
            """.format(stg=STAGING_HOUR))

            cur.execute("""
                CREATE UNIQUE INDEX uq_staging_hour_key ON {stg} (
                    trip_date, trip_hour, country, city, park_id,
                    lob_group, real_tipo_servicio_norm, segment_tag,
                    trip_outcome_norm,
                    COALESCE(cancel_reason_norm, ''),
                    COALESCE(cancel_reason_group, '')
                )
            """.format(stg=STAGING_HOUR))

            for i, (r_start, r_end) in enumerate(ranges):
                t0 = time.monotonic()
                _set_timeout(cur, timeout_ms)
                cur.execute("""
                    INSERT INTO {stg}
                    SELECT
                        trip_date, trip_hour, country, city, park_id, park_name,
                        lob_group, real_tipo_servicio_norm, segment_tag,
                        trip_outcome_norm, cancel_reason_norm, cancel_reason_group,

                        COUNT(*) AS requested_trips,
                        COUNT(*) FILTER (WHERE is_completed) AS completed_trips,
                        COUNT(*) FILTER (WHERE is_cancelled) AS cancelled_trips,
                        COUNT(*) FILTER (WHERE NOT is_completed AND NOT is_cancelled) AS unknown_outcome_trips,

                        SUM(gross_revenue) AS gross_revenue,
                        SUM(margin_total) AS margin_total,
                        SUM(distance_km) AS distance_total_km,
                        SUM(trip_duration_minutes) AS duration_total_minutes,
                        AVG(trip_duration_minutes) AS duration_avg_minutes,

                        CASE WHEN COUNT(*) > 0
                            THEN ROUND((COUNT(*) FILTER (WHERE is_cancelled))::numeric / COUNT(*)::numeric, 4)
                            ELSE 0 END AS cancellation_rate,
                        CASE WHEN COUNT(*) > 0
                            THEN ROUND((COUNT(*) FILTER (WHERE is_completed))::numeric / COUNT(*)::numeric, 4)
                            ELSE 0 END AS completion_rate,

                        MAX(fecha_inicio_viaje) AS max_trip_ts
                    FROM ops.v_real_trip_fact_v2
                    WHERE trip_date >= %s AND trip_date < %s
                    GROUP BY
                        trip_date, trip_hour, country, city, park_id, park_name,
                        lob_group, real_tipo_servicio_norm, segment_tag,
                        trip_outcome_norm, cancel_reason_norm, cancel_reason_group
                    ON CONFLICT (
                        trip_date, trip_hour, country, city, park_id,
                        lob_group, real_tipo_servicio_norm, segment_tag,
                        trip_outcome_norm,
                        COALESCE(cancel_reason_norm, ''),
                        COALESCE(cancel_reason_group, '')
                    ) DO UPDATE SET
                        requested_trips = {stg}.requested_trips + EXCLUDED.requested_trips,
                        completed_trips = {stg}.completed_trips + EXCLUDED.completed_trips,
                        cancelled_trips = {stg}.cancelled_trips + EXCLUDED.cancelled_trips,
                        unknown_outcome_trips = {stg}.unknown_outcome_trips + EXCLUDED.unknown_outcome_trips,
                        gross_revenue = {stg}.gross_revenue + EXCLUDED.gross_revenue,
                        margin_total = {stg}.margin_total + EXCLUDED.margin_total,
                        distance_total_km = {stg}.distance_total_km + EXCLUDED.distance_total_km,
                        duration_total_minutes = {stg}.duration_total_minutes + EXCLUDED.duration_total_minutes,
                        max_trip_ts = GREATEST({stg}.max_trip_ts, EXCLUDED.max_trip_ts)
                """.format(stg=STAGING_HOUR), (r_start, r_end))
                n = cur.rowcount
                total_rows += n
                logger.info("Bloque %d/%d [%s, %s): %d filas en %.1fs",
                            i + 1, len(ranges), r_start, r_end, n, time.monotonic() - t0)

            _set_timeout(cur, timeout_ms)

            # Swap: rename staging → MV via intermediate table
            cur.execute("DROP MATERIALIZED VIEW IF EXISTS " + MV_HOUR + " CASCADE")

            # Create MV as a standalone copy (not linked to staging)
            cur.execute("""
                CREATE MATERIALIZED VIEW {mv} AS
                SELECT
                    trip_date, trip_hour, country, city, park_id, park_name,
                    lob_group, real_tipo_servicio_norm, segment_tag,
                    trip_outcome_norm, cancel_reason_norm, cancel_reason_group,
                    requested_trips, completed_trips, cancelled_trips, unknown_outcome_trips,
                    gross_revenue, margin_total, distance_total_km,
                    duration_total_minutes, duration_avg_minutes,
                    cancellation_rate, completion_rate, max_trip_ts
                FROM {stg}
            """.format(mv=MV_HOUR, stg=STAGING_HOUR))

            cur.execute("""CREATE UNIQUE INDEX uq_mv_real_lob_hour_v2
                ON {mv} (
                    trip_date, trip_hour, country, city, park_id,
                    lob_group, real_tipo_servicio_norm, segment_tag,
                    trip_outcome_norm,
                    COALESCE(cancel_reason_norm, ''),
                    COALESCE(cancel_reason_group, '')
                )""".format(mv=MV_HOUR))
            cur.execute("CREATE INDEX idx_mv_hour_v2_date ON {mv} (trip_date)".format(mv=MV_HOUR))
            cur.execute("CREATE INDEX idx_mv_hour_v2_country_date ON {mv} (country, trip_date)".format(mv=MV_HOUR))
            cur.execute("CREATE INDEX idx_mv_hour_v2_hour ON {mv} (trip_hour)".format(mv=MV_HOUR))
            cur.execute("CREATE INDEX idx_mv_hour_v2_lob ON {mv} (lob_group, segment_tag)".format(mv=MV_HOUR))

            # Drop staging (safe: MV is a snapshot, no dependency)
            try:
                cur.execute("DROP TABLE IF EXISTS " + STAGING_HOUR)
            except Exception as e:
                logger.warning("No se pudo eliminar staging (ignorado): %s", e)
            cur.close()

        if _log_refresh:
            _log_refresh(MV_HOUR, status="ok", script_name=SCRIPT_NAME,
                         trigger_type="bootstrap", rows_after=total_rows)
        return True, "ok", total_rows
    except Exception as e:
        if _log_refresh:
            _log_refresh(MV_HOUR, status="error", script_name=SCRIPT_NAME,
                         trigger_type="bootstrap", error_message=str(e)[:500])
        logger.exception("Bootstrap hour falló")
        return False, str(e), total_rows


def _rebuild_derived_mv(mv_name: str, sql_def: str, indexes: List[str], dry_run: bool) -> Tuple[bool, str, int]:
    if dry_run:
        logger.info("DRY-RUN %s: se reconstruiría desde hourly", mv_name)
        return True, "dry_run", 0

    from app.db.connection import get_db, init_db_pool
    init_db_pool()
    timeout_ms = _timeout_ms()

    if _log_refresh:
        _log_refresh(mv_name, status="running", script_name=SCRIPT_NAME, trigger_type="bootstrap")

    try:
        with get_db() as conn:
            conn.autocommit = True
            cur = conn.cursor()
            _set_timeout(cur, timeout_ms)
            cur.execute("DROP MATERIALIZED VIEW IF EXISTS %s CASCADE" % mv_name)
            cur.execute(sql_def)
            for idx_sql in indexes:
                cur.execute(idx_sql)
            cur.execute("SELECT COUNT(*) FROM %s" % mv_name)
            row_count = cur.fetchone()[0]
            cur.close()

        if _log_refresh:
            _log_refresh(mv_name, status="ok", script_name=SCRIPT_NAME,
                         trigger_type="bootstrap", rows_after=row_count)
        logger.info("%s reconstruida: %d filas", mv_name, row_count)
        return True, "ok", row_count
    except Exception as e:
        if _log_refresh:
            _log_refresh(mv_name, status="error", script_name=SCRIPT_NAME,
                         trigger_type="bootstrap", error_message=str(e)[:500])
        logger.exception("Rebuild %s falló", mv_name)
        return False, str(e), 0


def bootstrap_day(dry_run: bool) -> Tuple[bool, str, int]:
    sql = """
    CREATE MATERIALIZED VIEW ops.mv_real_lob_day_v2 AS
    SELECT
        trip_date, country, city, park_id, park_name,
        lob_group, real_tipo_servicio_norm, segment_tag,
        trip_outcome_norm, cancel_reason_norm, cancel_reason_group,
        SUM(requested_trips) AS requested_trips,
        SUM(completed_trips) AS completed_trips,
        SUM(cancelled_trips) AS cancelled_trips,
        SUM(unknown_outcome_trips) AS unknown_outcome_trips,
        SUM(gross_revenue) AS gross_revenue,
        SUM(margin_total) AS margin_total,
        SUM(distance_total_km) AS distance_total_km,
        SUM(duration_total_minutes) AS duration_total_minutes,
        CASE WHEN SUM(completed_trips) > 0
            THEN ROUND(SUM(duration_total_minutes) / SUM(completed_trips)::numeric, 2)
            ELSE NULL END AS duration_avg_minutes,
        CASE WHEN SUM(requested_trips) > 0
            THEN ROUND(SUM(cancelled_trips)::numeric / SUM(requested_trips)::numeric, 4)
            ELSE 0 END AS cancellation_rate,
        CASE WHEN SUM(requested_trips) > 0
            THEN ROUND(SUM(completed_trips)::numeric / SUM(requested_trips)::numeric, 4)
            ELSE 0 END AS completion_rate,
        MAX(max_trip_ts) AS max_trip_ts
    FROM ops.mv_real_lob_hour_v2
    GROUP BY trip_date, country, city, park_id, park_name,
        lob_group, real_tipo_servicio_norm, segment_tag,
        trip_outcome_norm, cancel_reason_norm, cancel_reason_group
    """
    indexes = [
        """CREATE UNIQUE INDEX uq_mv_real_lob_day_v2
            ON ops.mv_real_lob_day_v2 (
                trip_date, country, city, park_id,
                lob_group, real_tipo_servicio_norm, segment_tag,
                trip_outcome_norm,
                COALESCE(cancel_reason_norm, ''),
                COALESCE(cancel_reason_group, '')
            )""",
        "CREATE INDEX idx_mv_day_v2_country_date ON ops.mv_real_lob_day_v2 (country, trip_date)",
        "CREATE INDEX idx_mv_day_v2_lob ON ops.mv_real_lob_day_v2 (lob_group, segment_tag)",
    ]
    return _rebuild_derived_mv(MV_DAY, sql, indexes, dry_run)


def bootstrap_week(dry_run: bool) -> Tuple[bool, str, int]:
    sql = """
    CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v3 AS
    WITH hourly AS (SELECT * FROM ops.mv_real_lob_hour_v2),
    global_max AS (SELECT MAX(max_trip_ts) AS m FROM hourly)
    SELECT
        DATE_TRUNC('week', h.trip_date)::date AS week_start,
        h.country, h.city, h.park_id, h.park_name,
        h.lob_group, h.real_tipo_servicio_norm, h.segment_tag,
        SUM(h.requested_trips) AS trips,
        SUM(h.completed_trips) AS completed_trips,
        SUM(h.cancelled_trips) AS cancelled_trips,
        SUM(h.gross_revenue) AS revenue,
        SUM(h.margin_total) AS margin_total,
        SUM(h.distance_total_km) AS distance_total_km,
        SUM(h.duration_total_minutes) AS duration_total_minutes,
        MAX(h.max_trip_ts) AS max_trip_ts,
        (DATE_TRUNC('week', h.trip_date)::date = DATE_TRUNC('week', g.m)::date) AS is_open
    FROM hourly h
    CROSS JOIN global_max g
    GROUP BY
        DATE_TRUNC('week', h.trip_date)::date,
        h.country, h.city, h.park_id, h.park_name,
        h.lob_group, h.real_tipo_servicio_norm, h.segment_tag,
        (DATE_TRUNC('week', h.trip_date)::date = DATE_TRUNC('week', g.m)::date)
    """
    indexes = [
        """CREATE UNIQUE INDEX uq_mv_real_lob_week_v3
            ON ops.mv_real_lob_week_v3 (
                country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start
            )""",
        "CREATE INDEX idx_mv_week_v3_ccpw ON ops.mv_real_lob_week_v3 (country, city, park_id, week_start)",
        "CREATE INDEX idx_mv_week_v3_ls ON ops.mv_real_lob_week_v3 (lob_group, segment_tag)",
    ]
    return _rebuild_derived_mv(MV_WEEK, sql, indexes, dry_run)


def bootstrap_month(dry_run: bool) -> Tuple[bool, str, int]:
    sql = """
    CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v3 AS
    WITH hourly AS (SELECT * FROM ops.mv_real_lob_hour_v2),
    global_max AS (SELECT MAX(max_trip_ts) AS m FROM hourly)
    SELECT
        DATE_TRUNC('month', h.trip_date)::date AS month_start,
        h.country, h.city, h.park_id, h.park_name,
        h.lob_group, h.real_tipo_servicio_norm, h.segment_tag,
        SUM(h.requested_trips) AS trips,
        SUM(h.completed_trips) AS completed_trips,
        SUM(h.cancelled_trips) AS cancelled_trips,
        SUM(h.gross_revenue) AS revenue,
        SUM(h.margin_total) AS margin_total,
        SUM(h.distance_total_km) AS distance_total_km,
        SUM(h.duration_total_minutes) AS duration_total_minutes,
        MAX(h.max_trip_ts) AS max_trip_ts,
        (DATE_TRUNC('month', h.trip_date)::date = DATE_TRUNC('month', g.m)::date) AS is_open
    FROM hourly h
    CROSS JOIN global_max g
    GROUP BY
        DATE_TRUNC('month', h.trip_date)::date,
        h.country, h.city, h.park_id, h.park_name,
        h.lob_group, h.real_tipo_servicio_norm, h.segment_tag,
        (DATE_TRUNC('month', h.trip_date)::date = DATE_TRUNC('month', g.m)::date)
    """
    indexes = [
        """CREATE UNIQUE INDEX uq_mv_real_lob_month_v3
            ON ops.mv_real_lob_month_v3 (
                country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start
            )""",
        "CREATE INDEX idx_mv_month_v3_ccpm ON ops.mv_real_lob_month_v3 (country, city, park_id, month_start)",
        "CREATE INDEX idx_mv_month_v3_ls ON ops.mv_real_lob_month_v3 (lob_group, segment_tag)",
    ]
    return _rebuild_derived_mv(MV_MONTH, sql, indexes, dry_run)


def main():
    parser = argparse.ArgumentParser(description="Bootstrap Hourly-First architecture")
    parser.add_argument("--only-hour", action="store_true")
    parser.add_argument("--only-day", action="store_true")
    parser.add_argument("--only-week", action="store_true")
    parser.add_argument("--only-month", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar plan, no ejecutar")
    args = parser.parse_args()

    specific = args.only_hour or args.only_day or args.only_week or args.only_month

    results = {}

    if not specific or args.only_hour:
        logger.info("═══ PASO 1/4: Bootstrap HOURLY ═══")
        ok, msg, rows = bootstrap_hour(args.dry_run)
        results["hour"] = (ok, msg, rows)
        if not ok and not specific:
            logger.error("Hour falló, no se pueden derivar day/week/month")
            _print_results(results)
            sys.exit(1)

    if not specific or args.only_day:
        logger.info("═══ PASO 2/4: Rebuild DAY desde HOURLY ═══")
        ok, msg, rows = bootstrap_day(args.dry_run)
        results["day"] = (ok, msg, rows)

    if not specific or args.only_week:
        logger.info("═══ PASO 3/4: Rebuild WEEK desde HOURLY ═══")
        ok, msg, rows = bootstrap_week(args.dry_run)
        results["week"] = (ok, msg, rows)

    if not specific or args.only_month:
        logger.info("═══ PASO 4/4: Rebuild MONTH desde HOURLY ═══")
        ok, msg, rows = bootstrap_month(args.dry_run)
        results["month"] = (ok, msg, rows)

    _print_results(results)
    all_ok = all(r[0] for r in results.values())
    sys.exit(0 if all_ok else 1)


def _print_results(results: dict):
    print("\n" + "=" * 60)
    print("CT-REAL-HOURLY-FIRST — Bootstrap Results")
    print("=" * 60)
    for layer, (ok, msg, rows) in results.items():
        status = "OK" if ok else "FAIL"
        print(f"  {layer:>8}: {status}  rows={rows}  msg={msg}")
    print("=" * 60)


if __name__ == "__main__":
    main()
