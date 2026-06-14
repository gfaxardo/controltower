"""YEGO Lima Growth — Exclusive Worklist Export Router (LG-PROG-EXCL-1D)

Read-only endpoints for exclusive driver worklist daily serving fact.
CSV export + Control Loop preview. No Control Loop DB writes.
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.yego_lima_exclusive_worklist_service import (
    get_exclusive_worklist_summary,
    get_exclusive_worklist_rows,
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/yego-lima-growth/exclusive-worklist",
    tags=["yego-lima-growth-exclusive-worklist"],
)

RECOMMENDED_ACTION = {
    "NEW_REACTIVATED_0_14_TO_50": "ONBOARDING_PUSH",
    "RAMP_UP_15_45_TO_100W": "PRODUCTIVITY_RAMP",
    "CONSOLIDATION_46_90_TO_100W": "CONSOLIDATION_PUSH",
    "ACTIVE_GROWTH_90_PLUS_BAND_UP": "BAND_GROWTH",
    "RECOVERY_RECENT_INACTIVE_HIGH_VALUE": "HIGH_VALUE_RECOVERY",
    "RECOVERY_RECENT_INACTIVE_LOW_VALUE": "LOW_VALUE_RECOVERY",
    "CEMETERY_LONG_CHURNED": "DO_NOT_EXPORT",
    "PROTECTED_ALREADY_MEETING_GOAL": "DO_NOT_EXPORT",
    "NO_DATA_OR_NO_ACTION": "DO_NOT_EXPORT",
}

DO_NOT_EXPORT = {"CEMETERY_LONG_CHURNED", "PROTECTED_ALREADY_MEETING_GOAL", "NO_DATA_OR_NO_ACTION"}


@router.get("/summary")
async def exclusive_worklist_summary(
    generated_date: Optional[str] = Query(None, description="Date to query. Default: latest."),
    exportable_only: bool = Query(False, description="Only count exportable drivers."),
):
    result = get_exclusive_worklist_summary(generated_date)
    if not result.get("ok", True):
        return result

    total = result.get("total_drivers", 0)
    exp = result.get("exportable_drivers", 0)
    return {
        "resolved_generated_date": result.get("resolved_generated_date"),
        "total_drivers": total if not exportable_only else exp,
        "exportable_drivers": exp,
        "non_exportable_drivers": max(0, total - exp),
        "by_universe": result.get("by_universe", []),
    }


@router.get("/rows")
async def exclusive_worklist_rows(
    generated_date: Optional[str] = Query(None, description="Date. Default: latest."),
    assigned_universe_v1: Optional[str] = Query(None, description="Filter by universe."),
    exportable_only: bool = Query(False, description="Exclude Cemetery + Protected."),
    limit: int = Query(100, ge=1, le=5000, description="Max rows."),
    offset: int = Query(0, ge=0, description="Offset."),
    search: Optional[str] = Query(None, description="Partial match on driver_id or driver_profile_id."),
):
    # If exportable_only, automatically exclude DO_NOT_EXPORT universes
    universe_filter = assigned_universe_v1
    if exportable_only and not universe_filter:
        pass  # handled by the service filtering below

    result = get_exclusive_worklist_rows(
        generated_date=generated_date,
        assigned_universe=None,  # fetch all, filter in memory for exportable_only
        exportable_only=False,
        limit=10000,  # fetch enough to filter
        offset=0,
    )

    if not result.get("ok", True):
        return result

    rows = result.get("rows", [])
    filtered = []
    for r in rows:
        if exportable_only and r.get("assigned_universe_v1") in DO_NOT_EXPORT:
            continue
        if universe_filter and r.get("assigned_universe_v1") != universe_filter:
            continue
        if search:
            did = str(r.get("driver_profile_id", ""))
            drname = str(r.get("driver_id", ""))
            if search.lower() not in did.lower() and search.lower() not in drname.lower():
                continue
        filtered.append(r)

    total = len(filtered)
    page = filtered[offset:offset + limit]

    return {
        "resolved_generated_date": result.get("resolved_generated_date"),
        "total": total,
        "limit": limit,
        "offset": offset,
        "rows": page,
    }


CSV_HEADERS = [
    "generated_date", "driver_profile_id", "driver_id", "assigned_universe_v1",
    "assigned_program_v1", "subsegment", "objective", "reason_code", "priority_rank",
    "operational_age_days", "weekly_trips", "activation_window_trips", "inactivity_days",
    "value_tier", "productivity_band", "trend", "target_metric", "baseline_metric",
    "export_to_control_loop",
]

CL_PREVIEW_HEADERS = [
    "driver_profile_id", "assigned_universe_v1", "assigned_program_v1",
    "objective", "reason_code", "priority_rank", "recommended_action_category",
    "target_metric", "baseline_metric", "generated_date",
    "would_export_to_control_loop", "initial_control_loop_status",
]


def _build_csv_rows(rows, include_cemetery=False):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        uni = r.get("assigned_universe_v1", "")
        if uni == "CEMETERY_LONG_CHURNED" and not include_cemetery:
            continue
        if uni in DO_NOT_EXPORT and uni != "CEMETERY_LONG_CHURNED":
            continue
        row_out = {k: r.get(k, "") for k in CSV_HEADERS}
        writer.writerow(row_out)
    return output.getvalue()


@router.get("/export.csv")
async def exclusive_worklist_export_csv(
    generated_date: Optional[str] = Query(None, description="Date. Default: latest."),
    assigned_universe_v1: Optional[str] = Query(None, description="Filter by universe."),
    exportable_only: bool = Query(True, description="Exclude Cemetery + Protected. Default: true."),
    include_cemetery: bool = Query(False, description="Include Cemetery drivers. Overrides exportable_only."),
):
    from app.services.yego_lima_exclusive_worklist_service import get_exclusive_worklist_rows as fetch_rows

    result = fetch_rows(
        generated_date=generated_date,
        assigned_universe=None,
        exportable_only=False,
        limit=50000,
        offset=0,
    )

    if not result.get("ok", True):
        return result

    rows = result.get("rows", [])
    filtered = []
    for r in rows:
        uni = r.get("assigned_universe_v1", "")
        if include_cemetery:
            pass
        elif exportable_only and uni in DO_NOT_EXPORT:
            continue
        if assigned_universe_v1 and uni != assigned_universe_v1:
            continue
        filtered.append(r)

    csv_content = _build_csv_rows(filtered, include_cemetery=include_cemetery)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="exclusive_worklist_{result.get("resolved_generated_date", "latest")}.csv"'
        },
    )


@router.get("/control-loop-preview")
async def exclusive_worklist_control_loop_preview(
    generated_date: Optional[str] = Query(None, description="Date. Default: latest."),
    assigned_universe_v1: Optional[str] = Query(None, description="Filter by universe."),
    limit: int = Query(1000, ge=1, le=10000, description="Max rows."),
    offset: int = Query(0, ge=0, description="Offset."),
):
    from app.services.yego_lima_exclusive_worklist_service import get_exclusive_worklist_rows as fetch_rows

    result = fetch_rows(
        generated_date=generated_date,
        assigned_universe=None,
        exportable_only=False,
        limit=50000,
        offset=0,
    )

    if not result.get("ok", True):
        return result

    rows = result.get("rows", [])
    preview = []
    for r in rows:
        uni = r.get("assigned_universe_v1", "")
        if uni in DO_NOT_EXPORT:
            continue
        if assigned_universe_v1 and uni != assigned_universe_v1:
            continue
        preview.append({
            "driver_profile_id": r.get("driver_profile_id"),
            "assigned_universe_v1": uni,
            "assigned_program_v1": r.get("assigned_program_v1"),
            "objective": r.get("objective"),
            "reason_code": r.get("reason_code"),
            "priority_rank": r.get("priority_rank"),
            "recommended_action_category": RECOMMENDED_ACTION.get(uni, "UNKNOWN"),
            "target_metric": r.get("target_metric"),
            "baseline_metric": r.get("baseline_metric"),
            "generated_date": r.get("generated_date"),
            "would_export_to_control_loop": True,
            "initial_control_loop_status": "READY",
        })

    total = len(preview)
    page = preview[offset:offset + limit]

    return {
        "resolved_generated_date": result.get("resolved_generated_date"),
        "total_exportable": total,
        "limit": limit,
        "offset": offset,
        "rows": page,
    }
