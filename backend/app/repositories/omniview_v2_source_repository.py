"""
Omniview V2 Source-Agnostic Repository — queries multiple source systems
through a unified interface.

Supported sources:
- CT_TRIPS_2026: ops.real_business_slice_{hour,day,week,month}_fact
- YANGO_API_RAW: raw_yango.mv_orders_day, raw_yango.mv_revenue_day

Never mixes sources. canonical_ready must be explicit.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

from app.services.omniview_v2_source_registry import (
    CT_TRIPS_2026,
    YANGO_API_RAW,
    SourceDefinition,
    SourceGrain,
    get_source,
)

logger = logging.getLogger(__name__)

CT_COUNTRY = "peru"
CT_CITY = "lima"
PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"


def _query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
    except Exception as e:
        logger.error("OV2 source repo error: %s", str(e)[:200])
        return []


def _query_one(sql: str, params: tuple = ()) -> Dict[str, Any]:
    rows = _query(sql, params)
    return rows[0] if rows else {}


def _serialize_date(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


# ═══════════════════════════════════════════════════════════════════
# CT_TRIPS_2026 Queries
# ═══════════════════════════════════════════════════════════════════

def _ct_get_kpis(
    grain: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
) -> List[Dict[str, Any]]:
    """Query CT real_business_slice by grain for given country/city."""
    src = get_source("CT_TRIPS_2026")
    if not src:
        return []

    grain_def = src.get_grain(grain)
    if not grain_def or not grain_def.supported:
        return []

    table = grain_def.table_name
    date_field = grain_def.date_field

    rows = _query(
        f"""
        SELECT
            {date_field} AS period_date,
            COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
            COALESCE(SUM(revenue_yego_final), 0)::numeric AS revenue_yego_final,
            COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers,
            COALESCE(AVG(avg_ticket), 0)::numeric AS avg_ticket,
            COALESCE(AVG(trips_per_driver), 0)::numeric AS trips_per_driver,
            COALESCE(AVG(commission_pct), 0)::numeric AS commission_pct,
            COALESCE(AVG(cancel_rate_pct), 0)::numeric AS cancel_rate_pct
        FROM {table}
        WHERE LOWER(TRIM(country)) = %s
          AND LOWER(TRIM(city)) = %s
          AND (%s::date IS NULL OR {date_field} >= %s::date)
          AND (%s::date IS NULL OR {date_field} <= %s::date)
        GROUP BY {date_field}
        ORDER BY {date_field}
        """,
        (country, city, date_from, date_from, date_to, date_to),
    )
    for r in rows:
        if r.get("period_date") and hasattr(r["period_date"], "isoformat"):
            r["period_date"] = r["period_date"].isoformat()
    return rows


def _ct_get_coverage(
    grain: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
) -> Dict[str, Any]:
    """Get coverage stats for CT source."""
    src = get_source("CT_TRIPS_2026")
    if not src:
        return {}

    grain_def = src.get_grain(grain)
    if not grain_def or not grain_def.supported:
        return {}

    table = grain_def.table_name
    date_field = grain_def.date_field

    row = _query_one(
        f"""
        SELECT
            COUNT(DISTINCT {date_field}) AS days_with_data,
            COUNT(DISTINCT {date_field}) AS expected_days
        FROM {table}
        WHERE LOWER(TRIM(country)) = %s
          AND LOWER(TRIM(city)) = %s
          AND (%s::date IS NULL OR {date_field} >= %s::date)
          AND (%s::date IS NULL OR {date_field} <= %s::date)
        """,
        (country, city, date_from, date_from, date_to, date_to),
    )

    days = int(row.get("days_with_data", 0) or 0)
    expected = int(row.get("expected_days", 0) or 0)
    return {
        "days_with_data": days,
        "expected_days": expected,
        "coverage_pct": round(days / expected * 100, 1) if expected > 0 else 0.0,
        "status": "FULL" if days == expected else "PARTIAL",
    }


def _ct_get_freshness(
    grain: str,
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
) -> Dict[str, Any]:
    """Get freshness metadata for CT source."""
    src = get_source("CT_TRIPS_2026")
    if not src:
        return {}

    grain_def = src.get_grain(grain)
    if not grain_def or not grain_def.supported:
        return {}

    table = grain_def.table_name
    date_field = grain_def.date_field

    row = _query_one(
        f"""
        SELECT
            MAX(refreshed_at) AS last_refreshed_at,
            MAX({date_field}) AS max_date
        FROM {table}
        WHERE LOWER(TRIM(country)) = %s
          AND LOWER(TRIM(city)) = %s
        """,
        (country, city),
    )
    last_refreshed = _serialize_date(row.get("last_refreshed_at"))
    max_date_val = _serialize_date(row.get("max_date"))
    return {
        "last_refreshed_at": last_refreshed,
        "max_period_date": max_date_val,
        "stale_since": None,
        "is_fresh": True,
    }


# ═══════════════════════════════════════════════════════════════════
# YANGO_API_RAW Queries
# ═══════════════════════════════════════════════════════════════════

def _yango_get_kpis(
    grain: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    park_id: str = PARK_ID,
) -> List[Dict[str, Any]]:
    """Query raw_yango MVs for KPIs."""
    if grain != "day":
        return []  # Only day grain supported currently

    rows = _query(
        """
        SELECT
            o.order_date AS period_date,
            o.orders_completed,
            o.orders_total,
            o.orders_cancelled,
            o.unique_drivers,
            r.revenue_partner_fee_amount,
            r.revenue_per_order,
            r.revenue_per_partner_fee_txn
        FROM raw_yango.mv_orders_day o
        LEFT JOIN raw_yango.mv_revenue_day r
            ON o.park_id = r.park_id AND o.order_date = r.revenue_date
        WHERE o.park_id = %s
          AND (%s::date IS NULL OR o.order_date >= %s::date)
          AND (%s::date IS NULL OR o.order_date <= %s::date)
        ORDER BY o.order_date
        """,
        (park_id, date_from, date_from, date_to, date_to),
    )
    for r in rows:
        if r.get("period_date") and hasattr(r["period_date"], "isoformat"):
            r["period_date"] = r["period_date"].isoformat()
    return rows


def _yango_get_coverage(
    grain: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    park_id: str = PARK_ID,
) -> Dict[str, Any]:
    """Get coverage stats for Yango source."""
    if grain != "day":
        return {"days_with_data": 0, "expected_days": 0, "coverage_pct": 0.0, "status": "NOT_SUPPORTED"}

    row = _query_one(
        """
        SELECT
            COUNT(*) AS days_with_data,
            COUNT(*) AS expected_days
        FROM raw_yango.mv_source_coverage_day
        WHERE park_id = %s
          AND (%s::date IS NULL OR coverage_date >= %s::date)
          AND (%s::date IS NULL OR coverage_date <= %s::date)
        """,
        (park_id, date_from, date_from, date_to, date_to),
    )
    days = int(row.get("days_with_data", 0) or 0)
    expected = int(row.get("expected_days", 0) or 0)
    return {
        "days_with_data": days,
        "expected_days": expected,
        "coverage_pct": round(days / expected * 100, 1) if expected > 0 else 0.0,
        "status": "FULL" if days == expected else "PARTIAL",
    }


def _yango_get_freshness(
    grain: str,
    park_id: str = PARK_ID,
) -> Dict[str, Any]:
    """Get freshness metadata for Yango source."""
    if grain != "day":
        return {}

    row = _query_one(
        """
        SELECT
            MAX(refreshed_at) AS last_refreshed_at,
            MAX(revenue_date) AS max_date
        FROM raw_yango.mv_revenue_day
        WHERE park_id = %s
        """,
        (park_id,),
    )
    return {
        "last_refreshed_at": _serialize_date(row.get("last_refreshed_at")),
        "max_period_date": _serialize_date(row.get("max_date")),
        "stale_since": None,
        "is_fresh": True,
    }


# ═══════════════════════════════════════════════════════════════════
# Public API — Source-Agnostic
# ═══════════════════════════════════════════════════════════════════

def get_kpis(
    source_system: str,
    grain: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Get KPI rows for a source/grain combination."""
    src = get_source(source_system)
    if not src:
        logger.warning("Unknown source_system: %s", source_system)
        return []

    grain_def = src.get_grain(grain)
    if not grain_def or not grain_def.supported:
        logger.warning("Grain %s not supported for source %s", grain, source_system)
        return []

    if source_system == "CT_TRIPS_2026":
        country = (filters or {}).get("country", CT_COUNTRY)
        city = (filters or {}).get("city", CT_CITY)
        return _ct_get_kpis(grain, date_from, date_to, country=country, city=city)

    if source_system == "YANGO_API_RAW":
        park_id = (filters or {}).get("park_id", PARK_ID)
        return _yango_get_kpis(grain, date_from, date_to, park_id=park_id)

    return []


