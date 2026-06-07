"""
Omniview V2 Source Registry — defines all registered data sources for Omniview V2.

Each source declares:
- status: CURRENT_BASELINE | FUTURE_CANDIDATE | DEPRECATED
- canonical_ready: whether certified for operational decisions
- supported_grains: hour, day, week, month
- tables: serving tables/views per grain
- metrics: available KPIs with field mappings
- warnings: inherent limitations

DO NOT mix sources. canonical_ready must be explicit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

CURRENT_BASELINE = "CURRENT_BASELINE"
FUTURE_CANDIDATE = "FUTURE_CANDIDATE"
DEPRECATED = "DEPRECATED"


@dataclass
class SourceMetric:
    metric_id: str
    label: str
    source_field: str
    unit: str
    aggregation: str = "SUM"
    is_estimated: bool = False
    confidence: str = "HIGH"


@dataclass
class SourceGrain:
    grain: str
    table_name: str
    date_field: str
    supported: bool = True


@dataclass
class SourceDefinition:
    source_system: str
    status: str
    canonical_ready: bool
    description: str
    supported_grains: List[SourceGrain] = field(default_factory=list)
    metrics: List[SourceMetric] = field(default_factory=list)
    warnings: List[dict] = field(default_factory=list)
    default_filters: dict = field(default_factory=dict)

    def get_grain(self, grain: str) -> Optional[SourceGrain]:
        for g in self.supported_grains:
            if g.grain == grain:
                return g
        return None

    def get_metric(self, metric_id: str) -> Optional[SourceMetric]:
        for m in self.metrics:
            if m.metric_id == metric_id:
                return m
        return None


# ═══════════════════════════════════════════════════════════════════
# Source Definitions
# ═══════════════════════════════════════════════════════════════════

CT_TRIPS_2026 = SourceDefinition(
    source_system="CT_TRIPS_2026",
    status=CURRENT_BASELINE,
    canonical_ready=True,
    description="Control Tower trips_2025/trips_2026 via real_business_slice serving facts. Current production baseline.",
    supported_grains=[
        SourceGrain(grain="hour", table_name="ops.real_business_slice_hour_fact", date_field="hour_start"),
        SourceGrain(grain="day", table_name="ops.real_business_slice_day_fact", date_field="trip_date"),
        SourceGrain(grain="week", table_name="ops.real_business_slice_week_fact", date_field="week_start"),
        SourceGrain(grain="month", table_name="ops.real_business_slice_month_fact", date_field="month"),
    ],
    metrics=[
        SourceMetric(metric_id="orders", label="Orders Completed", source_field="trips_completed", unit="count"),
        SourceMetric(metric_id="revenue", label="Revenue YEGO Final", source_field="revenue_yego_final", unit="PEN"),
        SourceMetric(metric_id="active_drivers", label="Active Drivers", source_field="active_drivers", unit="count"),
        SourceMetric(metric_id="avg_ticket", label="Average Ticket", source_field="avg_ticket", unit="PEN", aggregation="AVG"),
        SourceMetric(metric_id="trips_per_driver", label="Trips per Driver", source_field="trips_per_driver", unit="ratio", aggregation="AVG"),
        SourceMetric(metric_id="commission_pct", label="Commission %", source_field="commission_pct", unit="percent", aggregation="AVG"),
        SourceMetric(metric_id="cancel_rate_pct", label="Cancellation Rate %", source_field="cancel_rate_pct", unit="percent", aggregation="AVG"),
        SourceMetric(metric_id="revenue_per_order", label="Revenue per Order", source_field="revenue_yego_net", unit="PEN", is_estimated=True, aggregation="COMPUTED"),
        SourceMetric(metric_id="supply_hours", label="Supply Hours", source_field="supply_hours", unit="hours", confidence="LOW"),
    ],
    warnings=[],
    default_filters={"country": "peru", "city": "lima"},
)

YANGO_API_RAW = SourceDefinition(
    source_system="YANGO_API_RAW",
    status=FUTURE_CANDIDATE,
    canonical_ready=False,
    description="Yango Fleet API via raw_yango MVs. Shadow mode only. Not ready for operational decisions.",
    supported_grains=[
        SourceGrain(grain="day", table_name="raw_yango.mv_orders_day", date_field="order_date"),
    ],
    metrics=[
        SourceMetric(metric_id="orders", label="Orders Completed", source_field="orders_completed", unit="count"),
        SourceMetric(metric_id="revenue", label="Revenue Partner Fee", source_field="revenue_partner_fee_amount", unit="PEN", confidence="MEDIUM"),
        SourceMetric(metric_id="active_drivers", label="Active Drivers", source_field="unique_drivers", unit="count"),
        SourceMetric(metric_id="revenue_per_order", label="Revenue per Order", source_field="revenue_per_order", unit="PEN", is_estimated=True, aggregation="COMPUTED"),
        SourceMetric(metric_id="trips_per_driver", label="Trips per Driver", source_field="orders_completed", unit="ratio", is_estimated=True, aggregation="COMPUTED"),
    ],
    warnings=[
        {"code": "PARTIAL_PARK_COVERAGE", "message": "Only Lima park ingested. Multi-park coverage pending.", "severity": "warning"},
        {"code": "API_COVERAGE_WARNING", "message": "API coverage ~98.88% for orders, ~21% for revenue vs CT.", "severity": "warning"},
        {"code": "CANONICAL_NOT_READY", "message": "This source is NOT certified for operational decisions.", "severity": "critical"},
    ],
    default_filters={"park_id": "08e20910d81d42658d4334d3f6d10ac0"},
)


# ═══════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════

SOURCES: dict = {
    "CT_TRIPS_2026": CT_TRIPS_2026,
    "YANGO_API_RAW": YANGO_API_RAW,
}

DEFAULT_SOURCE = "CT_TRIPS_2026"


def get_source(source_system: str) -> Optional[SourceDefinition]:
    """Look up a registered source by identifier."""
    return SOURCES.get(source_system)


def get_all_sources() -> List[SourceDefinition]:
    """Return all registered sources."""
    return list(SOURCES.values())


def get_supported_sources() -> List[dict]:
    """Return summary of supported sources (for API /sources endpoint)."""
    result = []
    for key, src in SOURCES.items():
        result.append({
            "source_system": src.source_system,
            "status": src.status,
            "canonical_ready": src.canonical_ready,
            "description": src.description,
            "supported_grains": [g.grain for g in src.supported_grains if g.supported],
            "metric_count": len(src.metrics),
            "warnings": src.warnings,
        })
    return result
