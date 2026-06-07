"""
Omniview V2 Contract — unified KPI and response data structures.

Source-agnostic contract. All Omniview V2 endpoints must conform to this.
Uses dataclasses for lightweight, dependency-free definitions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════
# Core Value Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2Lineage:
    """Traceability from metric value back to source."""
    origin_table: str
    origin_field: str
    aggregation: str = "SUM"
    filters_applied: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OmniviewV2KpiValue:
    """A single KPI measurement."""
    metric_id: str
    label: str
    value: Optional[float] = None
    unit: str = ""
    source_system: str = ""
    source_table: str = ""
    grain: str = "day"
    period: str = ""
    confidence: str = "MEDIUM"
    is_estimated: bool = False
    warning_codes: List[str] = field(default_factory=list)
    lineage: Optional[OmniviewV2Lineage] = None


@dataclass
class OmniviewV2Period:
    """Time period for the data."""
    from_date: str
    to_date: str


@dataclass
class OmniviewV2Coverage:
    """Source coverage statistics."""
    days_with_data: int = 0
    expected_days: int = 0
    coverage_pct: float = 0.0
    status: str = "UNKNOWN"


@dataclass
class OmniviewV2Freshness:
    """Data freshness metadata."""
    last_refreshed_at: Optional[str] = None
    stale_since: Optional[str] = None
    is_fresh: bool = True


@dataclass
class OmniviewV2Warning:
    """Operational warning."""
    code: str
    message: str
    severity: str = "warning"  # info, warning, critical


# ═══════════════════════════════════════════════════════════════════
# Unified Response
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2Response:
    """Complete Omniview V2 API response."""
    source_system: str
    source_status: str = ""
    canonical_ready: bool = False
    grain: str = "day"
    period: Optional[OmniviewV2Period] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    kpis: List[OmniviewV2KpiValue] = field(default_factory=list)
    coverage: Optional[OmniviewV2Coverage] = None
    freshness: Optional[OmniviewV2Freshness] = None
    warnings: List[OmniviewV2Warning] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(self)


@dataclass
class OmniviewV2CompareResponse:
    """Side-by-side comparison of two sources."""
    source_a: OmniviewV2Response
    source_b: OmniviewV2Response
    grain: str = "day"
    period: Optional[OmniviewV2Period] = None
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_a": self.source_a.to_dict(),
            "source_b": self.source_b.to_dict(),
            "grain": self.grain,
            "period": {"from": self.period.from_date, "to": self.period.to_date} if self.period else None,
            "generated_at": self.generated_at,
        }


# ═══════════════════════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════════════════════

def _serialize(obj: Any) -> Any:
    """Recursively convert dataclasses to dicts for JSON output."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if hasattr(obj, "__dataclass_fields__"):
        result = {}
        for f_name in obj.__dataclass_fields__:
            val = getattr(obj, f_name)
            if val is not None or f_name in ("warning_codes", "warnings", "kpis", "filters_applied", "filters"):
                result[f_name] = _serialize(val)
        return result
    return str(obj)