def get_coverage(
    source_system: str,
    grain: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get coverage stats for a source/grain combination."""
    if source_system == "CT_TRIPS_2026":
        country = (filters or {}).get("country", CT_COUNTRY)
        city = (filters or {}).get("city", CT_CITY)
        return _ct_get_coverage(grain, date_from, date_to, country=country, city=city)

    if source_system == "YANGO_API_RAW":
        park_id = (filters or {}).get("park_id", PARK_ID)
        return _yango_get_coverage(grain, date_from, date_to, park_id=park_id)

    return {}


def get_freshness(
    source_system: str,
    grain: str,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get freshness metadata for a source/grain combination."""
    if source_system == "CT_TRIPS_2026":
        country = (filters or {}).get("country", CT_COUNTRY)
        city = (filters or {}).get("city", CT_CITY)
        return _ct_get_freshness(grain, country=country, city=city)

    if source_system == "YANGO_API_RAW":
        park_id = (filters or {}).get("park_id", PARK_ID)
        return _yango_get_freshness(grain, park_id=park_id)

    return {}


def get_lineage(
    source_system: str,
    grain: str,
    metric_id: str,
) -> Dict[str, Any]:
    """Get lineage info for a specific metric from a source."""
    src = get_source(source_system)
    if not src:
        return {}

    grain_def = src.get_grain(grain)
    metric_def = src.get_metric(metric_id)

    if not grain_def or not metric_def:
        return {}

    return {
        "origin_table": grain_def.table_name,
        "origin_field": metric_def.source_field,
        "aggregation": metric_def.aggregation,
        "source_system": source_system,
        "grain": grain,
    }
