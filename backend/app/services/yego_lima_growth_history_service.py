"""
YEGO Lima Fleet Growth Tower — Historical Bootstrap Service (Fase 2B-R0).

Responsabilidades:
- Inspeccionar columnas de trips_2025/trips_2026 sin asumir nombres
- Detectar mapeo: driver_id, fecha, status, park_id, revenue
- Filtrar Lima (park_id) + completadas
- Agregar a daily, luego weekly con rolling metrics
- Clasificar historical_band
- Persistir via repository

NO consultas directas desde Loyalty hacia trips tras bootstrap.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

from app.db.connection import _get_connection_params
from app.settings import settings
from app.repositories.yego_lima_growth_history_repository import (
    upsert_history_daily,
    upsert_history_weekly,
    get_history_summary,
    get_history_sample as repo_get_history_sample,
)

logger = logging.getLogger(__name__)

SOURCE_BOOTSTRAP = "trips_bootstrap"
BATCH_SIZE = 5000

HISTORICAL_BAND_50_PLUS = "HISTORICAL_50_PLUS"
HISTORICAL_BAND_30_49 = "HISTORICAL_30_49"
HISTORICAL_BAND_10_29 = "HISTORICAL_10_29"
HISTORICAL_BAND_00_09 = "HISTORICAL_00_09"
HISTORICAL_BAND_NONE = "NO_HISTORY"

TABLE_COLUMN_CANDIDATES: Dict[str, List[str]] = {
    "driver_id": ["conductor_id", "driver_id", "driver_profile_id"],
    "trip_date": ["fecha_inicio_viaje", "trip_date", "fecha", "date", "activity_date"],
    "status": ["condicion", "estado", "status", "trip_status"],
    "park_id": ["park_id", "parque_id", "park"],
    "revenue": ["precio_yango_pro", "gross_revenue", "revenue", "total", "price", "precio"],
}


def _detect_columns_from_conn(conn, table_name: str) -> Tuple[Dict[str, str], List[str]]:
    mapping: Dict[str, str] = {}
    warnings: List[str] = []
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    existing = {r[0].lower() for r in cur.fetchall()}
    cur.close()
    for logical, candidates in TABLE_COLUMN_CANDIDATES.items():
        found = next((c.lower() for c in candidates if c.lower() in existing), None)
        if found:
            mapping[logical] = found
        else:
            warnings.append(f"Column '{logical}' not found in {table_name}")
    return mapping, warnings


def _validate_required(mapping: Dict[str, str], table_name: str) -> Optional[str]:
    missing = [r for r in ["driver_id", "trip_date", "status", "park_id"] if r not in mapping]
    return f"Missing required columns in {table_name}: {missing}" if missing else None


def _classify_historical_band(best_week: Optional[int]) -> str:
    if best_week is None:
        return HISTORICAL_BAND_NONE
    if best_week >= 50:
        return HISTORICAL_BAND_50_PLUS
    if best_week >= 30:
        return HISTORICAL_BAND_30_49
    if best_week >= 10:
        return HISTORICAL_BAND_10_29
    if best_week > 0:
        return HISTORICAL_BAND_00_09
    return HISTORICAL_BAND_NONE


def bootstrap_history(from_date_str: str, to_date_str: str) -> Dict[str, Any]:
    from_date = date.fromisoformat(from_date_str)
    to_date = date.fromisoformat(to_date_str)

    logger.info("Bootstrap history: %s to %s", from_date, to_date)

    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()
    if not park_id:
        return {"ok": False, "error": "YANGO_LIMA_PARK_ID not configured"}

    all_warnings: List[str] = []
    table_mappings: Dict[str, Dict[str, str]] = {}

    params = _get_connection_params()
    params["options"] = "-c statement_timeout=600000"
    conn = psycopg2.connect(**params)
    conn.autocommit = False
    logger.info("  Direct connection opened in %.1fs", 0)

    try:
        for table in ["trips_2025", "trips_2026"]:
            mapping, warnings = _detect_columns_from_conn(conn, table)
            all_warnings.extend(warnings)
            err = _validate_required(mapping, table)
            if err:
                all_warnings.append(err)
            else:
                table_mappings[table] = mapping

        if not table_mappings:
            return {"ok": False, "error": "No usable trips tables found", "warnings": all_warnings}

        daily_rows: List[Dict[str, Any]] = []

        for table, mapping in table_mappings.items():
            driver_col, date_col = mapping["driver_id"], mapping["trip_date"]
            status_col, park_col = mapping["status"], mapping["park_id"]
            revenue_col = mapping.get("revenue")
            revenue_select = f"SUM(COALESCE({revenue_col}, 0))" if revenue_col else "NULL::numeric"

            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"""
                SELECT {driver_col} AS driver_id, {date_col}::date AS trip_date,
                       COUNT(*) AS completed_orders, {revenue_select} AS gross_revenue
                FROM public.{table}
                WHERE {park_col} = %(park_id)s
                  AND LOWER({status_col}) = 'completado'
                  AND {date_col} >= %(from_ts)s::timestamp
                  AND {date_col} <= %(to_ts)s::timestamp
                  AND {driver_col} IS NOT NULL
                GROUP BY {driver_col}, {date_col}::date
            """, {
                "park_id": park_id,
                "from_ts": f"{from_date} 00:00:00",
                "to_ts": f"{to_date} 23:59:59",
            })
            logger.info("  %s: query complete, fetching...", table)

            batch, row_count = [], 0
            for row in cur:
                batch.append({
                    "date": row["trip_date"],
                    "driver_profile_id": row["driver_id"],
                    "completed_orders": int(row["completed_orders"] or 0),
                    "gross_revenue": float(row["gross_revenue"]) if row.get("gross_revenue") is not None else None,
                    "source": SOURCE_BOOTSTRAP,
                })
                row_count += 1
                if len(batch) >= BATCH_SIZE:
                    upsert_history_daily(batch)
                    daily_rows.extend(batch)
                    batch = []
            if batch:
                upsert_history_daily(batch)
                daily_rows.extend(batch)
            cur.close()
            logger.info("  %s: %s daily rows upserted", table, row_count)

        conn.commit()
        logger.info("Daily done: %s rows", len(daily_rows))
    finally:
        conn.close()

    weekly_result = _build_weekly_sql_bulk()
    logger.info("Weekly done: %s rows", weekly_result.get("weekly_rows", 0))

    return {
        "ok": True,
        "daily_rows": len(daily_rows),
        "weekly_rows": weekly_result.get("weekly_rows", 0),
        "unique_drivers": weekly_result.get("unique_drivers", 0),
        "min_date": str(from_date),
        "max_date": str(to_date),
        "tables_used": list(table_mappings.keys()),
        "warnings": all_warnings,
        "park_id": park_id[:8] + "****",
    }


def _build_weekly_sql_bulk() -> Dict[str, Any]:
    """
    Build weekly aggregates in a single SQL pass.
    Computes active_days, avg_orders_per_active_day, rolling metrics,
    and historical_band all server-side via window functions.
    """
    sql = """
    WITH daily_agg AS (
        SELECT driver_profile_id,
               date_trunc('week', date)::date AS week_start_date,
               (date_trunc('week', date)::date + INTERVAL '6 days')::date AS week_end_date,
               SUM(completed_orders) AS completed_orders_week,
               SUM(COALESCE(gross_revenue, 0)) AS gross_revenue_week,
               COUNT(*) AS active_days
        FROM growth.yango_lima_driver_history_daily
        WHERE completed_orders > 0
        GROUP BY driver_profile_id, date_trunc('week', date)::date
    ),
    with_avg AS (
        SELECT driver_profile_id, week_start_date, week_end_date,
               completed_orders_week, gross_revenue_week, active_days,
               CASE WHEN active_days > 0
                    THEN ROUND(completed_orders_week::numeric / active_days, 4)
               END AS avg_orders_per_active_day
        FROM daily_agg
    )
    INSERT INTO growth.yango_lima_driver_history_weekly (
        week_start_date, week_end_date, driver_profile_id,
        completed_orders_week, gross_revenue_week,
        active_days, avg_orders_per_active_day,
        avg_orders_4w, avg_orders_8w, avg_orders_12w,
        best_week_12w, historical_band,
        source, last_calculated_at
    )
    SELECT w.week_start_date, w.week_end_date, w.driver_profile_id,
           w.completed_orders_week,
           ROUND(w.gross_revenue_week::numeric, 4),
           w.active_days,
           ROUND(w.avg_orders_per_active_day::numeric, 4),
           ROUND(AVG(w.completed_orders_week) OVER (
               PARTITION BY w.driver_profile_id ORDER BY w.week_start_date
               ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
           )::numeric, 4) AS avg_orders_4w,
           ROUND(AVG(w.completed_orders_week) OVER (
               PARTITION BY w.driver_profile_id ORDER BY w.week_start_date
               ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
           )::numeric, 4) AS avg_orders_8w,
           ROUND(AVG(w.completed_orders_week) OVER (
               PARTITION BY w.driver_profile_id ORDER BY w.week_start_date
               ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING
           )::numeric, 4) AS avg_orders_12w,
           MAX(w.completed_orders_week) OVER (
               PARTITION BY w.driver_profile_id ORDER BY w.week_start_date
               ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING
           )::integer AS best_week_12w,
           CASE
               WHEN COALESCE(
                   MAX(w.completed_orders_week) OVER (
                       PARTITION BY w.driver_profile_id ORDER BY w.week_start_date
                       ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING
                   ), w.completed_orders_week
               ) >= 50 THEN 'HISTORICAL_50_PLUS'
               WHEN COALESCE(
                   MAX(w.completed_orders_week) OVER (
                       PARTITION BY w.driver_profile_id ORDER BY w.week_start_date
                       ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING
                   ), w.completed_orders_week
               ) >= 30 THEN 'HISTORICAL_30_49'
               WHEN COALESCE(
                   MAX(w.completed_orders_week) OVER (
                       PARTITION BY w.driver_profile_id ORDER BY w.week_start_date
                       ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING
                   ), w.completed_orders_week
               ) >= 10 THEN 'HISTORICAL_10_29'
               WHEN COALESCE(
                   MAX(w.completed_orders_week) OVER (
                       PARTITION BY w.driver_profile_id ORDER BY w.week_start_date
                       ROWS BETWEEN 11 PRECEDING AND 1 PRECEDING
                   ), w.completed_orders_week
               ) > 0 THEN 'HISTORICAL_00_09'
               ELSE 'NO_HISTORY'
           END AS historical_band,
           'trips_bootstrap', now()
    FROM with_avg w
    ON CONFLICT (week_start_date, driver_profile_id) DO UPDATE SET
        week_end_date = EXCLUDED.week_end_date,
        completed_orders_week = EXCLUDED.completed_orders_week,
        gross_revenue_week = EXCLUDED.gross_revenue_week,
        active_days = EXCLUDED.active_days,
        avg_orders_per_active_day = EXCLUDED.avg_orders_per_active_day,
        avg_orders_4w = EXCLUDED.avg_orders_4w,
        avg_orders_8w = EXCLUDED.avg_orders_8w,
        avg_orders_12w = EXCLUDED.avg_orders_12w,
        best_week_12w = EXCLUDED.best_week_12w,
        historical_band = EXCLUDED.historical_band,
        last_calculated_at = now()
    """

    params = _get_connection_params()
    params["options"] = "-c statement_timeout=600000"
    conn = psycopg2.connect(**params)
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute(sql)
        weekly_rows = cur.rowcount
        conn.commit()
        cur.close()

        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT driver_profile_id) FROM growth.yango_lima_driver_history_weekly")
        unique_drivers = cur.fetchone()[0]
        cur.close()

        logger.info("Weekly build SQL: %s rows, %s drivers", weekly_rows, unique_drivers)
        return {"weekly_rows": weekly_rows, "unique_drivers": unique_drivers}
    finally:
        conn.close()


def history_summary() -> Dict[str, Any]:
    return get_history_summary()


def history_sample(limit: int = 20) -> list:
    return repo_get_history_sample(limit)


# ── Fase 2D-RH — Historical Continuity Hardening ──

def inspect_trips_sources() -> Dict[str, Any]:
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()
    if not park_id:
        return {"ok": False, "error": "YANGO_LIMA_PARK_ID not configured"}

    result: Dict[str, Any] = {"park_id": park_id[:8] + "****", "tables": {}}
    params = _get_connection_params()
    params["options"] = "-c statement_timeout=30000"
    conn = psycopg2.connect(**params)
    try:
        for table in ["trips_2025", "trips_2026"]:
            mapping, warnings = _detect_columns_from_conn(conn, table)
            err = _validate_required(mapping, table)
            if err:
                result["tables"][table] = {"error": err}
                continue

            cur = conn.cursor(cursor_factory=RealDictCursor)
            driver_col = mapping["driver_id"]
            date_col = mapping["trip_date"]
            park_col = mapping["park_id"]
            status_col = mapping["status"]

            cur.execute(f"SELECT COUNT(*) AS total FROM public.{table} WHERE {park_col} = %s AND LOWER({status_col}) = 'completado'", (park_id,))
            total_trips = cur.fetchone()["total"]

            cur.execute(f"SELECT COUNT(DISTINCT {driver_col}) FROM public.{table} WHERE {park_col} = %s AND LOWER({status_col}) = 'completado'", (park_id,))
            unique_drivers = cur.fetchone()["count"]

            cur.execute(f"SELECT MIN({date_col}), MAX({date_col}) FROM public.{table} WHERE {park_col} = %s AND LOWER({status_col}) = 'completado'", (park_id,))
            r = cur.fetchone()

            result["tables"][table] = {
                "detected_columns": mapping,
                "total_completed_trips": total_trips,
                "unique_drivers": unique_drivers,
                "min_date": str(r.get("min", r.get("min"))),
                "max_date": str(r.get("max", r.get("max"))),
                "warnings": warnings,
            }
            cur.close()

        # Current history state
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT MIN(date), MAX(date), COUNT(*), COUNT(DISTINCT driver_profile_id) FROM growth.yango_lima_driver_history_daily")
        r = cur.fetchone()
        result["existing_history"] = {
            "daily_min": str(r["min"]),
            "daily_max": str(r["max"]),
            "daily_rows": r["count"],
            "unique_drivers": r["count"],
        }
        cur.close()

        result["ok"] = True
        return result
    finally:
        conn.close()


def rebuild_history_until_cutover(cutover_date: str, from_date: Optional[str] = None, dry_run: bool = True) -> Dict[str, Any]:
    cutover = date.fromisoformat(cutover_date)
    start = date.fromisoformat(from_date) if from_date else date(2025, 1, 1)
    end = cutover - timedelta(days=1)

    if dry_run:
        return _estimate_backfill(start, end)

    return bootstrap_history(str(start), str(end))


def _estimate_backfill(from_date: date, to_date: date) -> Dict[str, Any]:
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()
    if not park_id:
        return {"ok": False, "error": "YANGO_LIMA_PARK_ID not configured", "dry_run": True}

    result = {"dry_run": True, "from_date": str(from_date), "to_date": str(to_date), "park_id": park_id[:8] + "****"}
    total_trips = 0
    total_drivers_set: set = set()

    params = _get_connection_params()
    params["options"] = "-c statement_timeout=30000"
    conn = psycopg2.connect(**params)
    try:
        for table in ["trips_2025", "trips_2026"]:
            mapping, _ = _detect_columns_from_conn(conn, table)
            err = _validate_required(mapping, table)
            if err:
                continue
            cur = conn.cursor(cursor_factory=RealDictCursor)
            driver_col, date_col, park_col, status_col = (
                mapping["driver_id"], mapping["trip_date"], mapping["park_id"], mapping["status"]
            )
            cur.execute(f"""
                SELECT COUNT(*) AS trips, COUNT(DISTINCT {driver_col}) AS drivers
                FROM public.{table}
                WHERE {park_col} = %s
                  AND LOWER({status_col}) = 'completado'
                  AND {date_col} >= %s::timestamp
                  AND {date_col} <= %s::timestamp
            """, (park_id, f"{from_date} 00:00:00", f"{to_date} 23:59:59"))
            r = cur.fetchone()
            result[table] = {"estimated_trips": r["trips"], "estimated_drivers": r["drivers"]}
            total_trips += r["trips"] or 0
            cur.close()

        result["estimated_total_trips"] = total_trips
        result["estimated_daily_rows"] = "depends on date granularity"
        result["note"] = "Run with dry_run=false to execute actual backfill"
        result["ok"] = True
        return result
    finally:
        conn.close()


def refresh_weekly_history() -> Dict[str, Any]:
    """
    FH-1: Governed weekly history refresh for autonomous tick.
    Checks if weekly table is behind daily table and runs _build_weekly_sql_bulk() if needed.
    Idempotent UPSERT — safe to call multiple times.
    """
    params = _get_connection_params()
    params["options"] = "-c statement_timeout=30000"
    conn = psycopg2.connect(**params)
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(week_start_date) FROM growth.yango_lima_driver_history_weekly")
        max_week = cur.fetchone()[0]
        cur.execute("SELECT MAX(date) FROM growth.yango_lima_driver_history_daily")
        max_daily = cur.fetchone()[0]
        cur.close()
    finally:
        conn.close()

    if not max_daily:
        return {"refreshed": False, "status": "NOOP", "reason": "No daily data available"}

    if max_week:
        latest_complete_monday = date.today() - timedelta(days=date.today().weekday())
        if isinstance(max_week, datetime):
            max_week_d = max_week.date()
        elif isinstance(max_week, str):
            max_week_d = date.fromisoformat(max_week[:10])
        else:
            max_week_d = max_week

        if max_week_d >= latest_complete_monday - timedelta(days=7):
            return {"refreshed": False, "status": "NOOP", "reason": f"Weekly up to date (latest: {max_week_d})"}

    result = _build_weekly_sql_bulk()
    return {"refreshed": True, "status": "REFRESHED", **result}


def continuity_check() -> Dict[str, Any]:
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()
    cutover = settings.LIMA_GROWTH_API_CUTOVER_DATE

    result: Dict[str, Any] = {"cutover_date": cutover}

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # History stats
        cur.execute("SELECT MIN(date) AS mi, MAX(date) AS ma, COUNT(DISTINCT driver_profile_id) AS u FROM growth.yango_lima_driver_history_daily WHERE date < %s", (cutover,))
        r = cur.fetchone()
        result["history"] = {"min_date": str(r["mi"]), "max_date": str(r["ma"]), "unique_drivers": r["u"]}

        # API stats (360_daily)
        cur.execute("SELECT MIN(date) AS mi, MAX(date) AS ma, COUNT(DISTINCT driver_profile_id) AS u FROM growth.yango_lima_driver_360_daily WHERE date >= %s", (cutover,))
        r = cur.fetchone()
        result["api"] = {"min_date": str(r["mi"]), "max_date": str(r["ma"]), "unique_drivers": r["u"]}

        # Overlap
        cur.execute("""
            SELECT COUNT(DISTINCT h.driver_profile_id)
            FROM growth.yango_lima_driver_history_daily h
            INNER JOIN growth.yango_lima_driver_360_daily a ON h.driver_profile_id = a.driver_profile_id
        """)
        result["overlapping_drivers"] = cur.fetchone()["count"]

        cur.execute("""
            SELECT COUNT(DISTINCT a.driver_profile_id)
            FROM growth.yango_lima_driver_360_daily a
            WHERE NOT EXISTS (
                SELECT 1 FROM growth.yango_lima_driver_history_daily h WHERE h.driver_profile_id = a.driver_profile_id
            )
        """)
        result["drivers_api_without_history"] = cur.fetchone()["count"] or 0

        cur.execute("""
            SELECT COUNT(DISTINCT h.driver_profile_id)
            FROM growth.yango_lima_driver_history_daily h
            WHERE NOT EXISTS (
                SELECT 1 FROM growth.yango_lima_driver_360_daily a WHERE a.driver_profile_id = h.driver_profile_id AND a.date >= %s
            )
        """, (cutover,))
        result["drivers_history_without_api"] = cur.fetchone()["count"] or 0

        result["warnings"] = []
        if result["drivers_api_without_history"] > 0:
            result["warnings"].append(f"{result['drivers_api_without_history']} API drivers without historical record")
        if result["drivers_history_without_api"] > 500:
            result["warnings"].append(f"{result['drivers_history_without_api']} historical drivers not seen in API post-cutover")

        return result
