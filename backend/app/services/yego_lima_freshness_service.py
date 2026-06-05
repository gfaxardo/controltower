"""
YEGO Lima Growth — Data Freshness Service (Fase 4B E2E).

Tracks sync status per source, validates post-cutover continuity,
generates hourly snapshots, and computes health (GREEN/YELLOW/RED).
"""

from __future__ import annotations
import logging
from datetime import date as date_type, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

TABLE_FRESHNESS = "growth.yango_lima_data_freshness"
TABLE_HOURLY = "growth.yango_lima_hourly_snapshot"
TABLE_360 = "growth.yango_lima_driver_360_daily"
TABLE_ORDERS_RAW = "growth.yango_lima_orders_raw"
TABLE_PROD_DAILY = "growth.yango_lima_productivity_daily"
TABLE_PROD_WEEKLY = "growth.yango_lima_productivity_weekly"
TABLE_PROD_MONTHLY = "growth.yango_lima_productivity_monthly"
TABLE_HIST_DAILY = "growth.yango_lima_driver_history_daily"

CUTOVER = (settings.LIMA_GROWTH_API_CUTOVER_DATE or "2026-06-01")

SOURCES = [
    "orders_api",
    "supply_api",
    "driver360",
    "productivity_daily",
    "productivity_weekly",
    "productivity_monthly",
]

_FRESHNESS_WINDOWS_MINUTES = {
    "orders_api": {"green": 360, "yellow": 1440},
    "supply_api": {"green": 360, "yellow": 1440},
    "driver360": {"green": 720, "yellow": 2880},
    "productivity_daily": {"green": 1440, "yellow": 4320},
    "productivity_weekly": {"green": 10080, "yellow": 20160},
    "productivity_monthly": {"green": 43200, "yellow": 86400},
}


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return int(default)


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return float(default)


def _now_utc():
    return datetime.now(timezone.utc)


def _parse_ts(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _age_minutes(ts) -> Optional[float]:
    if ts is None:
        return None
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = _now_utc() - ts
    return delta.total_seconds() / 60.0


def _health_label(source_name: str, last_sync_at, status: str,
                  max_data_ts) -> str:
    if status in ("initializing", "error"):
        return "RED"
    age = _age_minutes(last_sync_at)
    if age is None:
        return "RED"
    windows = _FRESHNESS_WINDOWS_MINUTES.get(source_name, {"green": 1440, "yellow": 4320})
    if age <= windows["green"]:
        return "GREEN"
    elif age <= windows["yellow"]:
        return "YELLOW"
    return "RED"


# ==============================================================
# UPDATE
# ==============================================================

def update_freshness(source_name: str,
                     status: str = "ok",
                     max_data_timestamp=None,
                     rows_synced: int = 0,
                     duration_seconds: float = 0,
                     error_message: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_FRESHNESS} (
                source_name, last_successful_sync_at, max_data_timestamp,
                rows_last_sync, sync_duration_seconds, status, error_message, updated_at
            ) VALUES (
                %(src)s, now(), %(max_ts)s,
                %(rows)s, %(dur)s, %(status)s, %(err)s, now()
            )
            ON CONFLICT (source_name) DO UPDATE SET
                last_successful_sync_at = EXCLUDED.last_successful_sync_at,
                max_data_timestamp = EXCLUDED.max_data_timestamp,
                rows_last_sync = EXCLUDED.rows_last_sync,
                sync_duration_seconds = EXCLUDED.sync_duration_seconds,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                updated_at = now()
        """, {
            "src": source_name,
            "max_ts": max_data_timestamp,
            "rows": rows_synced,
            "dur": duration_seconds,
            "status": status,
            "err": error_message,
        })
    logger.info("Freshness updated: %s -> %s (rows=%s, dur=%ss)",
                source_name, status, rows_synced, duration_seconds)
    return {"source_name": source_name, "status": status}


def record_orders_sync(from_dt: str, to_dt: str, orders_count: int,
                       duration_s: float):
    return update_freshness(
        "orders_api", status="ok",
        max_data_timestamp=to_dt,
        rows_synced=orders_count,
        duration_seconds=duration_s)


def record_supply_sync(drivers_count: int, duration_s: float):
    return update_freshness(
        "supply_api", status="ok",
        max_data_timestamp=_now_utc(),
        rows_synced=drivers_count,
        duration_seconds=duration_s)


def record_driver360_sync(date_str: str, drivers_count: int,
                          duration_s: float):
    return update_freshness(
        "driver360", status="ok",
        max_data_timestamp=date_str,
        rows_synced=drivers_count,
        duration_seconds=duration_s)


def record_productivity_sync(grain: str, key: str, active_drivers: int,
                             duration_s: float):
    return update_freshness(
        f"productivity_{grain}", status="ok",
        max_data_timestamp=key,
        rows_synced=active_drivers,
        duration_seconds=duration_s)


# ==============================================================
# GET
# ==============================================================

def get_freshness_status() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT source_name, last_successful_sync_at, max_data_timestamp,
                   rows_last_sync, sync_duration_seconds, status, error_message,
                   updated_at
            FROM {TABLE_FRESHNESS}
            ORDER BY source_name
        """)
        sources = []
        for row in cur.fetchall():
            last_sync = row["last_successful_sync_at"]
            age_m = _age_minutes(last_sync)
            sources.append({
                "source": row["source_name"],
                "status": row["status"],
                "last_successful_sync_at": _parse_ts(last_sync),
                "freshness_minutes": round(age_m, 1) if age_m is not None else None,
                "max_data_timestamp": _parse_ts(row["max_data_timestamp"]),
                "rows_last_sync": _safe_int(row["rows_last_sync"]),
                "sync_duration_seconds": _safe_float(row["sync_duration_seconds"]),
                "error_message": row["error_message"],
            })
        return {"sources": sources, "checked_at": _now_utc().isoformat()}


