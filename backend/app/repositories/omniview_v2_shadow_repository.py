"""
Omniview V2 Shadow Repository — reads from raw_yango MVs only.
Shadow mode: never writes, never touches V1 tables.

Reads only from:
- raw_yango.mv_orders_day
- raw_yango.mv_transactions_day
- raw_yango.mv_revenue_day
- raw_yango.mv_driver_profiles_snapshot
- raw_yango.mv_source_coverage_day
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"

CT_COUNTRY = "peru"
CT_CITY = "lima"


def _query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
    except Exception as e:
        logger.error("Shadow repo query error: %s", str(e)[:200])
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


# ═══════════════════════════════════════════════════════════════
# CT Fallback Reconciliation Helpers
# ═══════════════════════════════════════════════════════════════

def _ct_query_country_city_date(
    target_date: str,
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
) -> Dict[str, Any]:
    """Query CT for exact country/city/date match."""
    return _query_one(
        """
        SELECT
            COALESCE(SUM(trips_completed), 0)::bigint AS trips,
            COALESCE(SUM(revenue_yego_final), 0)::numeric AS revenue,
            trip_date AS data_date
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country)) = %s
          AND LOWER(TRIM(city)) = %s
          AND trip_date = %s::date
        GROUP BY trip_date
        """,
        (country, city, target_date),
    )


def _ct_query_nearest_date(
    target_date: str,
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
    max_days_back: int = 30,
) -> Dict[str, Any]:
    """Query CT for nearest date <= target_date (within max_days_back)."""
    return _query_one(
        """
        SELECT
            COALESCE(SUM(trips_completed), 0)::bigint AS trips,
            COALESCE(SUM(revenue_yego_final), 0)::numeric AS revenue,
            trip_date AS data_date
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country)) = %s
          AND LOWER(TRIM(city)) = %s
          AND trip_date <= %s::date
          AND trip_date >= (%s::date - %s::int)
        GROUP BY trip_date
        ORDER BY trip_date DESC
        LIMIT 1
        """,
        (country, city, target_date, target_date, max_days_back),
    )


def _ct_check_availability(
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Check if CT has any data at all for this country/city.
    Returns (has_data, min_date, max_date).
    """
    row = _query_one(
        """
        SELECT
            MIN(trip_date) AS min_date,
            MAX(trip_date) AS max_date,
            COUNT(*) AS n
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country)) = %s
          AND LOWER(TRIM(city)) = %s
        """,
        (country, city),
    )
    if row and int(row.get("n", 0) or 0) > 0:
        return True, _serialize_date(row.get("min_date")), _serialize_date(row.get("max_date"))
    return False, None, None


def _resolve_ct_data(
    target_date: str,
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
) -> Dict[str, Any]:
    """
    Resolve CT data with controlled fallback:
    1. EXACT_CITY_DATE: exact country/city/date match
    2. NEAREST_DATE: nearest date <= target_date (within 30 days)
    3. UNAVAILABLE: no CT data at all for this country/city

    Never fabricates data. Returns full reconciliation context.
    """
    # Level 1: exact match
    ct = _ct_query_country_city_date(target_date, country, city)
    ct_trips = int(ct.get("trips", 0) or 0)
    if ct and ct_trips > 0:
        return {
            "ct_trips": ct_trips,
            "ct_revenue": float(ct.get("revenue", 0) or 0),
            "ct_data_date": _serialize_date(ct.get("data_date")),
            "ct_match_level": "EXACT_CITY_DATE",
            "ct_filter_used": f"country='{country}' city='{city}' date={target_date}",
            "ct_warning": None,
        }

    # Level 2: nearest available date
    nearby = _ct_query_nearest_date(target_date, country, city)
    nearby_trips = int(nearby.get("trips", 0) or 0)
    if nearby and nearby_trips > 0:
        nearby_date_str = _serialize_date(nearby.get("data_date"))
        return {
            "ct_trips": nearby_trips,
            "ct_revenue": float(nearby.get("revenue", 0) or 0),
            "ct_data_date": nearby_date_str,
            "ct_match_level": "NEAREST_DATE",
            "ct_filter_used": f"country='{country}' city='{city}' nearest <= {target_date} (used: {nearby_date_str})",
            "ct_warning": f"CT data missing for {target_date}. Using nearest available date {nearby_date_str}.",
        }

    # Level 3: check if CT has any data at all
    has_ct, ct_min, ct_max = _ct_check_availability(country, city)
    if has_ct:
        return {
            "ct_trips": 0,
            "ct_revenue": 0.0,
            "ct_data_date": None,
            "ct_match_level": "NO_DATE_IN_RANGE",
            "ct_filter_used": f"country='{country}' city='{city}' date={target_date}",
            "ct_warning": f"CT has data from {ct_min} to {ct_max} but no date matches or is within range of {target_date}.",
        }

    # Level 4: completely unavailable
    return {
        "ct_trips": 0,
        "ct_revenue": 0.0,
        "ct_data_date": None,
        "ct_match_level": "UNAVAILABLE",
        "ct_filter_used": f"country='{country}' city='{city}'",
        "ct_warning": f"No CT data found for country='{country}' city='{city}'. Reconciliation unavailable.",
    }


