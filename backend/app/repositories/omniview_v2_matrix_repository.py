"""
Omniview V2 Matrix Repository — source-specific raw data queries for matrix.

Returns raw data dicts that the view model service transforms into MatrixResponse.
Never mixes sources. Uses existing source tables.

CT_TRIPS_2026:
- day: ops.real_business_slice_day_fact
- week: ops.real_business_slice_week_fact
- month: ops.real_business_slice_month_fact
- hour: ops.real_business_slice_hour_fact

YANGO_API_RAW:
- day: raw_yango.mv_orders_day + raw_yango.mv_revenue_day
- week/month/hour: NOT_SUPPORTED

No inventa columnas. Inspecciona schema antes de consultar.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

CT_COUNTRY = "peru"
CT_CITY = "lima"
PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"

CT_GRAIN_TABLES = {
    "hour": ("ops.real_business_slice_hour_fact", "hour_start"),
    "day": ("ops.real_business_slice_day_fact", "trip_date"),
    "week": ("ops.real_business_slice_week_fact", "week_start"),
    "month": ("ops.real_business_slice_month_fact", "month"),
}


def _query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
    except Exception as e:
        logger.error("Matrix repo query error: %s", str(e)[:200])
        return []


def _serialize_date(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


# ═══════════════════════════════════════════════════════════════════
# CT_TRIPS_2026
# ═══════════════════════════════════════════════════════════════════

def _grain_table(grain: str) -> Tuple[Optional[str], Optional[str]]:
    return CT_GRAIN_TABLES.get(grain, (None, None))


def _period_range_from_grain(date_from: str, date_to: str) -> Tuple[str, str]:
    return date_from, date_to


def get_ct_matrix_data(
    grain: str = "day",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    country: str = CT_COUNTRY,
    city: str = CT_CITY,
) -> Tuple[str, List[Dict[str, Any]]]:
    table, date_field = _grain_table(grain)
    if not table:
        return "NOT_SUPPORTED", []

    if not date_from:
        date_from = (date.today() - timedelta(days=7)).isoformat()
    if not date_to:
        date_to = date.today().isoformat()

    rows = _query(
        f"""
        SELECT
            {date_field} AS period_date,
            business_slice_name,
            COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
            COALESCE(SUM(revenue_yego_final), 0)::numeric AS revenue_yego_final,
            COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers
        FROM {table}
        WHERE LOWER(TRIM(country)) = %s
          AND LOWER(TRIM(city)) = %s
          AND {date_field} >= %s::date
          AND {date_field} <= %s::date
        GROUP BY {date_field}, business_slice_name
        ORDER BY {date_field}, business_slice_name
        """,
        (country, city, date_from, date_to),
    )

    for r in rows:
        if r.get("period_date") and hasattr(r["period_date"], "isoformat"):
            r["period_date"] = r["period_date"].isoformat()
        elif isinstance(r.get("period_date"), date):
            r["period_date"] = r["period_date"].isoformat()

    status = "FULL" if rows else "NO_DATA"
    return status, rows


# ═══════════════════════════════════════════════════════════════════
# YANGO_API_RAW
# ═══════════════════════════════════════════════════════════════════

def get_yango_matrix_data(
    grain: str = "day",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    park_id: str = PARK_ID,
) -> Tuple[str, List[Dict[str, Any]]]:
    if grain != "day":
        return "NOT_SUPPORTED", []

    if not date_from:
        date_from = (date.today() - timedelta(days=5)).isoformat()
    if not date_to:
        date_to = date.today().isoformat()

    rows = _query(
        """
        SELECT
            o.order_date AS period_date,
            'Lima Fleet' AS fleet_name,
            o.orders_total,
            o.orders_completed,
            o.orders_cancelled,
            o.unique_drivers,
            o.unique_cars,
            r.revenue_partner_fee_amount,
            r.revenue_partner_fee_count,
            r.platform_fee_amount,
            r.platform_fee_vat_amount,
            r.gmv_cash_amount,
            r.gmv_card_amount,
            r.promo_compensation_amount,
            r.adjustments_amount,
            r.refunds_amount,
            r.linked_orders,
            r.revenue_per_order,
            r.revenue_per_partner_fee_txn,
            r.revenue_source,
            r.revenue_confidence,
            r.total_transactions_count
        FROM raw_yango.mv_orders_day o
        LEFT JOIN raw_yango.mv_revenue_day r
            ON o.park_id = r.park_id AND o.order_date = r.revenue_date
        WHERE o.park_id = %s
          AND o.order_date >= %s::date
          AND o.order_date <= %s::date
        ORDER BY o.order_date
        """,
        (park_id, date_from, date_to),
    )

    for r in rows:
        if r.get("period_date") and hasattr(r["period_date"], "isoformat"):
            r["period_date"] = r["period_date"].isoformat()
        elif isinstance(r.get("period_date"), date):
            r["period_date"] = r["period_date"].isoformat()

    status = "FULL" if rows else "NO_DATA"
    return status, rows


# ═══════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════

def get_matrix_data(
    source_system: str,
    grain: str = "day",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    if source_system == "CT_TRIPS_2026":
        country = (filters or {}).get("country", CT_COUNTRY)
        city = (filters or {}).get("city", CT_CITY)
        return get_ct_matrix_data(grain, date_from, date_to, country, city)

    if source_system == "YANGO_API_RAW":
        park_id = (filters or {}).get("park_id", PARK_ID)
        return get_yango_matrix_data(grain, date_from, date_to, park_id)

    return "UNKNOWN_SOURCE", []
