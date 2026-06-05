"""
Omniview V2 Shadow Repository — reads from raw_yango MVs only.
Shadow mode: never writes, never touches V1 tables.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

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
        logger.error("Shadow repo query error: %s", str(e)[:200])
        return []


def _query_one(sql: str, params: tuple = ()) -> Dict[str, Any]:
    rows = _query(sql, params)
    return rows[0] if rows else {}


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
            o.orders_completed,
            o.orders_total,
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
        for k in ("order_date",):
            if r.get(k) and hasattr(r[k], "isoformat"):
                r[k] = r[k].isoformat()
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

    fd = cov.get("first_date")
    ld = cov.get("last_date")

    return {
        "park_id_masked": park_id[:8] + "***",
        "total_days": total,
        "full_days": full,
        "partial_days": int(cov.get("partial_days", 0) or 0),
        "coverage_pct": coverage_pct,
        "first_date": fd.isoformat() if fd and hasattr(fd, "isoformat") else str(fd) if fd else None,
        "last_date": ld.isoformat() if ld and hasattr(ld, "isoformat") else str(ld) if ld else None,
    }


# ── Reconciliation vs CT ─────────────────────────────────────

def get_reconciliation_vs_ct(
    park_id: str = PARK_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    mv_row = _query_one(
        """
        SELECT
            COALESCE(SUM(orders_completed), 0) AS trips,
            COALESCE(SUM(partner_fee_trip_amount), 0) AS revenue
        FROM raw_yango.mv_orders_day o
        LEFT JOIN raw_yango.mv_revenue_day r
            ON o.park_id = r.park_id AND o.order_date = r.revenue_date
        WHERE o.park_id = %s
          AND (%s::date IS NULL OR o.order_date >= %s::date)
          AND (%s::date IS NULL OR o.order_date <= %s::date)
        """,
        (park_id, date_from, date_from, date_to, date_to),
    )

    ct_row = _query_one(
        """
        SELECT
            SUM(trips_completed)::bigint AS trips,
            SUM(revenue_yego_final)::numeric AS revenue
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(REPLACE(REPLACE(country, '''', ''), '\"', ''))) = 'peru'
          AND LOWER(TRIM(REPLACE(REPLACE(city, '''', ''), '\"', ''))) = 'lima'
          AND (%s::date IS NULL OR trip_date >= %s::date)
          AND (%s::date IS NULL OR trip_date < %s::date)
        """,
        (date_from, date_from, date_to, date_to),
    )

    mv_trips = int(mv_row.get("trips", 0) or 0)
    mv_rev = float(mv_row.get("revenue", 0) or 0)
    ct_trips = int(ct_row.get("trips", 0) or 0)
    ct_rev = float(ct_row.get("revenue", 0) or 0)

    def _pct(a, b):
        if b and b != 0:
            return round((a - b) / b * 100, 2)
        return None

    return {
        "mv_trips": mv_trips,
        "mv_revenue_partner_fee": round(mv_rev, 2),
        "ct_trips": ct_trips,
        "ct_revenue_yego_final": round(ct_rev, 2),
        "trips_delta_pct": _pct(mv_trips, ct_trips),
        "revenue_delta_pct": _pct(mv_rev, ct_rev),
        "mv_revenue_per_order": round(mv_rev / mv_trips, 4) if mv_trips > 0 else 0,
        "ct_revenue_per_trip": round(ct_rev / ct_trips, 4) if ct_trips > 0 else 0,
    }
