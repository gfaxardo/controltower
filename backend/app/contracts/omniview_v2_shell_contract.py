"""
Omniview V2 Shell Contract — section-based product shell data structures.

Defines the 10 internal sections of the Omniview V2 product shell.
Each section has explicit status, allowed actions, and source coupling.

Allowed actions: VIEW_DETAIL, VIEW_LINEAGE, VIEW_COVERAGE, VIEW_RECONCILIATION.
NO ACTION_ENGINE. NO DECISION. NO EXECUTION.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════════

SECTION_STATUS_OK = "OK"
SECTION_STATUS_WARNING = "WARNING"
SECTION_STATUS_BLOCKED = "BLOCKED"
SECTION_STATUS_NOT_READY = "NOT_READY"

ALLOWED_ACTIONS = {"VIEW_DETAIL", "VIEW_LINEAGE", "VIEW_COVERAGE", "VIEW_RECONCILIATION"}


# ═══════════════════════════════════════════════════════════════════
# Section Status
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2SectionStatus:
    code: str = SECTION_STATUS_OK  # OK | WARNING | BLOCKED | NOT_READY
    reason: str = ""
    severity: str = "info"  # info | warning | critical


# ═══════════════════════════════════════════════════════════════════
# Warning Item
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2ShellWarning:
    code: str
    message: str
    severity: str = "warning"  # info | warning | critical
    section_id: str = ""


# ═══════════════════════════════════════════════════════════════════
# Allowed Action
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2ShellAction:
    action_id: str  # VIEW_DETAIL | VIEW_LINEAGE | VIEW_COVERAGE | VIEW_RECONCILIATION
    label: str
    route: str = ""
    enabled: bool = True


# ═══════════════════════════════════════════════════════════════════
# Base Section
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2ShellSection:
    section_id: str
    title: str
    description: str = ""
    status: OmniviewV2SectionStatus = field(default_factory=OmniviewV2SectionStatus)
    source_system: str = ""
    canonical_ready: bool = False
    summary: str = ""
    kpis: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[OmniviewV2ShellWarning] = field(default_factory=list)
    lineage_refs: List[str] = field(default_factory=list)
    next_action_label: str = ""
    allowed_actions: List[OmniviewV2ShellAction] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# Concrete Sections
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2ExecutiveState(OmniviewV2ShellSection):
    section_id: str = "executive_state"
    title: str = "Executive State"
    description: str = "Overall operational pulse — is the data trustworthy right now?"
    source_list: List[str] = field(default_factory=list)
    active_warnings_count: int = 0
    last_refreshed_at: Optional[str] = None


@dataclass
class OmniviewV2SourceHealth(OmniviewV2ShellSection):
    section_id: str = "source_health"
    title: str = "Source Health"
    description: str = "Per-source coverage, freshness, and ingestion pipeline status."
    sources: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class OmniviewV2KpiStrip(OmniviewV2ShellSection):
    section_id: str = "kpi_strip"
    title: str = "KPI Strip"
    description: str = "Top-level numeric KPIs: orders, revenue, drivers, revenue per order."
    period: str = ""


@dataclass
class OmniviewV2PlanVsRealReadiness(OmniviewV2ShellSection):
    section_id: str = "plan_vs_real"
    title: str = "Plan vs Real Readiness"
    description: str = "Is plan data available for comparison?"
    plan_available: bool = False
    plan_periods: List[str] = field(default_factory=list)
    source_note: str = ""


@dataclass
class OmniviewV2GrowthMovement(OmniviewV2ShellSection):
    section_id: str = "growth_movement"
    title: str = "Growth Movement"
    description: str = "Directional indicators: is the metric growing or shrinking?"
    direction: str = "stable"  # up | down | stable
    magnitude_pct: Optional[float] = None
    prior_period: str = ""


@dataclass
class OmniviewV2OperationalCoverage(OmniviewV2ShellSection):
    section_id: str = "operational_coverage"
    title: str = "Operational Coverage"
    description: str = "How complete is the data? Days, parks, slices covered."
    coverage_pct: float = 0.0
    days_with_data: int = 0
    expected_days: int = 0
    gap_dates: List[str] = field(default_factory=list)


@dataclass
class OmniviewV2RevenueIntegrity(OmniviewV2ShellSection):
    section_id: str = "revenue_integrity"
    title: str = "Revenue Integrity"
    description: str = "Is revenue data complete and reconcilable?"
    revenue_value: Optional[float] = None
    revenue_per_order: Optional[float] = None
    delta_vs_ct_pct: Optional[float] = None
    reconciliation_status: str = "UNKNOWN"


@dataclass
class OmniviewV2SliceReadiness(OmniviewV2ShellSection):
    section_id: str = "slice_readiness"
    title: str = "Slice Readiness"
    description: str = "Are business slices properly segmented?"
    slice_count: int = 0
    slice_list: List[str] = field(default_factory=list)
    slice_gaps: List[str] = field(default_factory=list)


@dataclass
class OmniviewV2AlertsWarnings(OmniviewV2ShellSection):
    section_id: str = "alerts_warnings"
    title: str = "Alerts / Warnings"
    description: str = "Aggregated view of all operational warnings."
    all_warnings: List[OmniviewV2ShellWarning] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0


@dataclass
class OmniviewV2LineageBlock(OmniviewV2ShellSection):
    section_id: str = "lineage_audit"
    title: str = "Lineage / Audit"
    description: str = "Traceability from value back to source table/field."
    entries: List[Dict[str, Any]] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# Shell Response
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2ShellResponse:
    source_system: str
    source_status: str = ""
    canonical_ready: bool = False
    grain: str = "day"
    filters: Dict[str, Any] = field(default_factory=dict)
    period: Dict[str, str] = field(default_factory=dict)
    sections: List[OmniviewV2ShellSection] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_shell(self)


# ═══════════════════════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════════════════════

def _serialize_shell(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _serialize_shell(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_shell(v) for v in obj]
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for f_name in obj.__dataclass_fields__:
            val = getattr(obj, f_name)
            result[f_name] = _serialize_shell(val)
        return result
    return str(obj)
