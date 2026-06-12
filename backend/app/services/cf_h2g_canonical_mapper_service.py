"""
CF-H2G — Omniview Canonical Source Mapper Service

Shadow mode only. Reads from Yango and CT sources, applies metric ownership
from ops.omniview_metric_source_registry, produces canonical day fact rows
in ops.omniview_canonical_day_fact_shadow.

Does NOT:
- Modify production Omniview serving facts
- Change UI data sources
- Promote Yango as canonical
- Touch multipark
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.db.connection import get_db

logger = logging.getLogger(__name__)

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"
CITY = "lima"
COUNTRY = "peru"
MAPPER_VERSION = "CF-H2G-1.0"

TABLE_REGISTRY = "ops.omniview_metric_source_registry"
TABLE_SHADOW = "ops.omniview_canonical_day_fact_shadow"

STATUS_MATCH = "MATCH"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_EXPECTED_SEMANTIC_DELTA = "EXPECTED_SEMANTIC_DELTA"
STATUS_FALLBACK_USED = "FALLBACK_USED"
STATUS_SOURCE_MISSING = "SOURCE_MISSING"
STATUS_NOT_CERTIFIED = "NOT_CERTIFIED"
STATUS_DUPLICATE_ADJUSTED = "DUPLICATE_ADJUSTED"
STATUS_CT_PROXY_DIFFERENCE = "CT_PROXY_DIFFERENCE"

_LIMA_TZ = timezone(timedelta(hours=-5))


def _now():
    return datetime.now(timezone.utc)


def _ensure_today_date() -> str:
    return datetime.now(_LIMA_TZ).date().isoformat()


# ═══════════════════════════════════════════════════════════════════
# Registry Operations
# ═══════════════════════════════════════════════════════════════════

def get_metric_registry() -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT metric_name, metric_label, metric_tier, canonical_owner, "
            f"shadow_validator, fallback_source, source_badge, grain, "
            f"formula_sql_reference, confidence, promotion_status, rollback_source, "
            f"is_active, sort_order "
            f"FROM {TABLE_REGISTRY} WHERE is_active = true ORDER BY sort_order"
        )
        return [
            {
                "metric_name": r[0], "metric_label": r[1], "metric_tier": r[2],
                "canonical_owner": r[3], "shadow_validator": r[4],
                "fallback_source": r[5], "source_badge": r[6], "grain": r[7],
                "formula_sql_reference": r[8], "confidence": r[9],
                "promotion_status": r[10], "rollback_source": r[11],
                "is_active": r[12], "sort_order": r[13],
            }
            for r in cur.fetchall()
        ]


def get_metric_owner(metric_name: str) -> Optional[str]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT canonical_owner FROM {TABLE_REGISTRY} WHERE metric_name = %(m)s AND is_active = true",
            {"m": metric_name},
        )
        row = cur.fetchone()
        return row[0] if row else None


# ═══════════════════════════════════════════════════════════════════
# Yango Source Queries
# ═══════════════════════════════════════════════════════════════════

def _query_yango_orders(target_date: str, park_id: str = PARK_ID) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(DISTINCT order_id) AS completed_trips,
                COUNT(DISTINCT driver_profile_id) AS active_drivers
            FROM raw_yango.orders_raw
            WHERE park_id = %(p)s
              AND order_status = 'complete'
              AND order_ended_at::date = %(d)s
        """, {"p": park_id, "d": target_date})
        row = cur.fetchone()
        if row:
            return {"completed_trips": int(row[0] or 0), "active_drivers": int(row[1] or 0)}
    return {"completed_trips": 0, "active_drivers": 0}


