"""
Driver Raw Freshness Service — FASE D2
Control Foundation: Identity Foundation

Responsibility:
- Dynamically inspect upstream RAW tables/views/MVs that feed Drivers.
- Calculate freshness per source without assuming columns.
- Return structured freshness map with blocking_gaps and remediation.
- Never crash if a table/view does not exist.
- Never crash if a column is missing.
- Use lightweight queries (COUNT(*), LIMIT metadata, NOT full scans).

Sources inspected:
  identity → public.drivers, public.drivers_data, public.module_ct_cabinet_drivers
  activity → public.trips_2025, public.trips_2026, ops.driver_daily_activity_fact
  geo     → dim.dim_park, ops.v_dim_park_resolved
  resolved→ ops.v_dim_driver_resolved
  lifecycle→ ops.mv_driver_lifecycle_base
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 15000

SOURCES = [
    # identity
    {"source_name": "public.drivers", "source_type": "raw", "role": "identity",
     "is_blocking_for_d2": True,
     "remediation": "Verify table exists with driver_id, phone, name, park_id columns."},
    {"source_name": "public.drivers_data", "source_type": "raw", "role": "contactability",
     "is_blocking_for_d2": True,
     "remediation": "This table has driver_phone. Integrate into ops.v_dim_driver_resolved or create serving.driver_identity_fact."},
    {"source_name": "public.module_ct_cabinet_drivers", "source_type": "raw", "role": "identity",
     "is_blocking_for_d2": False,
     "remediation": "Legacy Diego cabinet table. Has driver_phone, driver_nombre. Optional enrichment source."},
    # activity
    {"source_name": "public.trips_2025", "source_type": "raw", "role": "activity",
     "is_blocking_for_d2": False,
     "remediation": "Historical trips. Max operational date should be <= 2025-12-31."},
    {"source_name": "public.trips_2026", "source_type": "raw", "role": "activity",
     "is_blocking_for_d2": False,
     "remediation": "Current year trips. Must have recent data (within last 7 days)."},
    {"source_name": "ops.driver_daily_activity_fact", "source_type": "serving", "role": "activity",
     "is_blocking_for_d2": True,
     "remediation": "Core serving fact for driver activity. Must be refreshed daily. Check last_refreshed_at timestamp."},
    # geo
    {"source_name": "dim.dim_park", "source_type": "raw", "role": "geo",
     "is_blocking_for_d2": False,
     "remediation": "Park dimension. Verify city/country coverage."},
    {"source_name": "ops.v_dim_park_resolved", "source_type": "mv", "role": "geo",
     "is_blocking_for_d2": False,
     "remediation": "Resolved park view. Derived from dim.dim_park."},
    # resolved identity
    {"source_name": "ops.v_dim_driver_resolved", "source_type": "mv", "role": "identity",
     "is_blocking_for_d2": True,
     "remediation": "Resolved driver name from trips_unified. Missing phone. Must be enriched with public.drivers_data."},
    # lifecycle
    {"source_name": "ops.mv_driver_lifecycle_base", "source_type": "mv", "role": "lifecycle_candidate",
     "is_blocking_for_d2": False,
     "remediation": "Base lifecycle MV. Check freshness via last_completed_ts or driver_activity."},
]


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET LOCAL statement_timeout = %s", (str(int(timeout_ms)),))
    return c


def _safe_query(cur, sql: str, params: dict = None, default=None):
    """Execute query; return result or default on any error."""
    try:
        cur.execute(sql, params or {})
        return cur.fetchone() or cur.fetchall()
    except Exception as e:
        logger.debug("driver_raw_freshness: query failed for %s: %s", sql[:80], e)
        return default


def _table_exists(cur, schema_table: str) -> bool:
    parts = schema_table.split(".", 1)
    schema = parts[0] if len(parts) > 1 else "public"
    table = parts[1] if len(parts) > 1 else parts[0]
    row = _safe_query(
        cur,
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %(schema)s AND table_name = %(table)s
        ) AS exists
        """,
        {"schema": schema, "table": table},
    )
    return bool(row["exists"]) if row else False