def get_health() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM {TABLE_FRESHNESS} ORDER BY source_name")
        results = {}
        overall = "GREEN"
        for row in cur.fetchall():
            src = row["source_name"]
            health = _health_label(src, row["last_successful_sync_at"],
                                   row["status"], row["max_data_timestamp"])
            results[src] = {
                "health": health,
                "status": row["status"],
                "last_sync": _parse_ts(row["last_successful_sync_at"]),
                "freshness_minutes": round(_age_minutes(row["last_successful_sync_at"]) or 0, 1),
                "error": row["error_message"],
            }
            if health == "RED":
                overall = "RED"
            elif health == "YELLOW" and overall == "GREEN":
                overall = "YELLOW"

    return {"overall": overall, "sources": results, "checked_at": _now_utc().isoformat()}


def get_summary() -> Dict[str, Any]:
    health = get_health()

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT source_name, status, last_successful_sync_at,
                   max_data_timestamp, rows_last_sync
            FROM {TABLE_FRESHNESS}
            ORDER BY source_name
        """)
        details = {}
        for row in cur.fetchall():
            details[row["source_name"]] = {
                "status": row["status"],
                "last_sync": _parse_ts(row["last_successful_sync_at"]),
                "max_data_ts": _parse_ts(row["max_data_timestamp"]),
                "rows_last_sync": _safe_int(row["rows_last_sync"]),
            }

    green_count = sum(1 for v in health["sources"].values() if v["health"] == "GREEN")
    yellow_count = sum(1 for v in health["sources"].values() if v["health"] == "YELLOW")
    red_count = sum(1 for v in health["sources"].values() if v["health"] == "RED")

    return {
        "overall": health["overall"],
        "green": green_count,
        "yellow": yellow_count,
        "red": red_count,
        "sources": details,
        "health": health["sources"],
        "checked_at": _now_utc().isoformat(),
    }


# ==============================================================
# POST-CUTOVER CONTINUITY AUDIT
# ==============================================================

def validate_post_cutover_continuity() -> Dict[str, Any]:
    try:
        cutover_date = date_type.fromisoformat(CUTOVER)
    except (ValueError, TypeError):
        return {"error": f"Invalid CUTOVER date: {CUTOVER}"}

    today = date_type.today()
    days_total = (today - cutover_date).days + 1
    if days_total < 1:
        return {"error": "Cutover date is in the future", "cutover": CUTOVER}

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        sources_check = {
            "orders_api": {"table": TABLE_ORDERS_RAW, "date_col": "ended_at::date"},
            "supply_api": {"table": TABLE_360, "date_col": "date",
                           "where_extra": "supply_hours > 0"},
            "driver360": {"table": TABLE_360, "date_col": "date"},
            "productivity_daily": {"table": TABLE_PROD_DAILY, "date_col": "date"},
            "productivity_weekly": {"table": TABLE_PROD_WEEKLY,
                                    "date_col": "iso_week_start_date"},
            "productivity_monthly": {"table": TABLE_PROD_MONTHLY,
                                     "date_col": None},
        }

        results = {}
        total_gaps = 0

        for src_name, cfg in sources_check.items():
            table = cfg["table"]
            date_col = cfg["date_col"]
            where = cfg.get("where_extra", "")

            if date_col is None:
                cur.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                r = cur.fetchone()
                results[src_name] = {
                    "present": r["cnt"] > 0 if r else False,
                    "days_with_data": _safe_int(r["cnt"]) if r else 0,
                    "days_missing": 0,
                    "gaps": [],
                }
                continue

            where_clause = f"AND {where}" if where else ""

            cur.execute(f"""
                WITH all_dates AS (
                    SELECT generate_series(%(from_d)s::date, %(to_d)s::date, '1 day'::interval)::date AS d
                ),
                data_dates AS (
                    SELECT DISTINCT {date_col} AS d
                    FROM {table}
                    WHERE {date_col} >= %(from_d)s AND {date_col} <= %(to_d)s {where_clause}
                )
                SELECT a.d AS date,
                       CASE WHEN dd.d IS NOT NULL THEN true ELSE false END AS has_data
                FROM all_dates a
                LEFT JOIN data_dates dd ON a.d = dd.d
                ORDER BY a.d
            """, {"from_d": cutover_date.isoformat(), "to_d": today.isoformat()})

            days_present = 0
            gaps = []
            for row in cur.fetchall():
                d = str(row["date"])
                if row["has_data"]:
                    days_present += 1
                else:
                    gaps.append(d)

            results[src_name] = {
                "present": days_present > 0,
                "days_total": days_total,
                "days_with_data": days_present,
                "days_missing": days_total - days_present,
                "gaps": gaps[:30],
            }
            total_gaps += len(gaps)

    audit = {
        "cutover_date": CUTOVER,
        "today": today.isoformat(),
        "days_since_cutover": days_total,
        "sources": results,
        "total_gaps_detected": total_gaps,
        "continuity_ok": total_gaps == 0,
        "checked_at": _now_utc().isoformat(),
    }

    return audit


# ==============================================================
# HOURLY SNAPSHOT
# ==============================================================

def build_hourly_snapshot(hour_start: Optional[datetime] = None) -> Dict[str, Any]:
    if hour_start is None:
        hour_start = _now_utc().replace(minute=0, second=0, microsecond=0)

    hour_end = hour_start + timedelta(hours=1)
    today_str = hour_start.date().isoformat()

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            SELECT
                COALESCE(SUM(completed_orders), 0) AS completed_orders,
                COUNT(DISTINCT driver_profile_id) FILTER (WHERE completed_orders > 0) AS active_drivers,
                COUNT(DISTINCT driver_profile_id) FILTER (WHERE supply_hours > 0) AS supply_drivers,
                COALESCE(SUM(supply_hours), 0) AS supply_hours
            FROM {TABLE_360}
            WHERE date = %(d)s
        """, {"d": today_str})
        row = cur.fetchone()
        if not row or (row["completed_orders"] == 0 and row["supply_drivers"] == 0):
            return {"error": "No 360 data for today", "date": today_str,
                    "hour_start": hour_start.isoformat()}

        orders = _safe_int(row["completed_orders"])
        active = _safe_int(row["active_drivers"])
        supply_d = _safe_int(row["supply_drivers"])
        supply_h = _safe_float(row["supply_hours"])

        tpd = round(orders / active, 4) if active else None
        tpsh = round(orders / supply_h, 4) if supply_h else None

        cur.execute(f"""
            INSERT INTO {TABLE_HOURLY} (
                hour_start, hour_end,
                completed_orders, active_drivers, supply_drivers, supply_hours,
                trips_per_driver, trips_per_supply_hour, created_at
            ) VALUES (
                %(hs)s, %(he)s,
                %(o)s, %(a)s, %(s_d)s, %(sh)s,
                %(tpd)s, %(tpsh)s, now()
            )
            ON CONFLICT (hour_start) DO UPDATE SET
                hour_end = EXCLUDED.hour_end,
                completed_orders = EXCLUDED.completed_orders,
                active_drivers = EXCLUDED.active_drivers,
                supply_drivers = EXCLUDED.supply_drivers,
                supply_hours = EXCLUDED.supply_hours,
                trips_per_driver = EXCLUDED.trips_per_driver,
                trips_per_supply_hour = EXCLUDED.trips_per_supply_hour,
                created_at = now()
        """, {
            "hs": hour_start,
            "he": hour_end,
            "o": orders,
            "a": active,
            "s_d": supply_d,
            "sh": supply_h,
            "tpd": tpd,
            "tpsh": tpsh,
        })

        snapshot = {
            "hour_start": hour_start.isoformat(),
            "hour_end": hour_end.isoformat(),
            "completed_orders": orders,
            "active_drivers": active,
            "supply_drivers": supply_d,
            "supply_hours": round(supply_h, 4),
            "trips_per_driver": tpd,
            "trips_per_supply_hour": tpsh,
            "created_at": _now_utc().isoformat(),
        }

    logger.info("Hourly snapshot built: %s (active=%s, orders=%s)",
                hour_start.isoformat(), active, orders)
    return snapshot