def _query_yango_transactions(target_date: str, park_id: str = PARK_ID) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COALESCE(SUM(ABS(amount)) FILTER (
                    WHERE category_name = 'Partner fee for trip'
                ), 0) AS revenue_yego,
                COALESCE(SUM(amount) FILTER (
                    WHERE category_name IN ('Cash', 'Card payment', 'Corporate payment')
                ), 0) AS gmv_total,
                COALESCE(SUM(ABS(amount)) FILTER (
                    WHERE category_name = 'Service fee for trip'
                ), 0) AS service_fee
            FROM raw_yango.transactions_raw
            WHERE park_id = %(p)s
              AND event_at::date = %(d)s
        """, {"p": park_id, "d": target_date})
        row = cur.fetchone()
        if row:
            return {
                "revenue_yego": float(row[0] or 0),
                "gmv_total": float(row[1] or 0),
                "service_fee": float(row[2] or 0),
            }
    return {"revenue_yego": 0, "gmv_total": 0, "service_fee": 0}


def _query_yango_freshness(park_id: str = PARK_ID) -> Dict[str, Any]:
    now = _now()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                MAX(order_ended_at) AS last_order_at,
                MAX(api_fetched_at) AS last_order_ingested
            FROM raw_yango.orders_raw
            WHERE park_id = %(p)s
        """, {"p": park_id})
        row = cur.fetchone()
        last_order = row[0] if row else None
        last_ingested = row[1] if row else None

        cur.execute("""
            SELECT MAX(event_at) FROM raw_yango.transactions_raw
            WHERE park_id = %(p)s
        """, {"p": park_id})
        tx_row = cur.fetchone()
        last_tx = tx_row[0] if tx_row else None

    def _age_min(ts_val) -> Optional[float]:
        if ts_val is None:
            return None
        if isinstance(ts_val, str):
            ts_val = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
        if ts_val.tzinfo is None:
            ts_val = ts_val.replace(tzinfo=timezone.utc)
        return round((now - ts_val).total_seconds() / 60, 2)

    return {
        "last_order_ended_at": last_order.isoformat() if last_order else None,
        "last_order_ingested_at": last_ingested.isoformat() if last_ingested else None,
        "last_transaction_event_at": last_tx.isoformat() if last_tx else None,
        "order_freshness_minutes": _age_min(last_order),
        "transaction_freshness_minutes": _age_min(last_tx),
    }


# ═══════════════════════════════════════════════════════════════════
# CT Source Queries (for fallback and reconciliation)
# ═══════════════════════════════════════════════════════════════════

