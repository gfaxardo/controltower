"""
Omniview V2 Matrix View Model Service — transforms raw source data into
the unified MatrixResponse contract.

Uses:
- omniview_v2_matrix_repository.py (raw data queries)
- omniview_v2_matrix_contract.py (MatrixResponse dataclasses)
- omniview_v2_source_registry.py (source definitions)

Rules:
- All cells have row_id + column_id
- All cells have full CellContract
- Frontend does no business calculation
- null is never silently converted to 0
- YANGO_API_RAW canonical_ready=false
- source_table visible
- Basic lineage required
"""
from __future__ import annotations

import logging
from datetime import date as dt_date
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.contracts.omniview_v2_matrix_contract import (
    OmniviewV2MatrixCell,
    OmniviewV2MatrixColumn,
    OmniviewV2MatrixLineage,
    OmniviewV2MatrixMetadata,
    OmniviewV2MatrixResponse,
    OmniviewV2MatrixRow,
    OmniviewV2MatrixWarning,
)
from app.repositories.omniview_v2_matrix_repository import get_matrix_data
from app.services.omniview_v2_source_registry import (
    YANGO_API_RAW,
    SourceDefinition,
    get_source,
)

logger = logging.getLogger(__name__)

DAY_MS = 86400000


def _fmt_count(v: Any) -> str:
    if v is None:
        return "\u2014"
    try:
        return f"{int(v):,}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_pen(v: Any) -> str:
    if v is None:
        return "\u2014"
    try:
        return f"{float(v):,.2f}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "\u2014"
    try:
        return f"{float(v):.1f}%"
    except (ValueError, TypeError):
        return str(v)


# ═══════════════════════════════════════════════════════════════════
# Column Builder
# ═══════════════════════════════════════════════════════════════════

def build_columns(
    grain: str,
    date_from: str,
    date_to: str,
    period_dates: Optional[List[str]] = None,
) -> List[OmniviewV2MatrixColumn]:
    columns = []

    if period_dates:
        periods = period_dates
    else:
        try:
            f = dt_date.fromisoformat(date_from) if date_from else dt_date.today()
            t = dt_date.fromisoformat(date_to) if date_to else dt_date.today()
            days = max((t - f).days, 0)
            periods = [(f + timedelta(days=i)).isoformat() for i in range(days + 1)]
        except (ValueError, TypeError):
            periods = []

    today_str = dt_date.today().isoformat()

    for period_str in periods:
        is_future = period_str > today_str
        is_current = period_str == today_str

        label = period_str
        try:
            d = dt_date.fromisoformat(period_str)
            if grain == "day":
                label = d.strftime("%b %d")
            elif grain == "week":
                label = f"W{d.isocalendar()[1]}"
            elif grain == "month":
                label = d.strftime("%b %Y")
            elif grain == "hour":
                label = d.strftime("%H:%M")
        except (ValueError, TypeError):
            pass

        columns.append(OmniviewV2MatrixColumn(
            id=f"col_{period_str}",
            label=label,
            grain=grain,
            period=period_str,
            period_status="FUTURE" if is_future else "CURRENT" if is_current else "PARTIAL",
            sort_key=period_str,
            is_current=is_current,
            is_future=is_future,
        ))

    return columns


# ═══════════════════════════════════════════════════════════════════
# Row Builder
# ═══════════════════════════════════════════════════════════════════

def build_rows(
    raw_data: List[Dict[str, Any]],
    source_system: str,
) -> List[OmniviewV2MatrixRow]:
    if source_system == "CT_TRIPS_2026":
        slice_names = sorted(set(r.get("business_slice_name", "") for r in raw_data if r.get("business_slice_name")))
        return [
            OmniviewV2MatrixRow(
                id=f"row_{s.lower().replace(' ', '_')}",
                label=s,
                row_type="slice",
                row_status="OK",
                depth=0,
                sort_key=f"{i:02d}_{s}",
            )
            for i, s in enumerate(slice_names)
        ]

    if source_system == "YANGO_API_RAW":
        return [
            OmniviewV2MatrixRow(
                id="row_lima_fleet",
                label="Lima Fleet",
                row_type="slice",
                row_status="WARNING",
                depth=0,
                sort_key="00_lima_fleet",
            )
        ]

    return []


