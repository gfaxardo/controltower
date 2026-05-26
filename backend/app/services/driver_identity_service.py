"""
Driver Identity Service — FASE D2
Control Foundation: Identity Foundation

Replaces stubs in driver_identity_resolver_service.py for phone/contact fields.
Consumes RAW tables directly (public.drivers, public.drivers_data, public.module_ct_cabinet_drivers)
and resolved views (ops.v_dim_driver_resolved, ops.v_dim_park_resolved).

Principles:
- Deterministic identity resolution
- Phone from real sources, not hardcoded None
- If phone missing, return None + missing_fields + remediation
- Never crash if source table doesn't exist
- Lightweight queries (< 15s timeout)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 15000


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET LOCAL statement_timeout = %s", (str(int(timeout_ms)),))
    return c


def _safe_query(cur, sql: str, params: dict = None, default=None):
    try:
        cur.execute(sql, params or {})
        return cur.fetchone() or cur.fetchall()
    except Exception as e:
        logger.debug("driver_identity: query failed: %s", e)
        return default


# ─── Identity Source Resolution ──────────────────────────────────────────────


def resolve_driver_name(driver_id: str) -> Optional[str]:
    """Primary source: ops.v_dim_driver_resolved (conductor_nombre from trips_unified)."""
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            row = _safe_query(
                cur,
                "SELECT driver_name FROM ops.v_dim_driver_resolved WHERE driver_id = %(did)s LIMIT 1",
                {"did": driver_id},
            )
            if row and row.get("driver_name"):
                return row["driver_name"].strip()
    except Exception:
        pass
    return None


def resolve_driver_phone(driver_id: str) -> dict[str, Any]:
    """
    Resolve phone from available sources in priority order:
    1. public.drivers_data.driver_phone
    2. public.drivers.phone
    3. public.module_ct_cabinet_drivers.driver_phone

    Returns {"phone": str|None, "phone_source": str, "missing": bool}
    """
    result = {"phone": None, "phone_source": "none", "missing": True}

    sources = [
        ("public.drivers_data", "driver_phone"),
        ("public.drivers", "phone"),
        ("public.module_ct_cabinet_drivers", "driver_phone"),
    ]

    for source_table, source_col in sources:
        try:
            with get_db() as conn:
                cur = _cursor(conn)
                row = _safe_query(
                    cur,
                    f"SELECT {source_col} FROM {source_table} WHERE driver_id = %(did)s LIMIT 1",
                    {"did": driver_id},
                )
                if row and row.get(source_col):
                    phone_val = str(row[source_col]).strip()
                    if phone_val and phone_val.lower() not in ("null", "none", ""):
                        result["phone"] = phone_val
                        result["phone_source"] = f"{source_table}.{source_col}"
                        result["missing"] = False
                        return result
        except Exception:
            continue

    return result


def resolve_driver_park(driver_id: str) -> dict[str, Any]:
    """Resolve park_id for a driver from public.drivers."""
    result = {"park_id": None, "park_name": None, "city": None, "country": None}
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            row = _safe_query(
                cur,
                "SELECT d.park_id, p.park_name, p.city, p.country "
                "FROM public.drivers d "
                "LEFT JOIN dim.dim_park p ON d.park_id = p.park_id "
                "WHERE d.driver_id = %(did)s LIMIT 1",
                {"did": driver_id},
            )
            if row:
                result["park_id"] = row.get("park_id")
                result["park_name"] = row.get("park_name")
                result["city"] = row.get("city")
                result["country"] = row.get("country")
    except Exception:
        pass

    if not result["park_name"]:
        try:
            with get_db() as conn:
                cur = _cursor(conn)
                row = _safe_query(
                    cur,
                    "SELECT park_name, city, country FROM ops.v_dim_park_resolved "
                    "WHERE park_id = %(pid)s LIMIT 1",
                    {"pid": result["park_id"]} if result["park_id"] else {"pid": ""},
                )
                if row:
                    result["park_name"] = row.get("park_name")
                    result["city"] = row.get("city") or result["city"]
                    result["country"] = row.get("country") or result["country"]
        except Exception:
            pass

    return result


def resolve_driver_timestamps(driver_id: str) -> dict[str, Any]:
    """Resolve first_seen_at, first_trip_at, latest_trip_at, latest_activity_at."""
    result = {
        "first_seen_at": None,
        "first_trip_at": None,
        "latest_trip_at": None,
        "latest_activity_at": None,
    }

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            row = _safe_query(
                cur,
                "SELECT created_at AS first_seen_at, hire_date "
                "FROM public.drivers WHERE driver_id = %(did)s LIMIT 1",
                {"did": driver_id},
            )
            if row:
                if row.get("first_seen_at"):
                    result["first_seen_at"] = _to_iso(row["first_seen_at"])
    except Exception:
        pass

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            row = _safe_query(
                cur,
                "SELECT activation_ts AS first_trip_at, last_completed_ts AS latest_trip_at "
                "FROM ops.mv_driver_lifecycle_base WHERE driver_key = %(did)s LIMIT 1",
                {"did": driver_id},
            )
            if row:
                if row.get("first_trip_at"):
                    result["first_trip_at"] = _to_iso(row["first_trip_at"])
                if row.get("latest_trip_at"):
                    result["latest_trip_at"] = _to_iso(row["latest_trip_at"])
    except Exception:
        pass

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            row = _safe_query(
                cur,
                "SELECT MAX(activity_date) AS latest_activity_at "
                "FROM ops.driver_daily_activity_fact "
                "WHERE driver_id = %(did)s",
                {"did": driver_id},
            )
            if row and row.get("latest_activity_at"):
                result["latest_activity_at"] = _to_iso(row["latest_activity_at"])
    except Exception:
        pass

    if not result["latest_activity_at"]:
        result["latest_activity_at"] = result["latest_trip_at"]

    return result


# ─── Unified Identity Resolution ────────────────────────────────────────────


def get_driver_identity(driver_id: str) -> dict[str, Any]:
    """
    Full identity resolution for a single driver.

    Returns:
        {
            driver_id, driver_name, phone, phone_source,
            country, city, park_id, park_name,
            first_seen_at, first_trip_at, latest_trip_at, latest_activity_at,
            identity_confidence, data_quality_status, missing_fields,
            refreshed_at
        }
    """
    if not driver_id:
        return _empty_identity(driver_id)

    name = resolve_driver_name(driver_id)
    phone_info = resolve_driver_phone(driver_id)
    park_info = resolve_driver_park(driver_id)
    timestamps = resolve_driver_timestamps(driver_id)

    missing = []
    if not name:
        missing.append("driver_name")
    if phone_info["missing"]:
        missing.append("phone")
    if not park_info.get("park_name"):
        missing.append("park_info")

    confidence = "high"
    if missing:
        confidence = "medium" if len(missing) <= 1 else "low"

    quality = "ok"
    if "phone" in missing:
        quality = "warning"
    if len(missing) >= 2:
        quality = "degraded"

    return {
        "driver_id": driver_id,
        "driver_name": name,
        "phone": phone_info["phone"],
        "phone_source": phone_info["phone_source"],
        "country": park_info.get("country"),
        "city": park_info.get("city"),
        "park_id": park_info.get("park_id"),
        "park_name": park_info.get("park_name"),
        "first_seen_at": timestamps.get("first_seen_at"),
        "first_trip_at": timestamps.get("first_trip_at"),
        "latest_trip_at": timestamps.get("latest_trip_at"),
        "latest_activity_at": timestamps.get("latest_activity_at"),
        "identity_confidence": confidence,
        "data_quality_status": quality,
        "missing_fields": missing,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


def search_driver_identities(
    driver_id: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    has_phone: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Search driver identities with optional filters.
    Returns list of identity records.
    """
    results = []

    # Build base query from public.drivers, with rich identity fields
    base_sql = """
    SELECT
        d.driver_id,
        COALESCE(dr.driver_name, NULLIF(TRIM(d.full_name), '')) AS driver_name,
        COALESCE(dd.driver_phone, d.phone::text, mct.driver_phone) AS phone,
        CASE WHEN dd.driver_phone IS NOT NULL THEN 'public.drivers_data.driver_phone'
             WHEN d.phone IS NOT NULL THEN 'public.drivers.phone'
             WHEN mct.driver_phone IS NOT NULL THEN 'public.module_ct_cabinet_drivers.driver_phone'
             ELSE 'none' END AS phone_source,
        COALESCE(dp.city, prk.city) AS city,
        COALESCE(dp.country, prk.country) AS country,
        d.park_id,
        COALESCE(dp.park_name, prk.park_name) AS park_name,
        d.created_at AS first_seen_at,
        lb.activation_ts AS first_trip_at,
        lb.last_completed_ts AS latest_trip_at,
        GREATEST(lb.last_completed_ts, d.created_at) AS latest_activity_at,
        CASE WHEN dd.driver_phone IS NOT NULL OR d.phone IS NOT NULL OR mct.driver_phone IS NOT NULL THEN 'high'
             WHEN dr.driver_name IS NOT NULL THEN 'medium'
             ELSE 'low' END AS identity_confidence,
        CASE WHEN dd.driver_phone IS NULL AND d.phone IS NULL AND mct.driver_phone IS NULL THEN 'warning'
             ELSE 'ok' END AS data_quality_status,
        NOW() AS refreshed_at
    FROM public.drivers d
    LEFT JOIN ops.v_dim_driver_resolved dr ON d.driver_id = dr.driver_id
    LEFT JOIN public.drivers_data dd ON d.driver_id = dd.driver_id
    LEFT JOIN public.module_ct_cabinet_drivers mct ON d.driver_id = mct.driver_id
    LEFT JOIN dim.dim_park dp ON d.park_id = dp.park_id
    LEFT JOIN ops.v_dim_park_resolved prk ON d.park_id = prk.park_id
    LEFT JOIN ops.mv_driver_lifecycle_base lb ON d.driver_id = lb.driver_key
    WHERE 1=1
    """

    params = {}
    conditions = []
    order_clause = "ORDER BY d.created_at DESC NULLS LAST"

    if driver_id:
        conditions.append("d.driver_id = %(driver_id)s")
        params["driver_id"] = driver_id

    if country:
        conditions.append("(dp.country = %(country)s OR prk.country = %(country)s)")
        params["country"] = country

    if city:
        conditions.append("(dp.city = %(city)s OR prk.city = %(city)s)")
        params["city"] = city

    if park_id:
        conditions.append("d.park_id = %(park_id)s")
        params["park_id"] = park_id

    if has_phone is True:
        conditions.append(
            "(dd.driver_phone IS NOT NULL OR d.phone IS NOT NULL OR mct.driver_phone IS NOT NULL)"
        )
    elif has_phone is False:
        conditions.append(
            "(dd.driver_phone IS NULL AND d.phone IS NULL AND mct.driver_phone IS NULL)"
        )

    if conditions:
        base_sql += " AND " + " AND ".join(conditions)

    base_sql += f" {order_clause} LIMIT %(limit)s OFFSET %(offset)s"
    params["limit"] = limit
    params["offset"] = offset

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute(base_sql, params)
            rows = cur.fetchall() or []
            for row in rows:
                record = {
                    "driver_id": row.get("driver_id"),
                    "driver_name": row.get("driver_name", "").strip() if row.get("driver_name") else None,
                    "phone": row.get("phone", "").strip() if row.get("phone") else None,
                    "phone_source": row.get("phone_source", "none"),
                    "country": row.get("country"),
                    "city": row.get("city"),
                    "park_id": row.get("park_id"),
                    "park_name": row.get("park_name"),
                    "first_seen_at": _to_iso(row.get("first_seen_at")),
                    "first_trip_at": _to_iso(row.get("first_trip_at")),
                    "latest_trip_at": _to_iso(row.get("latest_trip_at")),
                    "latest_activity_at": _to_iso(row.get("latest_activity_at")),
                    "identity_confidence": row.get("identity_confidence", "low"),
                    "data_quality_status": row.get("data_quality_status", "unknown"),
                    "missing_fields": _derive_missing(record_after=row),
                    "refreshed_at": _to_iso(datetime.now(timezone.utc)),
                }
                results.append(record)
    except Exception as e:
        logger.warning("driver_identity search failed: %s", e)

    return results


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _to_iso(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return str(val)


def _derive_missing(record_after: dict) -> list[str]:
    missing = []
    if not record_after.get("driver_name"):
        missing.append("driver_name")
    if not record_after.get("phone"):
        missing.append("phone")
    if not record_after.get("park_name"):
        missing.append("park_info")
    return missing


def _empty_identity(driver_id: str) -> dict[str, Any]:
    return {
        "driver_id": driver_id,
        "driver_name": None,
        "phone": None,
        "phone_source": "none",
        "country": None,
        "city": None,
        "park_id": None,
        "park_name": None,
        "first_seen_at": None,
        "first_trip_at": None,
        "latest_trip_at": None,
        "latest_activity_at": None,
        "identity_confidence": "low",
        "data_quality_status": "unknown",
        "missing_fields": ["driver_name", "phone", "park_info"],
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
