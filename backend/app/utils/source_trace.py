"""
Source traceability for serving layer discipline.

Each feature registers its preferred serving source, forbidden sources,
and query mode. The diagnostics endpoint reads this registry to report
compliance, freshness, and enforcement status per feature.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.serving_guardrails import (
    FORBIDDEN_SERVING_SOURCES,
    ComplianceStatus,
    QueryMode,
    SourceType,
    get_all_declared_policies,
    get_db_gate_summary,
    get_db_guard_mode,
    get_feature_usage_summary,
    get_usage_log,
    is_policy_declared,
)

logger = logging.getLogger(__name__)


@dataclass
class ServingSourceEntry:
    feature_name: str
    endpoint: str
    service: str
    preferred_source: str
    source_type: SourceType
    source_grain: str
    query_mode: QueryMode = QueryMode.SERVING
    forbidden_sources: List[str] = field(default_factory=list)
    stale_threshold_hours: int = 48
    notes: str = ""
    endpoint_classification: str = "serving"


SERVING_REGISTRY: List[ServingSourceEntry] = [
    ServingSourceEntry(
        feature_name="Omniview monthly",
        endpoint="GET /ops/business-slice/monthly",
        service="business_slice_service.get_business_slice_monthly",
        preferred_source="ops.real_business_slice_month_fact",
        source_type=SourceType.FACT,
        source_grain="monthly",
        forbidden_sources=["ops.v_real_trips_business_slice_resolved", "ops.v_real_trips_enriched_base"],
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Omniview weekly",
        endpoint="GET /ops/business-slice/weekly",
        service="business_slice_service._weekly_from_fact",
        preferred_source="ops.real_business_slice_week_fact",
        source_type=SourceType.FACT,
        source_grain="weekly",
        forbidden_sources=["ops.v_real_trips_business_slice_resolved"],
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Omniview daily",
        endpoint="GET /ops/business-slice/daily",
        service="business_slice_service._daily_from_fact",
        preferred_source="ops.real_business_slice_day_fact",
        source_type=SourceType.FACT,
        source_grain="daily",
        stale_threshold_hours=24,
        forbidden_sources=["ops.v_real_trips_business_slice_resolved"],
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Omniview Matrix",
        endpoint="GET /ops/business-slice/omniview",
        service="business_slice_omniview_service.get_business_slice_omniview",
        preferred_source="ops.real_business_slice_month_fact",
        source_type=SourceType.FACT,
        source_grain="monthly/weekly/daily",
        forbidden_sources=["ops.v_real_trips_business_slice_resolved", "ops.v_real_trips_enriched_base"],
        notes="All grains served from facts (month/week/day). Resolved is build-only.",
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Control Loop Plan vs Real",
        endpoint="GET /ops/control-loop/plan-vs-real",
        service="control_loop_plan_vs_real_service.get_control_loop_plan_vs_real",
        preferred_source="ops.real_business_slice_month_fact",
        source_type=SourceType.FACT,
        source_grain="monthly",
        forbidden_sources=[
            "ops.v_real_monthly_control_loop_from_tajadas",
            "ops.v_real_trips_business_slice_resolved",
        ],
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Real LOB monthly",
        endpoint="GET /ops/real-lob/monthly",
        service="real_lob_service.get_real_lob_monthly_svc",
        preferred_source="ops.mv_real_trips_by_lob_month",
        source_type=SourceType.MV,
        source_grain="monthly",
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Real LOB monthly v2",
        endpoint="GET /ops/real-lob/monthly-v2",
        service="real_lob_service_v2.get_real_lob_monthly_v2",
        preferred_source="ops.mv_real_lob_month_v2",
        source_type=SourceType.MV,
        source_grain="monthly",
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Real LOB weekly v2",
        endpoint="GET /ops/real-lob/weekly-v2",
        service="real_lob_service_v2.get_real_lob_weekly_v2",
        preferred_source="ops.mv_real_lob_week_v2",
        source_type=SourceType.MV,
        source_grain="weekly",
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Real LOB v2 data",
        endpoint="GET /ops/real-lob/v2/data",
        service="real_lob_v2_data_service.get_real_lob_v2_data",
        preferred_source="ops.mv_real_lob_month_v2",
        source_type=SourceType.MV,
        source_grain="monthly/weekly",
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Real operational snapshot",
        endpoint="GET /ops/real-operational/snapshot",
        service="real_operational_service",
        preferred_source="ops.mv_real_lob_day_v2",
        source_type=SourceType.MV,
        source_grain="daily",
        stale_threshold_hours=24,
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Real LOB daily",
        endpoint="GET /ops/real-lob/daily/*",
        service="real_lob_daily_service",
        preferred_source="ops.real_rollup_day_fact",
        source_type=SourceType.FACT,
        source_grain="daily",
        stale_threshold_hours=24,
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Matrix integrity",
        endpoint="GET /ops/business-slice/matrix-operational-trust",
        service="omniview_matrix_integrity_service",
        preferred_source="ops.real_business_slice_day_fact",
        source_type=SourceType.FACT,
        source_grain="daily",
        query_mode=QueryMode.AUDIT,
        endpoint_classification="audit",
    ),
    ServingSourceEntry(
        feature_name="Real LOB drill",
        endpoint="GET /ops/real-lob/drill*",
        service="real_lob_drill_pro_service",
        preferred_source="ops.real_drill_dim_fact",
        source_type=SourceType.FACT,
        source_grain="multi-grain",
        query_mode=QueryMode.DRILL,
        endpoint_classification="drill",
    ),
    ServingSourceEntry(
        feature_name="Business slice coverage",
        endpoint="GET /ops/business-slice/coverage",
        service="business_slice_service.get_business_slice_coverage",
        preferred_source="ops.v_business_slice_coverage_month",
        source_type=SourceType.VIEW,
        source_grain="monthly",
        query_mode=QueryMode.DRILL,
        notes="DEBT: by_slice and resolution_counts queries use V_RESOLVED for resolution_status.",
        endpoint_classification="drill",
    ),
    ServingSourceEntry(
        feature_name="Real margin quality",
        endpoint="GET /ops/real-margin-quality",
        service="real_margin_quality_service",
        preferred_source="ops.v_real_trip_fact_v2",
        source_type=SourceType.VIEW,
        source_grain="trip-level",
        query_mode=QueryMode.AUDIT,
        notes="Needs trip-level for quality audit; accepted as audit endpoint.",
        endpoint_classification="audit",
    ),
    ServingSourceEntry(
        feature_name="Supply dynamics",
        endpoint="GET /ops/supply/*",
        service="supply_service",
        preferred_source="ops.mv_supply_segments_weekly",
        source_type=SourceType.MV,
        source_grain="weekly",
        stale_threshold_hours=168,
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Driver lifecycle",
        endpoint="GET /ops/driver-lifecycle/*",
        service="driver_lifecycle_service",
        preferred_source="ops.mv_driver_lifecycle_base",
        source_type=SourceType.MV,
        source_grain="weekly/monthly",
        stale_threshold_hours=168,
        endpoint_classification="serving",
    ),
    ServingSourceEntry(
        feature_name="Territory quality",
        endpoint="GET /ops/territory-quality/*",
        service="territory_quality_service",
        preferred_source="ops.v_territory_mapping_quality_kpis",
        source_type=SourceType.VIEW,
        source_grain="aggregated",
        notes="DEBT: some queries hit public.trips_all; needs dedicated summary MV.",
        endpoint_classification="serving",
    ),
]

_REGISTRY_BY_NAME: Dict[str, ServingSourceEntry] = {e.feature_name: e for e in SERVING_REGISTRY}


def get_feature_entry(feature_name: str) -> Optional[ServingSourceEntry]:
    return _REGISTRY_BY_NAME.get(feature_name)


def assert_feature_registered(feature_name: str) -> ServingSourceEntry:
    entry = _REGISTRY_BY_NAME.get(feature_name)
    if entry is None:
        logger.error("SERVING_REGISTRY_MISSING: feature=%s is not registered", feature_name)
        raise ValueError(f"Feature '{feature_name}' is not registered in SERVING_REGISTRY")
    return entry


def get_serving_registry() -> List[Dict[str, Any]]:
    return [
        {
            "feature_name": e.feature_name,
            "endpoint": e.endpoint,
            "service": e.service,
            "preferred_source": e.preferred_source,
            "source_type": e.source_type.value,
            "source_grain": e.source_grain,
            "query_mode": e.query_mode.value,
            "forbidden_sources": e.forbidden_sources,
            "stale_threshold_hours": e.stale_threshold_hours,
            "endpoint_classification": e.endpoint_classification,
            "notes": e.notes,
        }
        for e in SERVING_REGISTRY
    ]


def check_source_freshness(conn, table_name: str, date_column: str = "loaded_at") -> Dict[str, Any]:
    """Check row count and last refresh for a fact/MV table."""
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()[0]

        cur.execute(f"SELECT MAX({date_column}) FROM {table_name}")
        last_refresh = cur.fetchone()[0]
        cur.close()

        if row_count == 0:
            status = "empty"
        elif last_refresh is None:
            status = "unknown"
        else:
            status = "ok"

        return {
            "table": table_name,
            "row_count": row_count,
            "last_refresh_at": last_refresh.isoformat() if last_refresh else None,
            "last_refresh_raw": last_refresh,
            "source_status": status,
        }
    except Exception as e:
        return {
            "table": table_name,
            "row_count": None,
            "last_refresh_at": None,
            "last_refresh_raw": None,
            "source_status": "missing",
            "error": str(e),
        }


_FACT_TABLES_TO_CHECK = [
    ("ops.real_business_slice_month_fact", "loaded_at"),
    ("ops.real_business_slice_week_fact", "loaded_at"),
    ("ops.real_business_slice_day_fact", "loaded_at"),
    ("ops.real_business_slice_hour_fact", "loaded_at"),
    ("ops.real_drill_dim_fact", "last_trip_ts"),
]


def _compute_freshness(last_refresh_raw, threshold_hours: int) -> str:
    if last_refresh_raw is None:
        return "unknown"
    try:
        if hasattr(last_refresh_raw, "tzinfo") and last_refresh_raw.tzinfo is not None:
            now = datetime.now(timezone.utc)
            delta = now - last_refresh_raw
        else:
            delta = datetime.utcnow() - last_refresh_raw
        hours_old = delta.total_seconds() / 3600
        return "ok" if hours_old <= threshold_hours else "stale"
    except Exception:
        return "unknown"


def _compute_compliance(
    entry: ServingSourceEntry,
    fact_info: Dict[str, Any],
    usage_summary: Dict[str, Any],
) -> ComplianceStatus:
    usage = usage_summary.get(entry.feature_name)

    if usage and usage.get("forbidden_uses", 0) > 0:
        return ComplianceStatus.NON_COMPLIANT

    source_status = fact_info.get("source_status", "unknown")
    if source_status == "empty":
        return ComplianceStatus.WARNING
    if source_status == "missing":
        return ComplianceStatus.WARNING

    freshness = _compute_freshness(
        fact_info.get("last_refresh_raw"),
        entry.stale_threshold_hours,
    )
    if freshness == "stale":
        return ComplianceStatus.WARNING

    if source_status == "ok":
        return ComplianceStatus.COMPLIANT

    return ComplianceStatus.UNKNOWN


def _compute_recommended_action(
    entry: ServingSourceEntry,
    compliance: ComplianceStatus,
    fact_info: Dict[str, Any],
    usage: Optional[Dict[str, Any]],
) -> Optional[str]:
    if entry.notes:
        return entry.notes
    if compliance == ComplianceStatus.NON_COMPLIANT:
        if usage and usage.get("forbidden_uses", 0) > 0:
            return f"Forbidden source detected in runtime usage; switch to {entry.preferred_source}"
        return f"Use {entry.preferred_source} instead of current source"
    if compliance == ComplianceStatus.WARNING:
        status = fact_info.get("source_status", "unknown")
        if status == "empty":
            return f"Fact table {entry.preferred_source} is empty; run backfill"
        if status == "missing":
            return f"Fact table {entry.preferred_source} does not exist; run migration"
        return f"Source may be stale; check refresh for {entry.preferred_source}"
    return None


def get_unguarded_features() -> List[Dict[str, Any]]:
    """Features registered as serving but never traced via execute_serving_query at runtime."""
    usage = get_feature_usage_summary()
    unguarded = []
    for entry in SERVING_REGISTRY:
        if entry.query_mode != QueryMode.SERVING:
            continue
        if entry.feature_name not in usage:
            unguarded.append({
                "feature_name": entry.feature_name,
                "endpoint": entry.endpoint,
                "service": entry.service,
                "preferred_source": entry.preferred_source,
                "status": "unguarded",
                "reason": "No runtime trace recorded; ensure execute_serving_query is called",
            })
    return unguarded


def _runtime_gate_status(
    entry: ServingSourceEntry,
    usage: Optional[Dict[str, Any]],
    policy_declared: bool,
) -> str:
    if not policy_declared:
        return "BLOCKED"
    if entry.query_mode != QueryMode.SERVING:
        return "READY"
    if usage and usage.get("total_queries", 0) > 0:
        if usage.get("forbidden_uses", 0) > 0:
            return "DEGRADED"
        return "READY"
    return "UNKNOWN"


def get_serving_diagnostics_full(conn) -> List[Dict[str, Any]]:
    """Full diagnostics with compliance, freshness, hard-enforcement, and DB-gate status."""
    fact_status: Dict[str, Dict[str, Any]] = {}
    for table, col in _FACT_TABLES_TO_CHECK:
        fact_status[table] = check_source_freshness(conn, table, col)

    usage_summary = get_feature_usage_summary()
    declared_policies = get_all_declared_policies()
    db_gate_info = get_db_gate_summary()
    db_gate_by_feature = db_gate_info.get("by_feature", {})

    diagnostics = []
    for entry in SERVING_REGISTRY:
        ps = entry.preferred_source
        fact_info = fact_status.get(ps, {})

        usage = usage_summary.get(entry.feature_name)
        actual_source = usage.get("last_source") if usage else ps
        actual_source = actual_source or ps

        freshness = _compute_freshness(
            fact_info.get("last_refresh_raw"),
            entry.stale_threshold_hours,
        )

        compliance = _compute_compliance(entry, fact_info, usage_summary)

        forbidden_used = bool(usage and usage.get("forbidden_uses", 0) > 0)
        fallback_used = bool(usage and usage.get("fallbacks", 0) > 0)

        action = _compute_recommended_action(entry, compliance, fact_info, usage)

        policy_declared = entry.feature_name in declared_policies
        guarded_query_path_used = bool(usage and usage.get("total_queries", 0) > 0)
        preferred_match = (actual_source or "").strip().lower() == ps.strip().lower()
        gate_status = _runtime_gate_status(entry, usage, policy_declared)

        # DB gate fields (FASE 2.7)
        db_feat = db_gate_by_feature.get(entry.feature_name)
        db_gate_enabled = db_feat is not None
        query_context_present = db_gate_enabled and db_feat.get("total_gated", 0) > 0
        ungated_db_path = not db_gate_enabled and entry.query_mode == QueryMode.SERVING

        if db_gate_enabled and query_context_present:
            db_gate_status = "READY"
            if db_feat.get("warned", 0) > 0:
                db_gate_status = "WARN_ONLY"
        elif db_gate_enabled:
            db_gate_status = "DEGRADED"
        elif entry.query_mode != QueryMode.SERVING:
            db_gate_status = "READY"
        else:
            db_gate_status = "UNKNOWN"

        diagnostics.append({
            "feature_name": entry.feature_name,
            "registered": True,
            "endpoint": entry.endpoint,
            "endpoint_classification": entry.endpoint_classification,
            "query_mode": entry.query_mode.value,
            "preferred_source": ps,
            "preferred_source_type": entry.source_type.value,
            "actual_source_used": actual_source,
            "source_status": fact_info.get("source_status", "unknown"),
            "freshness_status": freshness,
            "last_refresh_at": fact_info.get("last_refresh_at"),
            "row_count": fact_info.get("row_count"),
            "fallback_allowed": False,
            "fallback_used": fallback_used,
            "fallback_reason": None,
            "forbidden_source_used": forbidden_used,
            "strict_mode": True,
            "compliance_status": compliance.value,
            "recommended_action": action,
            "policy_declared": policy_declared,
            "registry_declared": True,
            "guarded_query_path_used": guarded_query_path_used,
            "preferred_source_match": preferred_match,
            "runtime_gate_status": gate_status,
            "db_gate_enabled": db_gate_enabled,
            "db_guard_mode": db_gate_info.get("guard_mode", "unknown"),
            "query_context_present": query_context_present,
            "db_gate_status": db_gate_status,
            "ungated_db_path_detected": ungated_db_path,
        })
    return diagnostics
