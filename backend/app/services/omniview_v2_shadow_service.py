"""
Omniview V2 Shadow Service — builds API contract from raw_yango MVs.
Shadow mode only. canonical_ready is always false.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.repositories.omniview_v2_shadow_repository import (
    get_daily_kpis,
    get_revenue_by_day,
    get_coverage_by_day,
    get_source_health,
    get_reconciliation_vs_ct,
)

logger = logging.getLogger(__name__)

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"


def _build_warnings(
    health: Dict[str, Any],
    reconciliation: Dict[str, Any],
) -> list:
    warnings = []

    if health.get("total_days", 0) < 7:
        warnings.append({
            "code": "SHORT_SERIES",
            "message": f"Only {health['total_days']} days of data available. Minimum 7 recommended.",
            "severity": "warning",
        })

    if health.get("coverage_pct", 100) < 95:
        warnings.append({
            "code": "PARTIAL_COVERAGE",
            "message": f"Coverage at {health['coverage_pct']}%. Below 95% threshold.",
            "severity": "warning" if health["coverage_pct"] >= 50 else "critical",
        })

    rev_delta = reconciliation.get("revenue_delta_pct")
    if rev_delta is not None and abs(rev_delta) > 5:
        warnings.append({
            "code": "REVENUE_DELTA",
            "message": f"Revenue delta vs CT is {rev_delta}%. Above 5% threshold.",
            "severity": "warning",
        })

    warnings.append({
        "code": "SINGLE_PARK_SCOPE",
        "message": "Only one park (Lima) ingested. Multi-park coverage pending.",
        "severity": "info",
    })

    return warnings


def build_shadow_response(
    park_id: str = PARK_ID,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    kpi_rows = get_daily_kpis(park_id, date_from, date_to)
    revenue_rows = get_revenue_by_day(park_id, date_from, date_to)
    coverage_rows = get_coverage_by_day(park_id, date_from, date_to)
    health = get_source_health(park_id)
    reconciliation = get_reconciliation_vs_ct(park_id, date_from, date_to)
    warnings = _build_warnings(health, reconciliation)

    total_orders = sum(r.get("orders_completed", 0) or 0 for r in kpi_rows)
    total_revenue = sum(r.get("revenue_partner_fee", 0) or 0 for r in revenue_rows)

    return {
        "source": "YANGO_API_SHADOW",
        "status": "SHADOW_ONLY",
        "canonical_ready": False,
        "grain": "day",
        "filters": {
            "park_id_masked": park_id[:8] + "***" if park_id else None,
            "date_from": date_from,
            "date_to": date_to,
        },
        "kpis": {
            "orders": total_orders,
            "revenue_partner_fee": round(total_revenue, 2),
            "revenue_per_order": round(total_revenue / total_orders, 4) if total_orders > 0 else 0,
            "driver_profiles": health.get("total_days", 0),
            "coverage_pct": health.get("coverage_pct", 0),
        },
        "coverage": {
            "health": health,
            "daily": coverage_rows,
        },
        "reconciliation": reconciliation,
        "warnings": warnings,
    }
