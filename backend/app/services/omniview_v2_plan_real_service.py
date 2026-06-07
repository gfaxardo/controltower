"""
Omniview V2 Plan vs Real Service — builds MatrixResponse for monthly PvR.
"""
from __future__ import annotations

from datetime import date as dt_date
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.contracts.omniview_v2_matrix_contract import (
    OmniviewV2MatrixCell,
    OmniviewV2MatrixColumn,
    OmniviewV2MatrixMetadata,
    OmniviewV2MatrixResponse,
    OmniviewV2MatrixRow,
)
from app.repositories.omniview_v2_plan_real_repository import (
    get_latest_plan_version,
    get_monthly_plan_real,
    get_plan_versions,
)


def build_monthly_plan_real_matrix(
    country: str = "peru",
    city: str = "lima",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    metric_id: str = "trips",
    plan_version: Optional[str] = None,
) -> OmniviewV2MatrixResponse:
    if not plan_version:
        plan_version = get_latest_plan_version()

    if not date_from:
        date_from = (dt_date.today().replace(day=1) - timedelta(days=180)).isoformat()
    if not date_to:
        date_to = dt_date.today().replace(day=1).isoformat()

    raw = get_monthly_plan_real(country, city, date_from, date_to, metric_id, plan_version)

    # Build columns from unique months
    months = sorted(set(r["period"][:7] for r in raw))
    columns = []
    for m in months:
        d = dt_date.fromisoformat(m + "-01")
        label = d.strftime("%b %Y")
        columns.append(OmniviewV2MatrixColumn(
            id=f"col_{m}",
            label=label,
            grain="month",
            period=m + "-01",
            period_status="CLOSED" if m < dt_date.today().strftime("%Y-%m") else "CURRENT",
            sort_key=m,
            width=110,
            is_current=m == dt_date.today().strftime("%Y-%m"),
            is_future=m > dt_date.today().strftime("%Y-%m"),
        ))

    # Build rows from unique slices
    slices_list = sorted(set(r["business_slice_name"] for r in raw))
    rows = []
    for i, s in enumerate(slices_list):
        rows.append(OmniviewV2MatrixRow(
            id=f"row_{s.lower().replace(' ', '_')}",
            label=s,
            row_type="slice",
            row_status="OK",
            depth=0,
            sort_key=f"{i:02d}_{s}",
        ))

    # Build cells
    cells = []
    metric_labels = {
        "orders": ("Orders", "count"),
        "trips": ("Trips", "count"),
        "revenue": ("Revenue", "PEN"),
        "active_drivers": ("Drivers", "count"),
        "avg_ticket": ("Avg Ticket", "PEN"),
        "trips_per_driver": ("TPD", "ratio"),
    }
    label, unit = metric_labels.get(metric_id, ("Trips", "count"))

    for row in rows:
        for col in columns:
            raw_row = next(
                (r for r in raw
                 if r["period"][:7] == col.sort_key[:7]
                 and r["business_slice_name"] == row.label),
                None,
            )

            if not raw_row:
                cells.append(OmniviewV2MatrixCell(
                    row_id=row.id, column_id=col.id,
                    metric_id=metric_id, label=label,
                    value=None, formatted_value="\u2014", unit=unit,
                    grain="month", period=col.period, period_status=col.period_status,
                    canonical_ready=True, cell_status="BLOCKED",
                    source_system="CT_TRIPS_2026",
                ))
                continue

            plan_v = raw_row["plan_value"]
            real_v = raw_row["real_value"]
            gap_pct = raw_row["gap_pct"]
            status = raw_row["status"]

            if unit == "count":
                display = f"{int(real_v):,}" if real_v is not None else "\u2014"
            elif unit == "PEN":
                display = f"{real_v:,.1f}" if real_v is not None else "\u2014"
            else:
                display = f"{real_v:.2f}" if real_v is not None else "\u2014"

            cell_status = "OK" if status == "ON_TRACK" else "WARNING" if status in ("WATCH", "NO_PLAN") else "BLOCKED" if status in ("OFF_TRACK", "NO_REAL") else "OK"

            cells.append(OmniviewV2MatrixCell(
                row_id=row.id, column_id=col.id,
                metric_id=metric_id, label=label,
                value=real_v, formatted_value=display, unit=unit,
                grain="month", period=col.period, period_status=col.period_status,
                canonical_ready=True,
                coverage_pct=100.0 if real_v is not None else 0.0,
                cell_status=cell_status,
                source_system="CT_TRIPS_2026",
                source_table="ops.plan_trips_monthly + ops.real_business_slice_month_fact",
                comparison_status=status,
                delta_value=raw_row["gap_abs"],
                delta_pct=gap_pct,
                lineage_refs={
                    "plan_table": "ops.plan_trips_monthly",
                    "real_table": "ops.real_business_slice_month_fact",
                    "plan_version": plan_version,
                },
            ))

    return OmniviewV2MatrixResponse(
        matrix_id="ov2_plan_real_monthly",
        source_system="CT_TRIPS_2026",
        canonical_ready=True,
        grain="month",
        period_range={"from": date_from, "to": date_to},
        filters={"country": country, "city": city},
        metadata=OmniviewV2MatrixMetadata(
            source_status="CURRENT_BASELINE",
            source_table="ops.plan_trips_monthly",
            coverage_pct=100.0 if cells else 0.0,
            row_count=len(rows),
            column_count=len(columns),
            cell_count=len(cells),
        ),
        columns=columns,
        rows=rows,
        cells=cells,
        lineage=[],
    )