# ═══════════════════════════════════════════════════════════════════
# Cell Builder
# ═══════════════════════════════════════════════════════════════════

def _cell_status(value: Optional[float], is_future: bool, canonical_ready: bool) -> str:
    if is_future:
        return "NOT_COMPARABLE"
    if value is None:
        return "BLOCKED"
    if not canonical_ready:
        return "WARNING"
    return "OK"


def build_cells(
    raw_data: List[Dict[str, Any]],
    rows: List[OmniviewV2MatrixRow],
    columns: List[OmniviewV2MatrixColumn],
    source_system: str,
    grain: str,
    metric_id: str = "orders",
) -> List[OmniviewV2MatrixCell]:
    src_def = get_source(source_system)
    canonical_ready = src_def.canonical_ready if src_def else False
    source_table = src_def.get_grain(grain).table_name if src_def and src_def.get_grain(grain) else ""

    metric_map = {
        "orders": ("orders", "Orders Completed", "count", "trips_completed", _fmt_count),
        "revenue": ("revenue", "Revenue", "PEN", "revenue_yego_final", _fmt_pen),
        "active_drivers": ("active_drivers", "Active Drivers", "count", "active_drivers", _fmt_count),
        "avg_ticket": ("avg_ticket", "Average Ticket", "PEN", "avg_ticket", _fmt_pen),
        "trips_per_driver": ("trips_per_driver", "Trips per Driver", "ratio", "trips_per_driver", lambda v: f"{v:.2f}" if v is not None else "\u2014"),
    }
    yango_metric_map = {
        "orders": ("orders", "Orders Completed", "count", "orders_completed", _fmt_count),
        "revenue": ("revenue", "Revenue Partner Fee", "PEN", "revenue_partner_fee_amount", _fmt_pen),
        "active_drivers": ("active_drivers", "Active Drivers", "count", "unique_drivers", _fmt_count),
        "revenue_per_order": ("revenue_per_order", "Revenue per Order", "PEN", "revenue_per_order", _fmt_pen),
        "trips_per_driver": ("trips_per_driver", "Trips per Driver", "ratio", None, lambda v: "\u2014"),
    }

    mm = metric_map if source_system == "CT_TRIPS_2026" else yango_metric_map
    if metric_id not in mm:
        metric_id = "orders"
    mid, label, unit, field, formatter = mm[metric_id]

    cells = []

    for row in rows:
        for col in columns:
            raw_row = None

            if source_system == "CT_TRIPS_2026":
                raw_row = next(
                    (r for r in raw_data
                     if _serialize(r.get("period_date")) == col.period
                     and r.get("business_slice_name", "") == row.label),
                    None,
                )
            elif source_system == "YANGO_API_RAW":
                raw_row = next(
                    (r for r in raw_data
                     if _serialize(r.get("period_date")) == col.period),
                    None,
                )

            raw_val = None
            if raw_row and field:
                raw_val = raw_row.get(field)
                if raw_val is not None:
                    try:
                        if unit in ("count",):
                            raw_val = int(raw_val)
                        else:
                            raw_val = float(raw_val)
                    except (ValueError, TypeError):
                        raw_val = None

            cells.append(OmniviewV2MatrixCell(
                row_id=row.id,
                column_id=col.id,
                metric_id=mid,
                label=label,
                value=raw_val,
                formatted_value=formatter(raw_val),
                unit=unit,
                source_system=source_system,
                source_table=source_table,
                grain=grain,
                period=col.period,
                period_status=col.period_status,
                canonical_ready=canonical_ready,
                coverage_pct=100.0 if raw_val is not None else 0.0,
                freshness="",
                confidence="HIGH" if source_system == "CT_TRIPS_2026" else "MEDIUM",
                is_estimated=False,
                cell_status=_cell_status(raw_val, col.is_future, canonical_ready),
                lineage_refs={
                    "origin_table": source_table,
                    "origin_field": field or "",
                    "aggregation": "SUM",
                    "filters_applied": {},
                },
            ))

    return cells


# ═══════════════════════════════════════════════════════════════════
# Warnings & Lineage
# ═══════════════════════════════════════════════════════════════════

