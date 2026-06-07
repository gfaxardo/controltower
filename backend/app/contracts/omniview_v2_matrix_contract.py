"""
Omniview V2 Matrix Contract — matrix data structures for Omniview V2.

Defines the MatrixResponse contract that all sources must produce.
MatrixZone component is source-agnostic: it only consumes MatrixResponse.
Builds on OV2-C.2 Cell Contract and OV2-C.2B Visual System.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════
# Matrix Column
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2MatrixColumn:
    id: str
    label: str
    grain: str = "day"
    period: str = ""
    period_status: str = "CURRENT"  # CLOSED | PARTIAL | CURRENT | FUTURE | NO_PLAN | NO_REAL
    sort_key: str = ""
    width: int = 90
    is_current: bool = False
    is_future: bool = False


# ═══════════════════════════════════════════════════════════════════
# Matrix Row
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2MatrixRow:
    id: str
    label: str
    row_type: str = "slice"  # slice | metric | total | header
    row_status: str = "OK"   # OK | WARNING | BLOCKED
    parent_id: Optional[str] = None
    depth: int = 0
    sort_key: str = ""
    is_expandable: bool = False
    is_expanded: bool = True


# ═══════════════════════════════════════════════════════════════════
# Matrix Cell
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2MatrixCell:
    # Coordinates
    row_id: str = ""
    column_id: str = ""

    # Identity (from Cell Contract)
    metric_id: str = ""
    label: str = ""
    slice_id: Optional[str] = None
    slice_label: Optional[str] = None

    # Value
    value: Optional[float] = None
    formatted_value: str = "—"
    unit: str = ""

    # Source
    source_system: str = ""
    source_table: str = ""
    grain: str = "day"

    # Period
    period: str = ""
    period_status: str = "CURRENT"

    # Trust
    canonical_ready: bool = False
    coverage_pct: float = 0.0
    freshness: str = ""
    confidence: str = "MEDIUM"  # HIGH | MEDIUM | LOW
    is_estimated: bool = False

    # Warnings
    warning_codes: List[str] = field(default_factory=list)

    # Lineage
    lineage_refs: Dict[str, Any] = field(default_factory=dict)

    # Comparison (only in compare mode)
    comparison_status: Optional[str] = None  # MATCH | MINOR_DELTA | MAJOR_DELTA | NOT_COMPARABLE
    delta_value: Optional[float] = None
    delta_pct: Optional[float] = None

    # Aggregate Status
    cell_status: str = "OK"  # OK | WARNING | BLOCKED | NOT_COMPARABLE


# ═══════════════════════════════════════════════════════════════════
# Matrix Metadata
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2MatrixMetadata:
    source_status: str = ""  # CURRENT_BASELINE | FUTURE_CANDIDATE | DEPRECATED
    source_table: str = ""
    coverage_pct: float = 0.0
    freshness: str = ""
    data_date: str = ""
    refreshed_at: str = ""
    row_count: int = 0
    column_count: int = 0
    cell_count: int = 0
    comparable: bool = False
    comparison_basis: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# Matrix Warning
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2MatrixWarning:
    code: str = ""
    message: str = ""
    severity: str = "warning"  # info | warning | critical
    target_row_id: Optional[str] = None
    target_column_id: Optional[str] = None
    affected_cell_count: int = 0


# ═══════════════════════════════════════════════════════════════════
# Matrix Lineage Entry
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2MatrixLineage:
    metric_id: str = ""
    origin_table: str = ""
    origin_field: str = ""
    aggregation: str = "SUM"
    filters_applied: Dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════
# Matrix Response
# ═══════════════════════════════════════════════════════════════════

@dataclass
class OmniviewV2MatrixResponse:
    matrix_id: str = "ov2_main"
    source_system: str = ""
    canonical_ready: bool = False
    grain: str = "day"
    period_range: Dict[str, str] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    metadata: OmniviewV2MatrixMetadata = field(default_factory=OmniviewV2MatrixMetadata)
    columns: List[OmniviewV2MatrixColumn] = field(default_factory=list)
    rows: List[OmniviewV2MatrixRow] = field(default_factory=list)
    cells: List[OmniviewV2MatrixCell] = field(default_factory=list)
    warnings: List[OmniviewV2MatrixWarning] = field(default_factory=list)
    lineage: List[OmniviewV2MatrixLineage] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return _serialize(self)


# ═══════════════════════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════════════════════

def _serialize(obj: Any) -> Any:
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
            result[f_name] = _serialize(val)
        return result
    return str(obj)
