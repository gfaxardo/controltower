"""
Omniview V2 Shell Service — builds product shell sections on top of core service.

Each section is an independent block with status, KPIs, warnings, and allowed actions.
Uses the source-agnostic core (OV2-C.0) for data queries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.contracts.omniview_v2_shell_contract import (
    SECTION_STATUS_BLOCKED,
    SECTION_STATUS_NOT_READY,
    SECTION_STATUS_OK,
    SECTION_STATUS_WARNING,
    OmniviewV2AlertsWarnings,
    OmniviewV2ExecutiveState,
    OmniviewV2GrowthMovement,
    OmniviewV2KpiStrip,
    OmniviewV2LineageBlock,
    OmniviewV2OperationalCoverage,
    OmniviewV2PlanVsRealReadiness,
    OmniviewV2RevenueIntegrity,
    OmniviewV2SectionStatus,
    OmniviewV2ShellAction,
    OmniviewV2ShellResponse,
    OmniviewV2ShellSection,
    OmniviewV2ShellWarning,
    OmniviewV2SliceReadiness,
    OmniviewV2SourceHealth,
)
from app.repositories.omniview_v2_source_repository import (
    get_coverage,
    get_freshness,
    get_kpis,
)
from app.services.omniview_v2_core_service import get_omniview_v2_summary
from app.services.omniview_v2_source_registry import (
    YANGO_API_RAW,
    DEFAULT_SOURCE,
    SourceDefinition,
    get_source,
    get_supported_sources,
)

logger = logging.getLogger(__name__)

SECTION_IDS = [
    "executive_state", "source_health", "kpi_strip",
    "plan_vs_real", "growth_movement", "operational_coverage",
    "revenue_integrity", "slice_readiness", "alerts_warnings", "lineage_audit",
]


def _status(code: str, reason: str = "", severity: str = "info") -> OmniviewV2SectionStatus:
    return OmniviewV2SectionStatus(code=code, reason=reason, severity=severity)


def _action(action_id: str, label: str, route: str = "", enabled: bool = True) -> OmniviewV2ShellAction:
    return OmniviewV2ShellAction(action_id=action_id, label=label, route=route, enabled=enabled)


def _warn(code: str, message: str, severity: str = "warning", section_id: str = "") -> OmniviewV2ShellWarning:
    return OmniviewV2ShellWarning(code=code, message=message, severity=severity, section_id=section_id)


# ═══════════════════════════════════════════════════════════════════
# Section Builders
# ═══════════════════════════════════════════════════════════════════

def build_executive_state(
    src: SourceDefinition,
    grain: str,
    filters: Dict[str, Any],
    all_sections: List[OmniviewV2ShellSection],
) -> OmniviewV2ExecutiveState:
    """Overall operational pulse."""
    source_list = [s["source_system"] for s in get_all_available_sources_list()]
    warning_count = sum(1 for s in all_sections if s.status.code in (SECTION_STATUS_WARNING, SECTION_STATUS_BLOCKED))
    blocked_count = sum(1 for s in all_sections if s.status.code == SECTION_STATUS_BLOCKED)

    if blocked_count > 0:
        status_code = SECTION_STATUS_WARNING
        reason = f"{blocked_count} sections blocked"
    elif warning_count > 0:
        status_code = SECTION_STATUS_WARNING
        reason = f"{warning_count} sections with warnings"
    else:
        status_code = SECTION_STATUS_OK
        reason = "All sections operational"

    fresh = get_freshness(src.source_system, grain, filters)

    return OmniviewV2ExecutiveState(
        status=_status(status_code, reason),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        source_list=source_list,
        active_warnings_count=warning_count,
        last_refreshed_at=fresh.get("last_refreshed_at"),
        summary=f"Omniview V2 using {src.source_system}. {warning_count} active warnings.",
        allowed_actions=[_action("VIEW_DETAIL", "View Full Status")],
    )


def build_source_health(
    src: SourceDefinition,
    grain: str,
    filters: Dict[str, Any],
) -> OmniviewV2SourceHealth:
    """Per-source coverage and freshness."""
    sources_health = []
    all_ok = True

    for source_key, source_def in [("CT_TRIPS_2026", get_source("CT_TRIPS_2026")), ("YANGO_API_RAW", get_source("YANGO_API_RAW"))]:
        if not source_def:
            continue
        sg = grain if grain in [g.grain for g in source_def.supported_grains] else None
        cov = get_coverage(source_key, grain) if sg else {}
        fresh = get_freshness(source_key, grain) if sg else {}

        cov_pct = cov.get("coverage_pct", 0.0)
        if not sg:
            status_str = "NOT_SUPPORTED"
        elif cov_pct >= 95:
            status_str = "OK"
        elif cov_pct >= 50:
            status_str = "WARNING"
            all_ok = False
        else:
            status_str = "BLOCKED"
            all_ok = False

        sources_health.append({
            "source_system": source_def.source_system,
            "status": status_str,
            "canonical_ready": source_def.canonical_ready,
            "coverage_pct": cov_pct,
            "freshness_ok": fresh.get("is_fresh", False),
            "last_refreshed_at": fresh.get("last_refreshed_at"),
            "warnings_count": len(source_def.warnings),
        })

    return OmniviewV2SourceHealth(
        status=_status(SECTION_STATUS_OK if all_ok else SECTION_STATUS_WARNING),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        sources=sources_health,
        summary=f"{sum(1 for s in sources_health if s['status']=='OK')}/{len(sources_health)} sources healthy",
        allowed_actions=[_action("VIEW_DETAIL", "View Source Details")],
    )


def build_kpi_strip(
    src: SourceDefinition,
    grain: str,
    date_from: Optional[str],
    date_to: Optional[str],
    filters: Dict[str, Any],
) -> OmniviewV2KpiStrip:
    """Top-level KPI values."""
    summary = get_omniview_v2_summary(
        source_system=src.source_system,
        grain=grain,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
    )
    kpi_dict = summary.to_dict()
    kpi_list = kpi_dict.get("kpis", [])

    missing = sum(1 for k in kpi_list if k.get("value") is None)
    warnings = []
    if missing > 0:
        warnings.append(_warn("KPI_MISSING", f"{missing} KPI(s) have no value", "warning", "kpi_strip"))

    status_code = SECTION_STATUS_OK
    if missing == len(kpi_list):
        status_code = SECTION_STATUS_BLOCKED
        reason = "No KPI values available"
    elif missing > 0:
        status_code = SECTION_STATUS_WARNING
        reason = f"{missing}/{len(kpi_list)} KPIs missing"

    return OmniviewV2KpiStrip(
        status=_status(status_code, reason if missing > 0 else "All KPIs available"),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        kpis=kpi_list,
        period=kpi_dict.get("period", {}),
        warnings=warnings,
        summary=f"{len(kpi_list)} KPIs, {missing} missing",
        allowed_actions=[_action("VIEW_DETAIL", "View KPI Details"), _action("VIEW_LINEAGE", "View Lineage")],
    )


def build_plan_vs_real_readiness(
    src: SourceDefinition,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> OmniviewV2PlanVsRealReadiness:
    """Check if plan data infrastructure exists for this source AND real data exists."""
    if src.source_system == "YANGO_API_RAW":
        return OmniviewV2PlanVsRealReadiness(
            status=_status(SECTION_STATUS_BLOCKED, "Yango API has no plan infrastructure"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            plan_available=False,
            source_note="Plan vs Real is CT-native. Not available for YANGO_API_RAW.",
            summary="BLOCKED — no plan source for Yango API",
        )

    # CT: check if real data exists for the period
    has_real_data = True
    if date_from or date_to:
        from app.repositories.omniview_v2_source_repository import get_coverage
        cov = get_coverage(src.source_system, "day", date_from, date_to)
        has_real_data = cov.get("days_with_data", 0) > 0

    if not has_real_data:
        return OmniviewV2PlanVsRealReadiness(
            status=_status(SECTION_STATUS_WARNING, "Plan infrastructure exists but no real data for this period"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            plan_available=True,
            plan_periods=["monthly", "weekly"],
            source_note="Plan infrastructure ready. Real data pending for selected period.",
            summary="WARNING — plan available, real data not yet loaded",
        )

    return OmniviewV2PlanVsRealReadiness(
        status=_status(SECTION_STATUS_OK, "Plan infrastructure available (CT-native)"),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        plan_available=True,
        plan_periods=["monthly", "weekly"],
        source_note="Plan data available via ops.plan_business_slice_monthly and weekly.",
        summary="READY — plan data infrastructure present",
        allowed_actions=[_action("VIEW_DETAIL", "View Plan Readiness")],
    )


def build_growth_movement(
    src: SourceDefinition,
    grain: str,
    date_from: Optional[str],
    date_to: Optional[str],
    filters: Dict[str, Any],
) -> OmniviewV2GrowthMovement:
    """Directional growth indicators."""
    cov = get_coverage(src.source_system, grain, date_from, date_to, filters)
    days = cov.get("days_with_data", 0)

    if days == 0:
        return OmniviewV2GrowthMovement(
            status=_status(SECTION_STATUS_BLOCKED, "No data for selected period"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            direction="stable",
            summary=f"No data available for growth calculation",
        )

    if days < 2:
        return OmniviewV2GrowthMovement(
            status=_status(SECTION_STATUS_WARNING, f"Short series: only {days} day(s) of data"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            direction="stable",
            summary=f"Insufficient data for growth calculation ({days} days)",
        )

    if days < 7:
        return OmniviewV2GrowthMovement(
            status=_status(SECTION_STATUS_WARNING, f"Short series: {days} days < 7 recommended"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            direction="stable",
            summary=f"Growth indicators available but limited ({days} days)",
            warnings=[_warn("SHORT_SERIES", f"Only {days} days of data. At least 7 recommended for growth.", "warning", "growth_movement")],
        )

    return OmniviewV2GrowthMovement(
        status=_status(SECTION_STATUS_OK, f"{days} days of data available"),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        direction="stable",  # Would be computed from actual prior period comparison in OV2-D
        summary=f"Ready for growth analysis ({days} days)",
        allowed_actions=[_action("VIEW_DETAIL", "View Growth Details")],
    )


def build_operational_coverage(
    src: SourceDefinition,
    grain: str,
    date_from: Optional[str],
    date_to: Optional[str],
    filters: Dict[str, Any],
) -> OmniviewV2OperationalCoverage:
    """Data completeness section."""
    cov = get_coverage(src.source_system, grain, date_from, date_to, filters)
    cov_pct = cov.get("coverage_pct", 0.0)
    days_data = cov.get("days_with_data", 0)
    expected = cov.get("expected_days", 0)

    if days_data == 0:
        return OmniviewV2OperationalCoverage(
            status=_status(SECTION_STATUS_BLOCKED, "No data available"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            coverage_pct=0.0,
            summary="BLOCKED — no data for the requested period",
        )

    if cov_pct >= 95:
        status_code = SECTION_STATUS_OK
        reason = f"Coverage at {cov_pct}%"
    elif cov_pct >= 50:
        status_code = SECTION_STATUS_WARNING
        reason = f"Coverage at {cov_pct}% — below 95% threshold"
    else:
        status_code = SECTION_STATUS_BLOCKED
        reason = f"Coverage at {cov_pct}% — below 50% threshold"

    return OmniviewV2OperationalCoverage(
        status=_status(status_code, reason),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        coverage_pct=cov_pct,
        days_with_data=days_data,
        expected_days=expected,
        summary=f"{days_data}/{expected} days with data ({cov_pct}%)",
        allowed_actions=[_action("VIEW_DETAIL", "View Coverage Details"), _action("VIEW_COVERAGE", "Coverage Breakdown")],
    )


def build_revenue_integrity(
    src: SourceDefinition,
    grain: str,
    date_from: Optional[str],
    date_to: Optional[str],
    filters: Dict[str, Any],
) -> OmniviewV2RevenueIntegrity:
    """Revenue data completeness and reconciliation."""
    summary = get_omniview_v2_summary(
        source_system=src.source_system,
        grain=grain,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
    )
    kpi_dict = summary.to_dict()
    kpis = {k["metric_id"]: k for k in kpi_dict.get("kpis", [])}

    revenue_kpi = kpis.get("revenue", {})
    rev_per_order = kpis.get("revenue_per_order", {})
    rev_value = revenue_kpi.get("value")

    if rev_value is None or rev_value == 0:
        return OmniviewV2RevenueIntegrity(
            status=_status(SECTION_STATUS_BLOCKED, "Revenue unavailable"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            summary="BLOCKED — revenue data unavailable",
            warnings=[_warn("REVENUE_UNAVAILABLE", "No revenue data for the requested period.", "critical", "revenue_integrity")],
        )

    # For Yango source, get CT delta from reconciliation
    delta_pct = None
    reconciliation_status = "OK"
    if src.source_system == "YANGO_API_RAW":
        from app.repositories.omniview_v2_shadow_repository import get_reconciliation_vs_ct
        recon = get_reconciliation_vs_ct(date_from=date_from, date_to=date_to)
        delta_pct = recon.get("revenue_delta_pct")
        reconciliation_status = recon.get("status", "UNKNOWN")

    if delta_pct is not None and abs(delta_pct) > 5:
        status_code = SECTION_STATUS_WARNING
        reason = f"Revenue delta vs CT: {delta_pct}%"
    else:
        status_code = SECTION_STATUS_OK
        reason = f"Revenue available: {rev_value} {revenue_kpi.get('unit', '')}"

    return OmniviewV2RevenueIntegrity(
        status=_status(status_code, reason),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        revenue_value=rev_value,
        revenue_per_order=rev_per_order.get("value"),
        delta_vs_ct_pct=delta_pct,
        reconciliation_status=reconciliation_status,
        summary=f"Revenue: {rev_value} {revenue_kpi.get('unit', '')}",
        allowed_actions=[_action("VIEW_DETAIL", "View Revenue Details"), _action("VIEW_RECONCILIATION", "View Reconciliation")],
    )


def build_slice_readiness(
    src: SourceDefinition,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> OmniviewV2SliceReadiness:
    """Business slice segmentation readiness."""
    if src.source_system == "YANGO_API_RAW":
        return OmniviewV2SliceReadiness(
            status=_status(SECTION_STATUS_BLOCKED, "Yango API has no slice mapping"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            summary="BLOCKED — slice infrastructure is CT-native",
        )

    # CT: check if real data exists for the period
    has_data = True
    if date_from or date_to:
        from app.repositories.omniview_v2_source_repository import get_coverage
        cov = get_coverage(src.source_system, "day", date_from, date_to)
        has_data = cov.get("days_with_data", 0) > 0

    if not has_data:
        return OmniviewV2SliceReadiness(
            status=_status(SECTION_STATUS_WARNING, "Slice infrastructure exists but no data for this period"),
            source_system=src.source_system,
            canonical_ready=src.canonical_ready,
            slice_count=6,
            slice_list=["Auto regular", "YMA", "Tuk Tuk", "PRO", "Delivery", "Carga"],
            summary="WARNING — slices defined, data pending for selected period",
        )

    return OmniviewV2SliceReadiness(
        status=_status(SECTION_STATUS_OK, "Slice infrastructure available (CT-native)"),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        slice_count=6,
        slice_list=["Auto regular", "YMA", "Tuk Tuk", "PRO", "Delivery", "Carga"],
        summary="6 slices ready",
        allowed_actions=[_action("VIEW_DETAIL", "View Slice Details")],
    )


def build_alerts_warnings(
    all_sections: List[OmniviewV2ShellSection],
    src: SourceDefinition,
) -> OmniviewV2AlertsWarnings:
    """Aggregated warnings from all sections."""
    all_w = []
    for section in all_sections:
        for w in section.warnings:
            w.section_id = section.section_id
            all_w.append(w)

    critical_count = sum(1 for w in all_w if w.severity == "critical")
    warning_count = sum(1 for w in all_w if w.severity == "warning")
    info_count = sum(1 for w in all_w if w.severity == "info")

    if critical_count > 0:
        status_code = SECTION_STATUS_BLOCKED
    elif warning_count > 0:
        status_code = SECTION_STATUS_WARNING
    else:
        status_code = SECTION_STATUS_OK

    return OmniviewV2AlertsWarnings(
        status=_status(status_code, f"{critical_count} critical, {warning_count} warnings, {info_count} info"),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        all_warnings=all_w,
        critical_count=critical_count,
        warning_count=warning_count,
        info_count=info_count,
        summary=f"{len(all_w)} total warnings ({critical_count} critical)",
        allowed_actions=[_action("VIEW_DETAIL", "View All Warnings")],
    )


def build_lineage_block(
    src: SourceDefinition,
    grain: str,
    filters: Dict[str, Any],
) -> OmniviewV2LineageBlock:
    """Traceability from metrics back to source."""
    from app.repositories.omniview_v2_source_repository import get_lineage

    entries = []
    for metric in src.metrics:
        lin = get_lineage(src.source_system, grain, metric.metric_id)
        if lin:
            entries.append({
                "metric_id": metric.metric_id,
                "label": metric.label,
                "origin_table": lin.get("origin_table"),
                "origin_field": lin.get("origin_field"),
                "aggregation": lin.get("aggregation"),
            })

    return OmniviewV2LineageBlock(
        status=_status(SECTION_STATUS_OK if entries else SECTION_STATUS_WARNING),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        entries=entries,
        summary=f"{len(entries)} metrics with full lineage",
        allowed_actions=[_action("VIEW_LINEAGE", "View Full Lineage")],
    )


# ═══════════════════════════════════════════════════════════════════
# Shell Builder
# ═══════════════════════════════════════════════════════════════════

def get_all_available_sources_list() -> List[Dict[str, Any]]:
    return get_supported_sources()


def build_shell(
    source_system: Optional[str] = None,
    grain: str = "day",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> OmniviewV2ShellResponse:
    """Build the complete product shell for a source/grain combination."""
    source_key = source_system or DEFAULT_SOURCE
    src = get_source(source_key)

    if not src:
        section = OmniviewV2ShellSection(
            section_id="error",
            title="Unknown Source",
            status=_status(SECTION_STATUS_BLOCKED, f"Source '{source_key}' not registered"),
        )
        return OmniviewV2ShellResponse(
            source_system=source_key,
            source_status="UNKNOWN",
            canonical_ready=False,
            grain=grain,
            sections=[section],
        )

    actual_filters = filters or src.default_filters

    # Pre-compute shared data ONCE to avoid N duplicate DB queries
    from app.repositories.omniview_v2_source_repository import get_coverage as repo_coverage, get_freshness as repo_freshness

    shared_coverages = {}
    shared_freshness = repo_freshness(source_key, grain, actual_filters)
    shared_coverages["active"] = repo_coverage(source_key, grain, date_from, date_to, actual_filters)

    # Lazy: only compute other source health if needed (source_health section queries both sources)
    for other_key in ["CT_TRIPS_2026", "YANGO_API_RAW"]:
        if other_key != source_key:
            shared_coverages[other_key] = repo_coverage(other_key, grain)

    # Pre-compute core summary once (for kpi_strip + revenue_integrity)
    core_summary = get_omniview_v2_summary(
        source_system=source_key, grain=grain,
        date_from=date_from, date_to=date_to, filters=actual_filters,
    )

    # Sections list
    sections: List[OmniviewV2ShellSection] = []

    # 1. KPI Strip
    kpi_strip = build_kpi_strip_from_summary(core_summary, src)
    sections.append(kpi_strip)

    # 2. Source Health
    source_health = build_source_health_cached(src, grain, shared_coverages, shared_freshness)
    sections.append(source_health)

    # 3. Revenue Integrity
    rev_integrity = build_revenue_integrity_from_summary(core_summary, src, grain, date_from, date_to, actual_filters)
    sections.append(rev_integrity)

    # 4. Operational Coverage
    op_cov = build_operational_coverage_cached(src, grain, date_from, date_to, shared_coverages["active"])
    sections.append(op_cov)

    # 5. Growth Movement
    growth = build_growth_movement_cached(src, grain, date_from, date_to, shared_coverages["active"])
    sections.append(growth)

    # 6. Plan vs Real
    plan = build_plan_vs_real_readiness_cached(src, date_from, date_to, shared_coverages["active"])
    sections.append(plan)

    # 7. Slice Readiness
    slice_ready = build_slice_readiness_cached(src, date_from, date_to, shared_coverages["active"])
    sections.append(slice_ready)

    # 8. Lineage
    lineage = build_lineage_block(src, grain, actual_filters)
    sections.append(lineage)

    # 9. Alerts / Warnings
    alerts = build_alerts_warnings(sections, src)
    sections.append(alerts)

    # 10. Executive State
    executive = build_executive_state(src, grain, actual_filters, sections)
    sections.insert(0, executive)

    return OmniviewV2ShellResponse(
        source_system=src.source_system,
        source_status=src.status,
        canonical_ready=src.canonical_ready,
        grain=grain,
        filters=actual_filters,
        period={"from": date_from or "", "to": date_to or ""},
        sections=sections,
    )


# ── Cached variants (no duplicate DB queries) ─────────────────

def build_kpi_strip_from_summary(core_summary, src):
    kpi_dict = core_summary.to_dict()
    kpi_list = kpi_dict.get("kpis", [])
    missing = sum(1 for k in kpi_list if k.get("value") is None)
    warnings_list = []
    if missing > 0:
        warnings_list.append(_warn("KPI_MISSING", f"{missing} KPI(s) have no value", "warning", "kpi_strip"))
    status_code = SECTION_STATUS_OK
    reason = "All KPIs available"
    if missing == len(kpi_list):
        status_code = SECTION_STATUS_BLOCKED
        reason = "No KPI values available"
    elif missing > 0:
        status_code = SECTION_STATUS_WARNING
        reason = f"{missing}/{len(kpi_list)} KPIs missing"
    return OmniviewV2KpiStrip(
        status=_status(status_code, reason),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        kpis=kpi_list,
        period=kpi_dict.get("period", {}),
        warnings=warnings_list,
        summary=f"{len(kpi_list)} KPIs, {missing} missing",
        allowed_actions=[_action("VIEW_DETAIL", "View KPI Details"), _action("VIEW_LINEAGE", "View Lineage")],
    )


def build_source_health_cached(src, grain, coverages, freshness):
    sources_health = []
    all_ok = True
    for source_key, source_def in [("CT_TRIPS_2026", get_source("CT_TRIPS_2026")), ("YANGO_API_RAW", get_source("YANGO_API_RAW"))]:
        if not source_def:
            continue
        sg = grain if grain in [g.grain for g in source_def.supported_grains] else None
        cov = coverages.get(source_key, {})
        cov_pct = cov.get("coverage_pct", 0.0) if sg else 0.0
        if not sg:
            status_str = "NOT_SUPPORTED"
        elif cov_pct >= 95:
            status_str = "OK"
        elif cov_pct >= 50:
            status_str = "WARNING"; all_ok = False
        else:
            status_str = "BLOCKED"; all_ok = False
        sources_health.append({
            "source_system": source_def.source_system,
            "status": status_str,
            "canonical_ready": source_def.canonical_ready,
            "coverage_pct": cov_pct,
            "freshness_ok": freshness.get("is_fresh", False) if source_key == src.source_system else True,
            "last_refreshed_at": freshness.get("last_refreshed_at") if source_key == src.source_system else "",
            "warnings_count": len(source_def.warnings),
        })
    return OmniviewV2SourceHealth(
        status=_status(SECTION_STATUS_OK if all_ok else SECTION_STATUS_WARNING),
        source_system=src.source_system,
        canonical_ready=src.canonical_ready,
        sources=sources_health,
        summary=f"{sum(1 for s in sources_health if s['status']=='OK')}/{len(sources_health)} sources healthy",
        allowed_actions=[_action("VIEW_DETAIL", "View Source Details")],
    )


def build_revenue_integrity_from_summary(core_summary, src, grain, date_from, date_to, filters):
    kpi_dict = core_summary.to_dict()
    kpis = {k["metric_id"]: k for k in kpi_dict.get("kpis", [])}
    revenue_kpi = kpis.get("revenue", {})
    rev_per_order = kpis.get("revenue_per_order", {})
    rev_value = revenue_kpi.get("value")
    if rev_value is None or rev_value == 0:
        return OmniviewV2RevenueIntegrity(
            status=_status(SECTION_STATUS_BLOCKED, "Revenue unavailable"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            summary="BLOCKED — revenue data unavailable",
            warnings=[_warn("REVENUE_UNAVAILABLE", "No revenue data for the requested period.", "critical", "revenue_integrity")],
        )
    delta_pct = None
    reconciliation_status = "OK"
    if src.source_system == "YANGO_API_RAW":
        from app.repositories.omniview_v2_shadow_repository import get_reconciliation_vs_ct
        recon = get_reconciliation_vs_ct(date_from=date_from, date_to=date_to)
        delta_pct = recon.get("revenue_delta_pct")
        reconciliation_status = recon.get("status", "UNKNOWN")
    status_code = SECTION_STATUS_WARNING if (delta_pct is not None and abs(delta_pct) > 5) else SECTION_STATUS_OK
    reason = f"Revenue delta vs CT: {delta_pct}%" if (delta_pct is not None and abs(delta_pct) > 5) else f"Revenue available: {rev_value} {revenue_kpi.get('unit', '')}"
    return OmniviewV2RevenueIntegrity(
        status=_status(status_code, reason),
        source_system=src.source_system, canonical_ready=src.canonical_ready,
        revenue_value=rev_value, revenue_per_order=rev_per_order.get("value"),
        delta_vs_ct_pct=delta_pct, reconciliation_status=reconciliation_status,
        summary=f"Revenue: {rev_value} {revenue_kpi.get('unit', '')}",
        allowed_actions=[_action("VIEW_DETAIL", "View Revenue Details"), _action("VIEW_RECONCILIATION", "View Reconciliation")],
    )


def build_operational_coverage_cached(src, grain, date_from, date_to, cov):
    cov_pct = cov.get("coverage_pct", 0.0)
    days_data = cov.get("days_with_data", 0)
    expected = cov.get("expected_days", 0)
    if days_data == 0:
        return OmniviewV2OperationalCoverage(
            status=_status(SECTION_STATUS_BLOCKED, "No data available"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            coverage_pct=0.0, summary="BLOCKED — no data for the requested period",
        )
    if cov_pct >= 95: status_code, reason = SECTION_STATUS_OK, f"Coverage at {cov_pct}%"
    elif cov_pct >= 50: status_code, reason = SECTION_STATUS_WARNING, f"Coverage at {cov_pct}% — below 95% threshold"
    else: status_code, reason = SECTION_STATUS_BLOCKED, f"Coverage at {cov_pct}% — below 50% threshold"
    return OmniviewV2OperationalCoverage(
        status=_status(status_code, reason),
        source_system=src.source_system, canonical_ready=src.canonical_ready,
        coverage_pct=cov_pct, days_with_data=days_data, expected_days=expected,
        summary=f"{days_data}/{expected} days with data ({cov_pct}%)",
        allowed_actions=[_action("VIEW_DETAIL", "View Coverage Details"), _action("VIEW_COVERAGE", "Coverage Breakdown")],
    )


def build_growth_movement_cached(src, grain, date_from, date_to, cov):
    days = cov.get("days_with_data", 0)
    if days == 0:
        return OmniviewV2GrowthMovement(
            status=_status(SECTION_STATUS_BLOCKED, "No data for selected period"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            direction="stable", summary="No data available for growth calculation",
        )
    if days < 2:
        return OmniviewV2GrowthMovement(
            status=_status(SECTION_STATUS_WARNING, f"Short series: only {days} day(s)"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            direction="stable", summary=f"Insufficient data ({days} days)",
        )
    if days < 7:
        return OmniviewV2GrowthMovement(
            status=_status(SECTION_STATUS_WARNING, f"Short series: {days} days < 7 recommended"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            direction="stable", summary=f"Growth indicators available ({days} days)",
            warnings=[_warn("SHORT_SERIES", f"Only {days} days. At least 7 recommended.", "warning", "growth_movement")],
        )
    return OmniviewV2GrowthMovement(
        status=_status(SECTION_STATUS_OK, f"{days} days of data available"),
        source_system=src.source_system, canonical_ready=src.canonical_ready,
        direction="stable", summary=f"Ready for growth analysis ({days} days)",
        allowed_actions=[_action("VIEW_DETAIL", "View Growth Details")],
    )


def build_plan_vs_real_readiness_cached(src, date_from, date_to, cov):
    if src.source_system == "YANGO_API_RAW":
        return OmniviewV2PlanVsRealReadiness(
            status=_status(SECTION_STATUS_BLOCKED, "Yango API has no plan infrastructure"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            plan_available=False, source_note="Plan vs Real is CT-native.",
            summary="BLOCKED — no plan source for Yango API",
        )
    has_real_data = cov.get("days_with_data", 0) > 0
    if not has_real_data:
        return OmniviewV2PlanVsRealReadiness(
            status=_status(SECTION_STATUS_WARNING, "Plan infrastructure exists but no real data for this period"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            plan_available=True, plan_periods=["monthly", "weekly"],
            source_note="Plan infrastructure ready. Real data pending.",
            summary="WARNING — plan available, real data not yet loaded",
        )
    return OmniviewV2PlanVsRealReadiness(
        status=_status(SECTION_STATUS_OK, "Plan infrastructure available (CT-native)"),
        source_system=src.source_system, canonical_ready=src.canonical_ready,
        plan_available=True, plan_periods=["monthly", "weekly"],
        source_note="Plan data available via ops.plan_business_slice_monthly and weekly.",
        summary="READY — plan data infrastructure present",
        allowed_actions=[_action("VIEW_DETAIL", "View Plan Readiness")],
    )


def build_slice_readiness_cached(src, date_from, date_to, cov):
    if src.source_system == "YANGO_API_RAW":
        return OmniviewV2SliceReadiness(
            status=_status(SECTION_STATUS_BLOCKED, "Yango API has no slice mapping"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            summary="BLOCKED — slice infrastructure is CT-native",
        )
    has_data = cov.get("days_with_data", 0) > 0
    if not has_data:
        return OmniviewV2SliceReadiness(
            status=_status(SECTION_STATUS_WARNING, "Slice infrastructure exists but no data for this period"),
            source_system=src.source_system, canonical_ready=src.canonical_ready,
            slice_count=6, slice_list=["Auto regular", "YMA", "Tuk Tuk", "PRO", "Delivery", "Carga"],
            summary="WARNING — slices defined, data pending for selected period",
        )
    return OmniviewV2SliceReadiness(
        status=_status(SECTION_STATUS_OK, "Slice infrastructure available (CT-native)"),
        source_system=src.source_system, canonical_ready=src.canonical_ready,
        slice_count=6, slice_list=["Auto regular", "YMA", "Tuk Tuk", "PRO", "Delivery", "Carga"],
        summary="6 slices ready",
        allowed_actions=[_action("VIEW_DETAIL", "View Slice Details")],
    )


def get_shell_section(
    source_system: Optional[str] = None,
    grain: str = "day",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    section_id: str = "",
    filters: Optional[Dict[str, Any]] = None,
) -> Optional[OmniviewV2ShellSection]:
    """Get a single section by ID."""
    shell = build_shell(source_system, grain, date_from, date_to, filters)
    for s in shell.sections:
        if s.section_id == section_id:
            return s
    return None


def get_shell_sections_list() -> List[Dict[str, Any]]:
    """List all available section IDs with metadata."""
    return [
        {"section_id": "executive_state", "title": "Executive State", "description": "Overall operational pulse"},
        {"section_id": "source_health", "title": "Source Health", "description": "Per-source coverage and freshness"},
        {"section_id": "kpi_strip", "title": "KPI Strip", "description": "Top-level KPIs: orders, revenue, drivers"},
        {"section_id": "plan_vs_real", "title": "Plan vs Real Readiness", "description": "Plan data availability check"},
        {"section_id": "growth_movement", "title": "Growth Movement", "description": "Directional growth indicators"},
        {"section_id": "operational_coverage", "title": "Operational Coverage", "description": "Data completeness metrics"},
        {"section_id": "revenue_integrity", "title": "Revenue Integrity", "description": "Revenue completeness and reconciliation"},
        {"section_id": "slice_readiness", "title": "Slice Readiness", "description": "Business slice segmentation"},
        {"section_id": "alerts_warnings", "title": "Alerts / Warnings", "description": "Aggregated operational warnings"},
        {"section_id": "lineage_audit", "title": "Lineage / Audit", "description": "Traceability from value to source"},
    ]