def _column_exists(cur, schema_table: str, column: str) -> bool:
    parts = schema_table.split(".", 1)
    schema = parts[0] if len(parts) > 1 else "public"
    table = parts[1] if len(parts) > 1 else parts[0]
    row = _safe_query(
        cur,
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = %(schema)s AND table_name = %(table)s AND column_name = %(col)s
        ) AS exists
        """,
        {"schema": schema, "table": table, "col": column},
    )
    return bool(row["exists"]) if row else False


def _get_record_count(cur, schema_table: str) -> Optional[int]:
    """COUNT(*) with LIMIT-safe approach."""
    if not _table_exists(cur, schema_table):
        return None
    row = _safe_query(cur, f'SELECT COUNT(*) AS cnt FROM (SELECT 1 FROM {schema_table} LIMIT 5000) t')
    return int(row["cnt"]) if row else None


def _get_max_date(cur, schema_table: str, column: str) -> Optional[str]:
    """Get max date value, return ISO string or None."""
    if not _table_exists(cur, schema_table):
        return None
    if not _column_exists(cur, schema_table, column):
        return None
    try:
        row = _safe_query(cur, f'SELECT MAX({column}) AS max_val FROM {schema_table}')
        if row and row.get("max_val"):
            val = row["max_val"]
            if isinstance(val, datetime):
                return val.isoformat()
            return str(val)
    except Exception:
        pass
    return None


def _get_max_loaded_at(cur, schema_table: str) -> Optional[str]:
    """Try common loaded/refreshed/updated columns."""
    for col in ("last_refreshed_at", "refreshed_at", "loaded_at", "updated_at", "last_updated"):
        result = _get_max_date(cur, schema_table, col)
        if result:
            return result
    return None


def _has_column_candidates(cur, schema_table: str, candidates: list[str]) -> dict[str, bool]:
    """Check which candidate columns exist."""
    result = {}
    for col in candidates:
        result[col] = _column_exists(cur, schema_table, col)
    return result


def inspect_source(cur, source_def: dict) -> dict:
    """Inspect one source and return freshness metadata."""
    name = source_def["source_name"]
    exists = _table_exists(cur, name)

    result = {
        **source_def,
        "exists": exists,
        "record_count": None,
        "max_operational_date": None,
        "max_loaded_at": None,
        "freshness_status": "unknown",
        "freshness_reason": "",
        "available_columns": {},
    }

    if not exists:
        result["freshness_status"] = "blocked"
        result["freshness_reason"] = f"Table/view {name} does not exist."
        return result

    # record count
    result["record_count"] = _get_record_count(cur, name)

    # column discovery (identity-related)
    id_cols = _has_column_candidates(cur, name, [
        "driver_id", "conductor_id", "id",
        "driver_name", "conductor_nombre", "full_name", "driver_nombre",
        "phone", "driver_phone", "telefono",
        "email", "mail",
        "park_id", "park_name",
        "city", "ciudad", "country", "pais",
        "created_at", "registered_at", "hire_date",
        "first_trip_at", "first_seen_at", "activation_ts",
        "last_trip_at", "last_completed_ts", "last_activity_at", "last_active_date",
        "last_refreshed_at", "refreshed_at", "loaded_at", "updated_at",
    ])
    result["available_columns"] = {k: v for k, v in id_cols.items() if v}

    # operational date (for activity sources)
    if source_def["role"] == "activity":
        for date_col in ("fecha_finalizacion", "fecha_inicio_viaje", "trip_date", "activity_date", "completion_ts"):
            max_val = _get_max_date(cur, name, date_col)
            if max_val:
                result["max_operational_date"] = max_val
                break
    else:
        # for identity sources, try created_at / updated_at
        for ts_col in ("created_at", "updated_at", "hire_date", "uploaded_at"):
            max_val = _get_max_date(cur, name, ts_col)
            if max_val:
                if not result["max_operational_date"]:
                    result["max_operational_date"] = max_val

    # loaded_at / refreshed_at
    result["max_loaded_at"] = _get_max_loaded_at(cur, name)

    # freshness status determination
    now = datetime.now(timezone.utc)
    if result["max_operational_date"]:
        try:
            op_date = result["max_operational_date"]
            if isinstance(op_date, str):
                op_dt = datetime.fromisoformat(op_date.replace("Z", "+00:00"))
            else:
                op_dt = op_date
            if op_dt.tzinfo is None:
                op_dt = op_dt.replace(tzinfo=timezone.utc)
            delta = (now - op_dt).days
            if delta <= 2:
                result["freshness_status"] = "fresh"
                result["freshness_reason"] = f"Max operational date within {delta} day(s)."
            elif delta <= 14:
                result["freshness_status"] = "stale"
                result["freshness_reason"] = f"Max operational date is {delta} days ago."
            else:
                result["freshness_status"] = "stale"
                result["freshness_reason"] = f"Max operational date is {delta} days ago (stale)."
        except Exception:
            result["freshness_status"] = "unknown"
            result["freshness_reason"] = "Could not parse operational date."
    elif result["max_loaded_at"]:
        result["freshness_status"] = "fresh"
        result["freshness_reason"] = "No operational date column; using loaded_at."

    if result["freshness_status"] == "unknown" and exists:
        result["freshness_reason"] = result["freshness_reason"] or "No date/timestamp column found to determine freshness."

    return result


def get_raw_freshness_map() -> dict[str, Any]:
    """
    Inspect all driver RAW sources and return structured freshness map.
    Per-source timeout: 5s. Total max: ~60s.
    """
    import signal
    sources_result = []
    blocking_gaps = []
    warnings_list = []

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute("SET LOCAL statement_timeout = '5000'")  # 5s per query

            for source_def in SOURCES:
                try:
                    info = inspect_source(cur, source_def)
                    sources_result.append(info)

                    if info.get("is_blocking_for_d2") and info.get("freshness_status") in ("stale", "blocked", "unknown"):
                        blocking_gaps.append({
                            "source_name": info["source_name"],
                            "role": info["role"],
                            "freshness_status": info["freshness_status"],
                            "remediation": info.get("remediation", ""),
                        })

                    if info.get("freshness_status") == "stale":
                        warnings_list.append({
                            "source_name": info["source_name"],
                            "role": info["role"],
                            "freshness_status": info["freshness_status"],
                            "freshness_reason": info.get("freshness_reason", ""),
                        })
                except Exception as se:
                    sources_result.append({
                        "source_name": source_def.get("source_name", "unknown"),
                        "source_type": source_def.get("source_type", "unknown"),
                        "exists": False,
                        "role": source_def.get("role", "unknown"),
                        "freshness_status": "blocked",
                        "freshness_reason": f"Inspection timed out or failed: {str(se)[:100]}",
                        "is_blocking_for_d2": source_def.get("is_blocking_for_d2", False),
                        "remediation": "Source inspection failed. Check DB connectivity and table existence.",
                    })
    except Exception as e:
        logger.error("driver_raw_freshness_service: failed to inspect sources: %s", e)
        return {
            "status": "blocked",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sources": [],
            "blocking_gaps": [{"source_name": "database_connection", "freshness_status": "blocked",
                               "remediation": str(e)}],
            "warnings": [],
        }

    # derive overall status
    if blocking_gaps:
        overall = "blocked"
    elif warnings_list:
        overall = "warning"
    else:
        overall = "ok"

    return {
        "status": overall,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources_result,
        "blocking_gaps": blocking_gaps,
        "warnings": warnings_list,
    }
