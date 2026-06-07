"""
Omniview V2 Core Service — source-agnostic orchestration layer.

Responsibilities:
- Select source by source_system parameter
- Build unified OmniviewV2Response
- Aggregate warnings from source registry + operational state
- Never mix sources silently
- Support compare mode (two sources side-by-side)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.contracts.omniview_v2_contract import (
    OmniviewV2CompareResponse,
    OmniviewV2Coverage,
    OmniviewV2Freshness,
    OmniviewV2KpiValue,
    OmniviewV2Lineage,
    OmniviewV2Period,
    OmniviewV2Response,
    OmniviewV2Warning,
)
from app.repositories.omniview_v2_source_repository import (
    get_coverage,
    get_freshness,
    get_kpis,
    get_lineage,
)
from app.services.omniview_v2_source_registry import (
    CT_TRIPS_2026,
    YANGO_API_RAW,
    DEFAULT_SOURCE,
    SourceDefinition,
    get_source,
    get_supported_sources,
)

logger = logging.getLogger(__name__)


def _build_warnings(
    src: Optional[SourceDefinition],
    extra: Optional[List[Dict[str, Any]]] = None,
) -> List[OmniviewV2Warning]:
    warnings = []
    if src:
        for w in src.warnings:
            warnings.append(OmniviewV2Warning(
                code=w.get("code", "UNKNOWN"),
                message=w.get("message", ""),
                severity=w.get("severity", "warning"),
            ))
    for w in (extra or []):
        if w:
            warnings.append(OmniviewV2Warning(
                code=w.get("code", "UNKNOWN"),
                message=str(w.get("message", w)),
                severity=w.get("severity", "warning"),
            ))
    return warnings


def _build_kpi_value(
    metric_id: str,
    label: str,
    value: Optional[float],
    unit: str,
    source_system: str,
    source_table: str,
    grain: str,
    period: str,
    confidence: str = "MEDIUM",
    is_estimated: bool = False,
    warning_codes: Optional[List[str]] = None,
    lineage: Optional[Dict[str, Any]] = None,
) -> OmniviewV2KpiValue:
    lin = None
    if lineage:
        lin = OmniviewV2Lineage(
            origin_table=lineage.get("origin_table", ""),
            origin_field=lineage.get("origin_field", ""),
            aggregation=lineage.get("aggregation", "SUM"),
            filters_applied=lineage.get("filters_applied", {}),
        )
    return OmniviewV2KpiValue(
        metric_id=metric_id,
        label=label,
        value=value,
        unit=unit,
        source_system=source_system,
        source_table=source_table,
        grain=grain,
        period=period,
        confidence=confidence,
        is_estimated=is_estimated,
        warning_codes=warning_codes or [],
        lineage=lin,
    )


# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

def get_omniview_v2_summary(
    source_system: Optional[str] = None,
    grain: str = "day",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> OmniviewV2Response:
    """Build unified summary response for a single source."""
    source_key = source_system or DEFAULT_SOURCE
    src = get_source(source_key)
    if not src:
        return OmniviewV2Response(
            source_system=source_key,
            source_status="UNKNOWN",
            canonical_ready=False,
            grain=grain,
            warnings=[OmniviewV2Warning(code="UNKNOWN_SOURCE", message=f"Source {source_key} not registered.", severity="critical")],
        )

    grain_def = src.get_grain(grain)
    if not grain_def or not grain_def.supported:
        return OmniviewV2Response(
            source_system=source_key,
            source_status=src.status,
            canonical_ready=src.canonical_ready,
            grain=grain,
            filters=filters or {},
            warnings=[OmniviewV2Warning(code="GRAIN_NOT_SUPPORTED", message=f"Grain '{grain}' not supported for source {source_key}.", severity="warning")],
        )

    actual_filters = filters or src.default_filters

    # Query KPIs
    rows = get_kpis(source_key, grain, date_from, date_to, actual_filters)
    cov = get_coverage(source_key, grain, date_from, date_to, actual_filters)
    fresh = get_freshness(source_key, grain, actual_filters)

    # Aggregate KPIs
    total_orders = sum(int(r.get("trips_completed", 0) or r.get("orders_completed", 0) or 0) for r in rows)
    total_revenue = sum(float(r.get("revenue_yego_final", 0) or r.get("revenue_partner_fee_amount", 0) or 0) for r in rows)
    total_drivers = sum(int(r.get("active_drivers", 0) or r.get("unique_drivers", 0) or 0) for r in rows)

    source_table = grain_def.table_name

    # Build KPI list
    period_dates = sorted(set(r.get("period_date", "") for r in rows if r.get("period_date")))
    period_str = period_dates[0] if len(period_dates) == 1 else f"{period_dates[0]}:{period_dates[-1]}" if period_dates else ""

    kpis = []
    for metric_def in src.metrics:
        value = None
        if metric_def.metric_id == "orders":
            value = total_orders if total_orders > 0 else None
        elif metric_def.metric_id == "revenue":
            value = total_revenue if total_revenue > 0 else None
        elif metric_def.metric_id == "active_drivers":
            value = total_drivers if total_drivers > 0 else None
        elif metric_def.metric_id == "revenue_per_order":
            value = round(total_revenue / total_orders, 4) if total_orders > 0 and total_revenue > 0 else None
        elif metric_def.metric_id == "trips_per_driver":
            value = round(total_orders / total_drivers, 4) if total_drivers > 0 and total_orders > 0 else None
        elif metric_def.metric_id in ("avg_ticket", "commission_pct", "cancel_rate_pct"):
            values = [float(r.get(metric_def.source_field, 0) or 0) for r in rows if r.get(metric_def.source_field)]
            value = round(sum(values) / len(values), 4) if values else None

        lin = get_lineage(source_key, grain, metric_def.metric_id)
        kpis.append(_build_kpi_value(
            metric_id=metric_def.metric_id,
            label=metric_def.label,
            value=value,
            unit=metric_def.unit,
            source_system=source_key,
            source_table=source_table,
            grain=grain,
            period=period_str,
            confidence=metric_def.confidence,
            is_estimated=metric_def.is_estimated,
            lineage=lin,
        ))

    # Build warnings
    warnings = _build_warnings(src)

    # Revenue unavailable check
    if total_revenue is None or total_revenue == 0:
        warnings.append(OmniviewV2Warning(
            code="REVENUE_UNAVAILABLE",
            message="Revenue data unavailable for the requested period.",
            severity="warning",
        ))

    return OmniviewV2Response(
        source_system=source_key,
        source_status=src.status,
        canonical_ready=src.canonical_ready,
        grain=grain,
        period=OmniviewV2Period(from_date=date_from or "", to_date=date_to or ""),
        filters=actual_filters,
        kpis=kpis,
        coverage=OmniviewV2Coverage(
            days_with_data=cov.get("days_with_data", 0),
            expected_days=cov.get("expected_days", 0),
            coverage_pct=cov.get("coverage_pct", 0.0),
            status=cov.get("status", "UNKNOWN"),
        ),
        freshness=OmniviewV2Freshness(
            last_refreshed_at=fresh.get("last_refreshed_at"),
            is_fresh=fresh.get("is_fresh", True),
        ),
        warnings=warnings,
    )


# ═══════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════

def get_omniview_v2_health() -> Dict[str, Any]:
    """Get health status for all registered sources."""
    sources_health = {}
    all_ok = True

    for key, src in [("CT_TRIPS_2026", CT_TRIPS_2026), ("YANGO_API_RAW", YANGO_API_RAW)]:
        grain = src.supported_grains[0].grain if src.supported_grains else "day"
        cov = get_coverage(key, grain)
        fresh = get_freshness(key, grain)
        sources_health[key] = {
            "status": src.status,
            "canonical_ready": src.canonical_ready,
            "coverage_pct": cov.get("coverage_pct", 0.0),
            "freshness_ok": fresh.get("is_fresh", False),
            "warnings": len(src.warnings),
        }
        if cov.get("coverage_pct", 0) < 50:
            all_ok = False

    return {
        "healthy": all_ok,
        "sources": sources_health,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════
# Compare
# ═══════════════════════════════════════════════════════════════════

def get_source_comparison(
    source_a: str,
    source_b: str,
    grain: str = "day",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> OmniviewV2CompareResponse:
    """Compare two sources side-by-side at the same grain."""
    resp_a = get_omniview_v2_summary(source_a, grain, date_from, date_to, filters)
    resp_b = get_omniview_v2_summary(source_b, grain, date_from, date_to, filters)
    return OmniviewV2CompareResponse(
        source_a=resp_a,
        source_b=resp_b,
        grain=grain,
        period=OmniviewV2Period(from_date=date_from or "", to_date=date_to or ""),
    )