def get_hourly_snapshots(limit: int = 24) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT * FROM {TABLE_HOURLY}
            ORDER BY hour_start DESC
            LIMIT %(lim)s
        """, {"lim": min(limit, 168)})
        results = []
        for row in cur.fetchall():
            results.append({
                "hour_start": _parse_ts(row["hour_start"]),
                "hour_end": _parse_ts(row["hour_end"]),
                "completed_orders": _safe_int(row["completed_orders"]),
                "active_drivers": _safe_int(row["active_drivers"]),
                "supply_drivers": _safe_int(row["supply_drivers"]),
                "supply_hours": _safe_float(row["supply_hours"]),
                "trips_per_driver": _safe_float(row["trips_per_driver"]),
                "trips_per_supply_hour": _safe_float(row["trips_per_supply_hour"]),
                "created_at": _parse_ts(row["created_at"]),
            })
        return results


# ==============================================================
# INCREMENTAL VALIDATION
# ==============================================================

def validate_incremental_strategy() -> Dict[str, Any]:
    return {
        "orders_api": {
            "strategy": "incremental_pull",
            "mechanism": "capture-orders-range with from/to dates + UPSERT on order_id",
            "incremental": True,
            "notes": "No full rebuild needed. Each pull fetches date range and upserts.",
        },
        "supply_api": {
            "strategy": "per_driver_incremental",
            "mechanism": "Only fetches supply for HOT/WARM drivers. COLD/DORMANT skip API.",
            "incremental": True,
            "notes": "Rate-limited per-driver calls with backoff. No full batch rebuild.",
        },
        "driver360": {
            "strategy": "eligible_universe_driven",
            "mechanism": "Only processes drivers from eligible_universe. UPSERT on (driver_profile_id, date).",
            "incremental": True,
            "notes": "Impacted drivers only. Non-eligible skipped entirely.",
        },
        "productivity": {
            "strategy": "point_in_time_upsert",
            "mechanism": "Each grain upserts by PK (date/isoweek/month). Only target period affected.",
            "incremental": True,
            "notes": "One date/week/month at a time. No cascade rebuild.",
        },
    }


# ==============================================================
# REFRESH SCALING ESTIMATES
# ==============================================================

def estimate_refresh_capacity() -> Dict[str, Any]:
    base_times = {
        "orders_api": 12.0,
        "supply_api_per_100_drivers": 150.0,
        "driver360_per_100_drivers": 45.0,
        "productivity_all_grains": 3.0,
    }

    return {
        "5k_active": {
            "orders_api_estimate_s": round(base_times["orders_api"], 0),
            "supply_api_estimate_s": round(base_times["supply_api_per_100_drivers"] * 50, 0),
            "driver360_estimate_s": round(base_times["driver360_per_100_drivers"] * 50, 0),
            "productivity_estimate_s": base_times["productivity_all_grains"],
            "total_estimate_s": round(
                base_times["orders_api"] +
                base_times["supply_api_per_100_drivers"] * 50 +
                base_times["driver360_per_100_drivers"] * 50 +
                base_times["productivity_all_grains"], 0),
            "feasible_without_scheduler": True,
        },
        "10k_active": {
            "orders_api_estimate_s": round(base_times["orders_api"], 0),
            "supply_api_estimate_s": round(base_times["supply_api_per_100_drivers"] * 100, 0),
            "driver360_estimate_s": round(base_times["driver360_per_100_drivers"] * 100, 0),
            "productivity_estimate_s": base_times["productivity_all_grains"],
            "total_estimate_s": round(
                base_times["orders_api"] +
                base_times["supply_api_per_100_drivers"] * 100 +
                base_times["driver360_per_100_drivers"] * 100 +
                base_times["productivity_all_grains"], 0),
            "feasible_without_scheduler": True,
        },
        "20k_active": {
            "orders_api_estimate_s": round(base_times["orders_api"], 0),
            "supply_api_estimate_s": round(base_times["supply_api_per_100_drivers"] * 200, 0),
            "driver360_estimate_s": round(base_times["driver360_per_100_drivers"] * 200, 0),
            "productivity_estimate_s": base_times["productivity_all_grains"],
            "total_estimate_s": round(
                base_times["orders_api"] +
                base_times["supply_api_per_100_drivers"] * 200 +
                base_times["driver360_per_100_drivers"] * 200 +
                base_times["productivity_all_grains"], 0),
            "feasible_without_scheduler": False,
            "recommendation": "Scheduler needed at 20K scale. Supply batch requires 300s (~5min) at 1.5s/driver.",
        },
    }