def _classify_status(mv_trips: int, mv_rev: float, ct_trips: int, ct_rev: float) -> str:
    """Classify reconciliation status based on data availability and deltas."""
    if ct_trips == 0 and mv_trips > 0:
        return "API_ONLY"

    if ct_trips == 0 and mv_trips == 0:
        return "NO_DATA"

    def _pct(a, b):
        if b and b != 0:
            return abs((a - b) / b * 100)
        return None

    trips_delta = _pct(mv_trips, ct_trips)
    rev_delta = _pct(mv_rev, ct_rev)

    max_delta = max(trips_delta or 0, rev_delta or 0)

    if max_delta == 0:
        return "MATCH"
    elif max_delta < 5:
        return "MINOR_DELTA"
    else:
        return "MAJOR_DELTA"


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

# ── Daily KPIs ───────────────────────────────────────────────

def get_daily_kpis(
    park_id: str = PARK_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows = _query(
        """
        SELECT
            o.order_date,
            o.orders_total,
            o.orders_completed,
            o.orders_cancelled,
            o.unique_drivers,
            o.unique_cars,
            r.partner_fee_trip_amount AS revenue_partner_fee,
            r.partner_fee_trip_count,
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
        if r.get("order_date") and hasattr(r["order_date"], "isoformat"):
            r["order_date"] = r["order_date"].isoformat()
    return rows


# ── Revenue by day ───────────────────────────────────────────

def get_revenue_by_day(
    park_id: str = PARK_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows = _query(
        """
        SELECT
            revenue_date,
            currency,
            partner_fee_trip_amount,
            partner_fee_trip_count,
            service_fee_trip_amount,
            service_fee_vat_amount,
            gmv_cash_card_amount,
            promo_compensation_amount,
            adjustments_amount,
            revenue_candidate_amount,
            revenue_candidate_count,
            linked_orders,
            revenue_per_order,
            revenue_per_partner_fee_txn
        FROM raw_yango.mv_revenue_day
        WHERE park_id = %s
          AND (%s::date IS NULL OR revenue_date >= %s::date)
          AND (%s::date IS NULL OR revenue_date <= %s::date)
        ORDER BY revenue_date
        """,
        (park_id, date_from, date_from, date_to, date_to),
    )
    for r in rows:
        if r.get("revenue_date") and hasattr(r["revenue_date"], "isoformat"):
            r["revenue_date"] = r["revenue_date"].isoformat()
    return rows


# ── Coverage by day ──────────────────────────────────────────

def get_coverage_by_day(
    park_id: str = PARK_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows = _query(
        """
        SELECT
            coverage_date,
            has_orders,
            has_transactions,
            has_revenue_candidate,
            orders_count,
            transactions_count,
            revenue_candidate_count,
            ingestion_runs_count,
            coverage_status
        FROM raw_yango.mv_source_coverage_day
        WHERE park_id = %s
          AND (%s::date IS NULL OR coverage_date >= %s::date)
          AND (%s::date IS NULL OR coverage_date <= %s::date)
        ORDER BY coverage_date
        """,
        (park_id, date_from, date_from, date_to, date_to),
    )
    for r in rows:
        if r.get("coverage_date") and hasattr(r["coverage_date"], "isoformat"):
            r["coverage_date"] = r["coverage_date"].isoformat()
    return rows


# ── Driver Profiles count ────────────────────────────────────

def get_driver_profiles_count(
    park_id: str = PARK_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    row = _query_one(
        """
        SELECT
            COUNT(*) AS total_profiles,
            COUNT(DISTINCT last_seen_at::date) AS snapshot_days,
            MIN(last_seen_at) AS first_seen,
            MAX(last_seen_at) AS last_seen
        FROM raw_yango.mv_driver_profiles_snapshot
        WHERE park_id = %s
          AND (%s::date IS NULL OR last_seen_at::date >= %s::date)
          AND (%s::date IS NULL OR last_seen_at::date <= %s::date)
        """,
        (park_id, date_from, date_from, date_to, date_to),
    )
    return {
        "total_profiles": int(row.get("total_profiles", 0) or 0),
        "snapshot_days": int(row.get("snapshot_days", 0) or 0),
        "first_seen": _serialize_date(row.get("first_seen")),
        "last_seen": _serialize_date(row.get("last_seen")),
    }


# ── Source health ────────────────────────────────────────────

def get_source_health(park_id: str = PARK_ID) -> Dict[str, Any]:
    cov = _query_one(
        """
        SELECT
            COUNT(*) AS total_days,
            COUNT(*) FILTER (WHERE coverage_status = 'FULL') AS full_days,
            COUNT(*) FILTER (WHERE coverage_status = 'PARTIAL') AS partial_days,
            MIN(coverage_date) AS first_date,
            MAX(coverage_date) AS last_date
        FROM raw_yango.mv_source_coverage_day
        WHERE park_id = %s
        """,
        (park_id,),
    )
    total = int(cov.get("total_days", 0) or 0)
    full = int(cov.get("full_days", 0) or 0)
    coverage_pct = round(full / total * 100, 1) if total > 0 else 0.0

    return {
        "park_id_masked": park_id[:8] + "***",
        "total_days": total,
        "full_days": full,
        "partial_days": int(cov.get("partial_days", 0) or 0),
        "coverage_pct": coverage_pct,
        "first_date": _serialize_date(cov.get("first_date")),
        "last_date": _serialize_date(cov.get("last_date")),
    }


# ── Reconciliation vs CT (hardened) ──────────────────────────

def get_reconciliation_vs_ct(
    park_id: str = PARK_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    # Aggregate MV side
    mv_agg = _query_one(
        """
        SELECT
            COALESCE(SUM(o.orders_completed), 0) AS trips,
            COALESCE(SUM(r.partner_fee_trip_amount), 0) AS revenue,
            MIN(o.order_date) AS mv_min_date,
            MAX(o.order_date) AS mv_max_date
        FROM raw_yango.mv_orders_day o
        LEFT JOIN raw_yango.mv_revenue_day r
            ON o.park_id = r.park_id AND o.order_date = r.revenue_date
        WHERE o.park_id = %s
          AND (%s::date IS NULL OR o.order_date >= %s::date)
          AND (%s::date IS NULL OR o.order_date <= %s::date)
        """,
        (park_id, date_from, date_from, date_to, date_to),
    )

    mv_trips = int(mv_agg.get("trips", 0) or 0)
    mv_rev = float(mv_agg.get("revenue", 0) or 0)

    # Resolve CT side with fallback
    target_date = date_to or date_from or _serialize_date(mv_agg.get("mv_max_date"))
    if target_date is None:
        target_date = date.today().isoformat()

    ct_result = _resolve_ct_data(
        target_date,
        country=CT_COUNTRY,
        city=CT_CITY,
    )

    ct_trips = ct_result["ct_trips"]
    ct_rev = ct_result["ct_revenue"]
    ct_match_level = ct_result["ct_match_level"]
    ct_data_date = ct_result["ct_data_date"]
    ct_warning = ct_result["ct_warning"]

    def _pct(a, b):
        if b and b != 0:
            return round((a - b) / b * 100, 2)
        return None

    status = _classify_status(mv_trips, mv_rev, ct_trips, ct_rev)

    # Build basis string
    if ct_match_level == "UNAVAILABLE":
        basis = "UNAVAILABLE"
    elif ct_match_level == "NO_DATE_IN_RANGE":
        basis = "NO_MATCHING_DATE"
    elif ct_match_level == "NEAREST_DATE":
        basis = "NEAREST_DATE"
    else:
        basis = "CITY_DATE"

    return {
        "status": status,
        "basis": basis,
        "ct_match_level": ct_match_level,
        "mv_orders": mv_trips,
        "mv_revenue_partner_fee": round(mv_rev, 2),
        "ct_trips": ct_trips,
        "ct_revenue_yego_final": round(ct_rev, 2),
        "trips_delta_pct": _pct(mv_trips, ct_trips),
        "revenue_delta_pct": _pct(mv_rev, ct_rev),
        "mv_revenue_per_order": round(mv_rev / mv_trips, 4) if mv_trips > 0 else 0,
        "ct_revenue_per_trip": round(ct_rev / ct_trips, 4) if ct_trips > 0 else 0,
        "ct_data_date": ct_data_date,
        "ct_filter_used": ct_result["ct_filter_used"],
        "mv_date_range": {
            "from": _serialize_date(mv_agg.get("mv_min_date")),
            "to": _serialize_date(mv_agg.get("mv_max_date")),
        },
        "warnings": [ct_warning] if ct_warning else [],
    }
