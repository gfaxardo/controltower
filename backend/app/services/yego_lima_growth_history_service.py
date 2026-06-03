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