def build_warnings(
    source_system: str,
    grain: str,
    status: str,
    rows_count: int,
) -> List[OmniviewV2MatrixWarning]:
    warnings = []

    if status == "NOT_SUPPORTED":
        warnings.append(OmniviewV2MatrixWarning(
            code="GRAIN_NOT_SUPPORTED",
            message=f"Grain '{grain}' is not supported for source '{source_system}'.",
            severity="warning",
        ))

    if status == "NO_DATA":
        warnings.append(OmniviewV2MatrixWarning(
            code="NO_DATA",
            message="No data available for the selected period.",
            severity="warning",
        ))

    if source_system == "YANGO_API_RAW":
        warnings.append(OmniviewV2MatrixWarning(
            code="CANONICAL_NOT_READY",
            message="Source YANGO_API_RAW is NOT certified for operational decisions.",
            severity="critical",
        ))

    if rows_count == 0 and status not in ("NOT_SUPPORTED", "NO_DATA"):
        warnings.append(OmniviewV2MatrixWarning(
            code="EMPTY_MATRIX",
            message="Matrix has no rows. Check source and filters.",
            severity="warning",
        ))

    return warnings


def build_lineage(source_system: str, grain: str) -> List[OmniviewV2MatrixLineage]:
    src_def = get_source(source_system)
    if not src_def:
        return []

    table = src_def.get_grain(grain).table_name if src_def.get_grain(grain) else ""
    entries = []
    for metric in src_def.metrics[:6]:
        entries.append(OmniviewV2MatrixLineage(
            metric_id=metric.metric_id,
            origin_table=table,
            origin_field=metric.source_field,
            aggregation=metric.aggregation,
        ))
    return entries


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _serialize(obj: Any) -> str:
    if obj is None:
        return ""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


# ═══════════════════════════════════════════════════════════════════
# Main: build_matrix_response
# ═══════════════════════════════════════════════════════════════════

def build_matrix_response(
    source_system: str = "CT_TRIPS_2026",
    grain: str = "day",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    metric_id: str = "orders",
) -> OmniviewV2MatrixResponse:
    src_def = get_source(source_system)
    if not src_def:
        return OmniviewV2MatrixResponse(
            matrix_id="ov2_matrix",
            source_system=source_system,
            canonical_ready=False,
            grain=grain,
            warnings=[OmniviewV2MatrixWarning(code="UNKNOWN_SOURCE", message=f"Source '{source_system}' not registered.", severity="critical")],
        )

    canonical_ready = src_def.canonical_ready
    status, raw_data = get_matrix_data(source_system, grain, date_from, date_to, filters)

    if status == "NOT_SUPPORTED":
        return OmniviewV2MatrixResponse(
            matrix_id="ov2_matrix",
            source_system=source_system,
            canonical_ready=canonical_ready,
            grain=grain,
            period_range={"from": date_from or "", "to": date_to or ""},
            filters=filters or {},
            warnings=build_warnings(source_system, grain, status, 0),
            lineage=build_lineage(source_system, grain),
        )

    period_dates = sorted(set(
        _serialize(r.get("period_date")) for r in raw_data if r.get("period_date")
    ))

    columns = build_columns(grain, date_from or "", date_to or "", period_dates or None)
    rows = build_rows(raw_data, source_system)
    cells = build_cells(raw_data, rows, columns, source_system, grain, metric_id)

    metadata = OmniviewV2MatrixMetadata(
        source_status=src_def.status,
        source_table=src_def.get_grain(grain).table_name if src_def.get_grain(grain) else "",
        coverage_pct=100.0 if raw_data else 0.0,
        data_date=period_dates[-1] if period_dates else "",
        row_count=len(rows),
        column_count=len(columns),
        cell_count=len(cells),
        comparable=source_system == "CT_TRIPS_2026",
    )

    warnings = build_warnings(source_system, grain, status, len(rows))

    return OmniviewV2MatrixResponse(
        matrix_id="ov2_matrix",
        source_system=source_system,
        canonical_ready=canonical_ready,
        grain=grain,
        period_range={"from": date_from or "", "to": date_to or ""},
        filters=filters or {},
        metadata=metadata,
        columns=columns,
        rows=rows,
        cells=cells,
        warnings=warnings,
        lineage=build_lineage(source_system, grain),
    )