def _query_ct_day_fact(target_date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
                COALESCE(SUM(trips_cancelled), 0)::bigint AS trips_cancelled,
                COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers,
                COALESCE(SUM(revenue_yego_final), 0)::numeric AS revenue_yego_final,
                COALESCE(AVG(avg_ticket), 0)::numeric AS avg_ticket,
                COALESCE(AVG(trips_per_driver), 0)::numeric AS trips_per_driver,
                COALESCE(AVG(commission_pct), 0)::numeric AS commission_pct,
                COALESCE(AVG(cancel_rate_pct), 0)::numeric AS cancel_rate_pct
            FROM ops.real_business_slice_day_fact
            WHERE LOWER(TRIM(country)) = %(c)s
              AND LOWER(TRIM(city)) = %(ci)s
              AND trip_date = %(d)s
        """, {"c": COUNTRY, "ci": CITY, "d": target_date})
        row = cur.fetchone()
        if row:
            return {
                "trips_completed": int(row[0] or 0),
                "trips_cancelled": int(row[1] or 0),
                "active_drivers": int(row[2] or 0),
                "revenue_yego_final": float(row[3] or 0),
                "avg_ticket": float(row[4] or 0),
                "trips_per_driver": float(row[5] or 0),
                "commission_pct": float(row[6] or 0),
                "cancel_rate_pct": float(row[7] or 0),
            }
    return {}


# ═══════════════════════════════════════════════════════════════════
# Reconciliation
# ═══════════════════════════════════════════════════════════════════

def _reconcile_metric(
    metric_name: str,
    yango_val: Optional[float],
    ct_val: Optional[float],
    source_badge: str,
    threshold_pct: float = 5.0,
) -> Dict[str, Any]:
    if yango_val is None and ct_val is None:
        return {"status": STATUS_SOURCE_MISSING, "delta_abs": None, "delta_pct": None,
                "reason_code": "SOURCE_MISSING", "detail": "No data from either source"}

    if yango_val is None:
        return {"status": STATUS_FAIL, "delta_abs": None, "delta_pct": None,
                "reason_code": "SOURCE_MISSING", "detail": "Yango data missing"}
    if ct_val is None:
        return {"status": STATUS_SOURCE_MISSING, "delta_abs": None, "delta_pct": None,
                "reason_code": "SOURCE_MISSING", "detail": "CT data missing"}

    if source_badge == "FALLBACK_CT_BRIDGE":
        return {"status": STATUS_WARN, "delta_abs": 0, "delta_pct": 0,
                "reason_code": "FALLBACK_USED", "detail": "CT fallback used — no comparison possible"}

    if abs(ct_val) < 0.001 and abs(yango_val) < 0.001:
        return {"status": STATUS_MATCH, "delta_abs": 0, "delta_pct": 0,
                "reason_code": "MATCH", "detail": "Both zero"}

    if abs(ct_val) < 0.001:
        return {"status": STATUS_WARN, "delta_abs": abs(yango_val), "delta_pct": None,
                "reason_code": "EXPECTED_SEMANTIC_DELTA", "detail": "CT is zero, Yango has value"}

    delta_abs = abs(yango_val - ct_val)
    delta_pct = round(delta_abs / abs(ct_val) * 100, 4)

    if delta_pct <= threshold_pct:
        return {"status": STATUS_MATCH, "delta_abs": round(delta_abs, 4),
                "delta_pct": delta_pct, "reason_code": "MATCH", "detail": f"Within {threshold_pct}% threshold"}
    elif delta_pct <= threshold_pct * 3:
        return {"status": STATUS_WARN, "delta_abs": round(delta_abs, 4),
                "delta_pct": delta_pct, "reason_code": "EXPECTED_SEMANTIC_DELTA",
                "detail": f"Delta {delta_pct}% exceeds {threshold_pct}% but within {threshold_pct*3}%"}
    else:
        return {"status": STATUS_FAIL, "delta_abs": round(delta_abs, 4),
                "delta_pct": delta_pct, "reason_code": "CT_PROXY_DIFFERENCE",
                "detail": f"Delta {delta_pct}% exceeds {threshold_pct*3}% — likely proxy/scale difference"}


def _source_badge_for_metric(metric_name: str, yango_available: bool) -> str:
    owner = get_metric_owner(metric_name)
    if not owner:
        return "UNKNOWN"

    if owner == "YANGO":
        return "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE"
    elif owner == "CT_BRIDGE":
        return "CT_BRIDGE"
    elif owner == "SHARED":
        return "SHARED"
    elif owner == "HYBRID":
        return "HYBRID"
    elif owner == "BLOCKED":
        return "BLOCKED"
    return "UNKNOWN"


# ═══════════════════════════════════════════════════════════════════
# Core Mapper
# ═══════════════════════════════════════════════════════════════════

def generate_canonical_day_fact(
    target_date: str,
    park_id: str = PARK_ID,
) -> Dict[str, Any]:
    yango_orders = _query_yango_orders(target_date, park_id)
    yango_tx = _query_yango_transactions(target_date, park_id)
    yango_freshness = _query_yango_freshness(park_id)
    ct_fact = _query_ct_day_fact(target_date)

    yango_available = yango_orders.get("completed_trips", 0) > 0
    tx_available = yango_tx.get("revenue_yego", 0) > 0 or yango_tx.get("gmv_total", 0) > 0

    completed_trips = yango_orders["completed_trips"] if yango_available else ct_fact.get("trips_completed", 0)
    active_drivers = yango_orders["active_drivers"] if yango_available else ct_fact.get("active_drivers", 0)
    revenue_yego = yango_tx["revenue_yego"] if tx_available else ct_fact.get("revenue_yego_final", 0)
    gmv_total = yango_tx["gmv_total"] if tx_available else 0

    avg_ticket = round(gmv_total / completed_trips, 4) if completed_trips > 0 else 0
    trips_per_driver = round(completed_trips / active_drivers, 4) if active_drivers > 0 else 0
    revenue_per_order = round(revenue_yego / completed_trips, 4) if completed_trips > 0 else 0

    service_fee = yango_tx.get("service_fee", 0)
    commission_rate = round(service_fee / gmv_total, 4) if gmv_total > 0 else (
        round(revenue_yego / gmv_total, 4) if gmv_total > 0 else 0
    )

    cancelled_trips = ct_fact.get("trips_cancelled", 0)
    total_for_rate = completed_trips + cancelled_trips
    cancel_rate_pct = round(cancelled_trips / total_for_rate * 100, 4) if total_for_rate > 0 else 0

    order_freshness = yango_freshness.get("order_freshness_minutes")
    tx_freshness = yango_freshness.get("transaction_freshness_minutes")

    ct_completed = ct_fact.get("trips_completed", 0)
    ct_active = ct_fact.get("active_drivers", 0)
    ct_revenue = ct_fact.get("revenue_yego_final", 0)

    reconciliations = {
        "completed_trips": _reconcile_metric(
            "completed_trips", completed_trips, ct_completed,
            "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE", threshold_pct=1.0
        ),
        "active_drivers": _reconcile_metric(
            "active_drivers", active_drivers, ct_active,
            "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE", threshold_pct=5.0
        ),
        "revenue_yego": _reconcile_metric(
            "revenue_yego", revenue_yego, ct_revenue,
            "YANGO_API" if tx_available else "FALLBACK_CT_BRIDGE", threshold_pct=5.0
        ),
        "gmv": _reconcile_metric(
            "gmv", gmv_total, 0,
            "YANGO_API" if tx_available else "MISSING", threshold_pct=5.0
        ),
        "avg_ticket": _reconcile_metric(
            "avg_ticket", avg_ticket, ct_fact.get("avg_ticket", 0),
            "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE", threshold_pct=5.0
        ),
        "trips_per_driver": _reconcile_metric(
            "trips_per_driver", trips_per_driver, ct_fact.get("trips_per_driver", 0),
            "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE", threshold_pct=5.0
        ),
        "revenue_per_order": _reconcile_metric(
            "revenue_per_order", revenue_per_order, (
                ct_revenue / ct_completed if ct_completed > 0 else 0
            ),
            "YANGO_API" if tx_available else "FALLBACK_CT_BRIDGE", threshold_pct=5.0
        ),
        "commission_rate": _reconcile_metric(
            "commission_rate", commission_rate, ct_fact.get("commission_pct", 0) * 100 if ct_fact.get("commission_pct") else 0,
            "YANGO_API" if tx_available else "FALLBACK_CT_BRIDGE", threshold_pct=5.0
        ),
        "cancelled_trips": {
            "status": STATUS_NOT_CERTIFIED, "delta_abs": None, "delta_pct": None,
            "reason_code": "NOT_CERTIFIED",
            "detail": "Yango no ingiere cancelados. CT es unica fuente."
        },
        "cancel_rate_pct": {
            "status": STATUS_NOT_CERTIFIED, "delta_abs": None, "delta_pct": None,
            "reason_code": "NOT_CERTIFIED",
            "detail": "Yango no ingiere cancelados. Tasa es CT-only."
        },
    }

    coverage_yango = 100.0 if yango_available else 0.0
    coverage_tx = 100.0 if tx_available else 0.0

    fallback_used = not yango_available
    fallback_details = {}
    if fallback_used:
        fallback_details = {
            "completed_trips": "CT_BRIDGE" if not yango_available else "YANGO_API",
            "active_drivers": "CT_BRIDGE" if not yango_available else "YANGO_API",
            "revenue_yego": "CT_BRIDGE" if not tx_available else "YANGO_API",
            "gmv": "MISSING" if not tx_available else "YANGO_API",
            "reason": "Yango data unavailable for this date" if not yango_available else None,
        }

    day_fact = {
        "source_date": target_date,
        "park_id": park_id,
        "city": CITY,
        "country": COUNTRY,

        "completed_trips_value": completed_trips,
        "completed_trips_source_badge": "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE",
        "completed_trips_coverage_pct": coverage_yango,
        "completed_trips_freshness_min": order_freshness,
        "completed_trips_reconciliation": reconciliations["completed_trips"]["status"],

        "active_drivers_value": active_drivers,
        "active_drivers_source_badge": "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE",
        "active_drivers_coverage_pct": coverage_yango,
        "active_drivers_freshness_min": order_freshness,
        "active_drivers_reconciliation": reconciliations["active_drivers"]["status"],

        "revenue_yego_value": revenue_yego,
        "revenue_yego_source_badge": "YANGO_API" if tx_available else "FALLBACK_CT_BRIDGE",
        "revenue_yego_coverage_pct": coverage_tx,
        "revenue_yego_freshness_min": tx_freshness,
        "revenue_yego_reconciliation": reconciliations["revenue_yego"]["status"],

        "gmv_total_value": gmv_total,
        "gmv_total_source_badge": "YANGO_API" if tx_available else "MISSING",
        "gmv_total_coverage_pct": coverage_tx,
        "gmv_total_freshness_min": tx_freshness,
        "gmv_total_reconciliation": reconciliations["gmv"]["status"],

        "avg_ticket_value": avg_ticket,
        "avg_ticket_source_badge": "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE",
        "avg_ticket_coverage_pct": coverage_yango,
        "avg_ticket_freshness_min": order_freshness,
        "avg_ticket_reconciliation": reconciliations["avg_ticket"]["status"],

        "trips_per_driver_value": trips_per_driver,
        "trips_per_driver_source_badge": "YANGO_API" if yango_available else "FALLBACK_CT_BRIDGE",
        "trips_per_driver_coverage_pct": coverage_yango,
        "trips_per_driver_freshness_min": order_freshness,
        "trips_per_driver_reconciliation": reconciliations["trips_per_driver"]["status"],

        "revenue_per_order_value": revenue_per_order,
        "revenue_per_order_source_badge": "YANGO_API" if tx_available else "FALLBACK_CT_BRIDGE",
        "revenue_per_order_coverage_pct": coverage_tx,
        "revenue_per_order_freshness_min": tx_freshness,
        "revenue_per_order_reconciliation": reconciliations["revenue_per_order"]["status"],

        "commission_rate_value": commission_rate,
        "commission_rate_source_badge": "YANGO_API" if tx_available else "FALLBACK_CT_BRIDGE",
        "commission_rate_coverage_pct": coverage_tx,
        "commission_rate_freshness_min": tx_freshness,
        "commission_rate_reconciliation": reconciliations["commission_rate"]["status"],

        "cancelled_trips_value": cancelled_trips,
        "cancelled_trips_source_badge": "CT_BRIDGE",
        "cancelled_trips_coverage_pct": 100.0,
        "cancelled_trips_freshness_min": None,
        "cancelled_trips_reconciliation": reconciliations["cancelled_trips"]["status"],

        "cancel_rate_pct_value": cancel_rate_pct,
        "cancel_rate_pct_source_badge": "HYBRID",
        "cancel_rate_pct_coverage_pct": coverage_yango,
        "cancel_rate_pct_freshness_min": order_freshness,
        "cancel_rate_pct_reconciliation": reconciliations["cancel_rate_pct"]["status"],

        "generated_at": _now(),
        "mapper_version": MAPPER_VERSION,
        "fallback_used": fallback_used,
        "fallback_details": fallback_details if fallback_details else None,
    }

    return day_fact


def save_canonical_day_fact(day_fact: Dict[str, Any]) -> bool:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE_SHADOW} ("
                f"source_date, park_id, city, country, "
                f"completed_trips_value, completed_trips_source_badge, "
                f"completed_trips_coverage_pct, completed_trips_freshness_min, completed_trips_reconciliation, "
                f"active_drivers_value, active_drivers_source_badge, "
                f"active_drivers_coverage_pct, active_drivers_freshness_min, active_drivers_reconciliation, "
                f"revenue_yego_value, revenue_yego_source_badge, "
                f"revenue_yego_coverage_pct, revenue_yego_freshness_min, revenue_yego_reconciliation, "
                f"gmv_total_value, gmv_total_source_badge, "
                f"gmv_total_coverage_pct, gmv_total_freshness_min, gmv_total_reconciliation, "
                f"avg_ticket_value, avg_ticket_source_badge, "
                f"avg_ticket_coverage_pct, avg_ticket_freshness_min, avg_ticket_reconciliation, "
                f"trips_per_driver_value, trips_per_driver_source_badge, "
                f"trips_per_driver_coverage_pct, trips_per_driver_freshness_min, trips_per_driver_reconciliation, "
                f"revenue_per_order_value, revenue_per_order_source_badge, "
                f"revenue_per_order_coverage_pct, revenue_per_order_freshness_min, revenue_per_order_reconciliation, "
                f"commission_rate_value, commission_rate_source_badge, "
                f"commission_rate_coverage_pct, commission_rate_freshness_min, commission_rate_reconciliation, "
                f"cancelled_trips_value, cancelled_trips_source_badge, "
                f"cancelled_trips_coverage_pct, cancelled_trips_freshness_min, cancelled_trips_reconciliation, "
                f"cancel_rate_pct_value, cancel_rate_pct_source_badge, "
                f"cancel_rate_pct_coverage_pct, cancel_rate_pct_freshness_min, cancel_rate_pct_reconciliation, "
                f"generated_at, mapper_version, fallback_used, fallback_details"
                f") VALUES ("
                f"%(source_date)s, %(park_id)s, %(city)s, %(country)s, "
                f"%(cv)s, %(csb)s, %(ccp)s, %(cfm)s, %(cr)s, "
                f"%(av)s, %(asb)s, %(acp)s, %(afm)s, %(ar)s, "
                f"%(rv)s, %(rsb)s, %(rcp)s, %(rfm)s, %(rr)s, "
                f"%(gv)s, %(gsb)s, %(gcp)s, %(gfm)s, %(gr)s, "
                f"%(atv)s, %(atsb)s, %(atcp)s, %(atfm)s, %(atr)s, "
                f"%(tdv)s, %(tdsb)s, %(tdcp)s, %(tdfm)s, %(tdr)s, "
                f"%(rov)s, %(rosb)s, %(rocp)s, %(rofm)s, %(ror)s, "
                f"%(cmv)s, %(cmsb)s, %(cmcp)s, %(cmfm)s, %(cmr)s, "
                f"%(cxv)s, %(cxsb)s, %(cxcp)s, %(cxfm)s, %(cxr)s, "
                f"%(cprv)s, %(cprsb)s, %(cprcp)s, %(cprfm)s, %(cprr)s, "
                f"%(gen)s, %(mver)s, %(fu)s, %(fd)s::jsonb"
                f") "
                f"ON CONFLICT (source_date, park_id) DO UPDATE SET "
                f"completed_trips_value = EXCLUDED.completed_trips_value, "
                f"completed_trips_source_badge = EXCLUDED.completed_trips_source_badge, "
                f"completed_trips_coverage_pct = EXCLUDED.completed_trips_coverage_pct, "
                f"completed_trips_freshness_min = EXCLUDED.completed_trips_freshness_min, "
                f"completed_trips_reconciliation = EXCLUDED.completed_trips_reconciliation, "
                f"active_drivers_value = EXCLUDED.active_drivers_value, "
                f"active_drivers_source_badge = EXCLUDED.active_drivers_source_badge, "
                f"active_drivers_coverage_pct = EXCLUDED.active_drivers_coverage_pct, "
                f"active_drivers_freshness_min = EXCLUDED.active_drivers_freshness_min, "
                f"active_drivers_reconciliation = EXCLUDED.active_drivers_reconciliation, "
                f"revenue_yego_value = EXCLUDED.revenue_yego_value, "
                f"revenue_yego_source_badge = EXCLUDED.revenue_yego_source_badge, "
                f"revenue_yego_coverage_pct = EXCLUDED.revenue_yego_coverage_pct, "
                f"revenue_yego_freshness_min = EXCLUDED.revenue_yego_freshness_min, "
                f"revenue_yego_reconciliation = EXCLUDED.revenue_yego_reconciliation, "
                f"gmv_total_value = EXCLUDED.gmv_total_value, "
                f"gmv_total_source_badge = EXCLUDED.gmv_total_source_badge, "
                f"gmv_total_coverage_pct = EXCLUDED.gmv_total_coverage_pct, "
                f"gmv_total_freshness_min = EXCLUDED.gmv_total_freshness_min, "
                f"gmv_total_reconciliation = EXCLUDED.gmv_total_reconciliation, "
                f"avg_ticket_value = EXCLUDED.avg_ticket_value, "
                f"avg_ticket_source_badge = EXCLUDED.avg_ticket_source_badge, "
                f"avg_ticket_coverage_pct = EXCLUDED.avg_ticket_coverage_pct, "
                f"avg_ticket_freshness_min = EXCLUDED.avg_ticket_freshness_min, "
                f"avg_ticket_reconciliation = EXCLUDED.avg_ticket_reconciliation, "
                f"trips_per_driver_value = EXCLUDED.trips_per_driver_value, "
                f"trips_per_driver_source_badge = EXCLUDED.trips_per_driver_source_badge, "
                f"trips_per_driver_coverage_pct = EXCLUDED.trips_per_driver_coverage_pct, "
                f"trips_per_driver_freshness_min = EXCLUDED.trips_per_driver_freshness_min, "
                f"trips_per_driver_reconciliation = EXCLUDED.trips_per_driver_reconciliation, "
                f"revenue_per_order_value = EXCLUDED.revenue_per_order_value, "
                f"revenue_per_order_source_badge = EXCLUDED.revenue_per_order_source_badge, "
                f"revenue_per_order_coverage_pct = EXCLUDED.revenue_per_order_coverage_pct, "
                f"revenue_per_order_freshness_min = EXCLUDED.revenue_per_order_freshness_min, "
                f"revenue_per_order_reconciliation = EXCLUDED.revenue_per_order_reconciliation, "
                f"commission_rate_value = EXCLUDED.commission_rate_value, "
                f"commission_rate_source_badge = EXCLUDED.commission_rate_source_badge, "
                f"commission_rate_coverage_pct = EXCLUDED.commission_rate_coverage_pct, "
                f"commission_rate_freshness_min = EXCLUDED.commission_rate_freshness_min, "
                f"commission_rate_reconciliation = EXCLUDED.commission_rate_reconciliation, "
                f"cancelled_trips_value = EXCLUDED.cancelled_trips_value, "
                f"cancelled_trips_source_badge = EXCLUDED.cancelled_trips_source_badge, "
                f"cancelled_trips_coverage_pct = EXCLUDED.cancelled_trips_coverage_pct, "
                f"cancelled_trips_freshness_min = EXCLUDED.cancelled_trips_freshness_min, "
                f"cancelled_trips_reconciliation = EXCLUDED.cancelled_trips_reconciliation, "
                f"cancel_rate_pct_value = EXCLUDED.cancel_rate_pct_value, "
                f"cancel_rate_pct_source_badge = EXCLUDED.cancel_rate_pct_source_badge, "
                f"cancel_rate_pct_coverage_pct = EXCLUDED.cancel_rate_pct_coverage_pct, "
                f"cancel_rate_pct_freshness_min = EXCLUDED.cancel_rate_pct_freshness_min, "
                f"cancel_rate_pct_reconciliation = EXCLUDED.cancel_rate_pct_reconciliation, "
                f"generated_at = EXCLUDED.generated_at, "
                f"mapper_version = EXCLUDED.mapper_version, "
                f"fallback_used = EXCLUDED.fallback_used, "
                f"fallback_details = EXCLUDED.fallback_details",
                {
                    "source_date": day_fact["source_date"],
                    "park_id": day_fact["park_id"],
                    "city": day_fact["city"],
                    "country": day_fact["country"],
                    "cv": day_fact["completed_trips_value"],
                    "csb": day_fact["completed_trips_source_badge"],
                    "ccp": day_fact["completed_trips_coverage_pct"],
                    "cfm": day_fact["completed_trips_freshness_min"],
                    "cr": day_fact["completed_trips_reconciliation"],
                    "av": day_fact["active_drivers_value"],
                    "asb": day_fact["active_drivers_source_badge"],
                    "acp": day_fact["active_drivers_coverage_pct"],
                    "afm": day_fact["active_drivers_freshness_min"],
                    "ar": day_fact["active_drivers_reconciliation"],
                    "rv": day_fact["revenue_yego_value"],
                    "rsb": day_fact["revenue_yego_source_badge"],
                    "rcp": day_fact["revenue_yego_coverage_pct"],
                    "rfm": day_fact["revenue_yego_freshness_min"],
                    "rr": day_fact["revenue_yego_reconciliation"],
                    "gv": day_fact["gmv_total_value"],
                    "gsb": day_fact["gmv_total_source_badge"],
                    "gcp": day_fact["gmv_total_coverage_pct"],
                    "gfm": day_fact["gmv_total_freshness_min"],
                    "gr": day_fact["gmv_total_reconciliation"],
                    "atv": day_fact["avg_ticket_value"],
                    "atsb": day_fact["avg_ticket_source_badge"],
                    "atcp": day_fact["avg_ticket_coverage_pct"],
                    "atfm": day_fact["avg_ticket_freshness_min"],
                    "atr": day_fact["avg_ticket_reconciliation"],
                    "tdv": day_fact["trips_per_driver_value"],
                    "tdsb": day_fact["trips_per_driver_source_badge"],
                    "tdcp": day_fact["trips_per_driver_coverage_pct"],
                    "tdfm": day_fact["trips_per_driver_freshness_min"],
                    "tdr": day_fact["trips_per_driver_reconciliation"],
                    "rov": day_fact["revenue_per_order_value"],
                    "rosb": day_fact["revenue_per_order_source_badge"],
                    "rocp": day_fact["revenue_per_order_coverage_pct"],
                    "rofm": day_fact["revenue_per_order_freshness_min"],
                    "ror": day_fact["revenue_per_order_reconciliation"],
                    "cmv": day_fact["commission_rate_value"],
                    "cmsb": day_fact["commission_rate_source_badge"],
                    "cmcp": day_fact["commission_rate_coverage_pct"],
                    "cmfm": day_fact["commission_rate_freshness_min"],
                    "cmr": day_fact["commission_rate_reconciliation"],
                    "cxv": day_fact["cancelled_trips_value"],
                    "cxsb": day_fact["cancelled_trips_source_badge"],
                    "cxcp": day_fact["cancelled_trips_coverage_pct"],
                    "cxfm": day_fact["cancelled_trips_freshness_min"],
                    "cxr": day_fact["cancelled_trips_reconciliation"],
                    "cprv": day_fact["cancel_rate_pct_value"],
                    "cprsb": day_fact["cancel_rate_pct_source_badge"],
                    "cprcp": day_fact["cancel_rate_pct_coverage_pct"],
                    "cprfm": day_fact["cancel_rate_pct_freshness_min"],
                    "cprr": day_fact["cancel_rate_pct_reconciliation"],
                    "gen": day_fact["generated_at"],
                    "mver": day_fact["mapper_version"],
                    "fu": day_fact["fallback_used"],
                    "fd": __import__('json').dumps(day_fact.get("fallback_details") or {}),
                }
            )
            conn.commit()
        return True
    except Exception as e:
        logger.exception("Failed to save canonical day fact for %s: %s",
                         day_fact.get("source_date"), e)
        return False


def run_mapper_for_date_range(
    date_from: str,
    date_to: str,
    park_id: str = PARK_ID,
) -> Dict[str, Any]:
    results = []
    errors = []
    dates_covered = []
    fallback_dates = []

    from datetime import date as date_type, timedelta as td

    d_from = date_type.fromisoformat(date_from)
    d_to = date_type.fromisoformat(date_to)
    d_current = d_from

    while d_current <= d_to:
        target = d_current.isoformat()
        try:
            day_fact = generate_canonical_day_fact(target, park_id)
            saved = save_canonical_day_fact(day_fact)
            dates_covered.append(target)
            if day_fact.get("fallback_used"):
                fallback_dates.append(target)
            results.append({
                "date": target,
                "saved": saved,
                "fallback_used": day_fact.get("fallback_used"),
                "completed_trips": day_fact.get("completed_trips_value"),
                "revenue_yego": day_fact.get("revenue_yego_value"),
                "gmv": day_fact.get("gmv_total_value"),
                "active_drivers": day_fact.get("active_drivers_value"),
                "reconciliation_summary": {
                    "completed_trips": day_fact.get("completed_trips_reconciliation"),
                    "active_drivers": day_fact.get("active_drivers_reconciliation"),
                    "revenue_yego": day_fact.get("revenue_yego_reconciliation"),
                    "gmv": day_fact.get("gmv_total_reconciliation"),
                },
            })
        except Exception as e:
            errors.append({"date": target, "error": str(e)[:200]})
            logger.exception("Mapper failed for %s", target)

        d_current += td(days=1)

    return {
        "dates_covered": dates_covered,
        "total_dates": len(dates_covered),
        "fallback_dates": fallback_dates,
        "fallback_count": len(fallback_dates),
        "errors": errors,
        "results": results,
        "mapper_version": MAPPER_VERSION,
    }


def get_canonical_day_facts(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    park_id: str = PARK_ID,
) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT source_date, park_id, city, country, "
            f"completed_trips_value, completed_trips_source_badge, completed_trips_coverage_pct, "
            f"completed_trips_freshness_min, completed_trips_reconciliation, "
            f"active_drivers_value, active_drivers_source_badge, active_drivers_coverage_pct, "
            f"active_drivers_freshness_min, active_drivers_reconciliation, "
            f"revenue_yego_value, revenue_yego_source_badge, revenue_yego_coverage_pct, "
            f"revenue_yego_freshness_min, revenue_yego_reconciliation, "
            f"gmv_total_value, gmv_total_source_badge, gmv_total_coverage_pct, "
            f"gmv_total_freshness_min, gmv_total_reconciliation, "
            f"avg_ticket_value, cancelled_trips_value, cancel_rate_pct_value, "
            f"generated_at, mapper_version, fallback_used "
            f"FROM {TABLE_SHADOW} "
            f"WHERE park_id = %(p)s "
            f"  AND (%(df)s::date IS NULL OR source_date >= %(df)s::date) "
            f"  AND (%(dt)s::date IS NULL OR source_date <= %(dt)s::date) "
            f"ORDER BY source_date",
            {"p": park_id, "df": date_from, "dt": date_to}
        )
        return [
            {
                "source_date": str(r[0]), "park_id": r[1], "city": r[2], "country": r[3],
                "completed_trips_value": float(r[4]) if r[4] else None,
                "completed_trips_source_badge": r[5],
                "completed_trips_coverage_pct": float(r[6]) if r[6] else None,
                "completed_trips_freshness_min": float(r[7]) if r[7] else None,
                "completed_trips_reconciliation": r[8],
                "active_drivers_value": float(r[9]) if r[9] else None,
                "active_drivers_source_badge": r[10],
                "active_drivers_coverage_pct": float(r[11]) if r[11] else None,
                "active_drivers_freshness_min": float(r[12]) if r[12] else None,
                "active_drivers_reconciliation": r[13],
                "revenue_yego_value": float(r[14]) if r[14] else None,
                "revenue_yego_source_badge": r[15],
                "revenue_yego_coverage_pct": float(r[16]) if r[16] else None,
                "revenue_yego_freshness_min": float(r[17]) if r[17] else None,
                "revenue_yego_reconciliation": r[18],
                "gmv_total_value": float(r[19]) if r[19] else None,
                "gmv_total_source_badge": r[20],
                "gmv_total_coverage_pct": float(r[21]) if r[21] else None,
                "gmv_total_freshness_min": float(r[22]) if r[22] else None,
                "gmv_total_reconciliation": r[23],
                "avg_ticket_value": float(r[24]) if r[24] else None,
                "cancelled_trips_value": float(r[25]) if r[25] else None,
                "cancel_rate_pct_value": float(r[26]) if r[26] else None,
                "generated_at": r[27].isoformat() if r[27] else None,
                "mapper_version": r[28],
                "fallback_used": r[29],
            }
            for r in cur.fetchall()
        ]
