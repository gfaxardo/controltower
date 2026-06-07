"""
Omniview V2 Router — source-agnostic backend API (parallel to V1).

Endpoints:
- GET /ops/omniview-v2/sources     — list registered sources
- GET /ops/omniview-v2/summary     — KPIs from a single source
- GET /ops/omniview-v2/health      — health check for all sources
- GET /ops/omniview-v2/compare     — side-by-side source comparison

Rules:
- canonical_ready must be explicit in every response.
- source_system must be explicit in every request (defaults to CT_TRIPS_2026).
- YANGO_API_RAW always has canonical_ready=false.
- Never mixes sources silently.
- No UI connection yet.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.omniview_v2_core_service import (
    get_omniview_v2_health,
    get_omniview_v2_summary,
    get_source_comparison,
)
from app.services.omniview_v2_source_registry import get_supported_sources
from app.services.omniview_v2_matrix_view_model_service import build_matrix_response
from app.services.omniview_v2_snapshot_service import get_served_payload
from app.services.omniview_v2_plan_real_service import build_monthly_plan_real_matrix
from app.repositories.omniview_v2_plan_real_repository import get_plan_versions

router = APIRouter(prefix="/ops/omniview-v2", tags=["omniview_v2"])


@router.get("/sources")
def list_sources():
    """List all registered data sources with their status and capabilities."""
    return {
        "sources": get_supported_sources(),
        "default_source": "CT_TRIPS_2026",
    }


@router.get("/summary")
def get_summary(
    source_system: str = Query(default="CT_TRIPS_2026", description="Source system: CT_TRIPS_2026 | YANGO_API_RAW"),
    grain: str = Query(default="day", description="Time grain: hour | day | week | month"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
):
    """Get KPIs for a source/grain combination."""
    filters = {"country": country, "city": city}
    if source_system == "YANGO_API_RAW":
        filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}

    response = get_omniview_v2_summary(
        source_system=source_system,
        grain=grain,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
    )
    return response.to_dict()


@router.get("/health")
def get_health():
    """Health status for all registered Omniview V2 sources."""
    return get_omniview_v2_health()


@router.get("/compare")
def compare_sources(
    source_a: str = Query(default="CT_TRIPS_2026", description="First source system"),
    source_b: str = Query(default="YANGO_API_RAW", description="Second source system"),
    grain: str = Query(default="day"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """Compare two sources side-by-side at the same grain."""
    response = get_source_comparison(
        source_a=source_a,
        source_b=source_b,
        grain=grain,
        date_from=date_from,
        date_to=date_to,
    )
    return response.to_dict()


@router.get("/matrix")
def get_matrix(
    source_system: str = Query(default="CT_TRIPS_2026"),
    grain: str = Query(default="day"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
    allow_runtime: bool = Query(default=False),
    metric_id: str = Query(default="orders"),
):
    """Get MatrixResponse. Snapshot-first. No runtime without explicit flag."""
    # Single-day: try snapshot first
    if date_from and date_from == date_to:
        from app.services.omniview_v2_snapshot_service import get_served_payload
        snap = get_served_payload(source_system, grain, date_from, "matrix")
        if snap and snap.get("cells"):
            return snap

    # Multi-day ranges: allow runtime (matrix is fast ~750ms)
    if date_from and date_from != date_to:
        filters = {"country": country, "city": city}
        if source_system == "YANGO_API_RAW":
            filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}
        response = build_matrix_response(
            source_system=source_system, grain=grain,
            date_from=date_from, date_to=date_to,
            filters=filters, metric_id=metric_id,
        )
        return response.to_dict()

    # Single-day, no snapshot, allow_runtime NOT set → fast SERVING_SNAPSHOT_MISSING
    if not allow_runtime:
        from app.contracts.omniview_v2_matrix_contract import OmniviewV2MatrixResponse, OmniviewV2MatrixWarning
        return OmniviewV2MatrixResponse(
            matrix_id="ov2_matrix",
            source_system=source_system,
            canonical_ready=source_system != "YANGO_API_RAW",
            grain=grain,
            warnings=[OmniviewV2MatrixWarning(
                code="SERVING_SNAPSHOT_MISSING",
                message=f"No serving snapshot for {source_system}/{grain}/{date_from}. Refresh snapshots or use allow_runtime=true.",
                severity="warning",
            )],
        ).to_dict()

    # Single-day with allow_runtime=true: proceed but will be slow
    filters = {"country": country, "city": city}
    if source_system == "YANGO_API_RAW":
        filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}
    response = build_matrix_response(
        source_system=source_system, grain=grain,
        date_from=date_from, date_to=date_to,
        filters=filters, metric_id=metric_id,
    )
    return response.to_dict()


@router.get("/operating-date")
def get_operating_date(
    source_system: str = Query(default="CT_TRIPS_2026"),
):
    """Get the latest closed date with data and current processing status. <500ms"""
    from app.db.connection import get_db
    from datetime import date as dt_date

    default_date = dt_date.today().isoformat()
    latest_closed = None
    max_available = None
    has_today_data = False

    try:
        with get_db() as conn:
            cur = conn.cursor()
            if source_system == "CT_TRIPS_2026":
                cur.execute(
                    "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact "
                    "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"
                )
                row = cur.fetchone()
                if row and row[0]:
                    max_available = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
                    latest_closed = max_available

                today_str = dt_date.today().isoformat()
                cur.execute(
                    "SELECT COUNT(*) FROM ops.real_business_slice_day_fact "
                    "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' AND trip_date=%s",
                    (today_str,),
                )
                has_today_data = (cur.fetchone()[0] or 0) > 0

            elif source_system == "YANGO_API_RAW":
                cur.execute(
                    "SELECT MAX(order_date) FROM raw_yango.mv_orders_day "
                    "WHERE park_id='08e20910d81d42658d4334d3f6d10ac0'"
                )
                row = cur.fetchone()
                if row and row[0]:
                    max_available = row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
                    latest_closed = max_available

            cur.close()
    except Exception:
        pass

    if latest_closed:
        default_date = latest_closed

    return {
        "latest_closed_date": latest_closed,
        "current_processing_date": dt_date.today().isoformat(),
        "max_available_date": max_available,
        "has_today_data": has_today_data,
        "default_date": default_date,
        "source_system": source_system,
        "freshness_status": "STALE" if not has_today_data and max_available and max_available < dt_date.today().isoformat() else "FRESH",
    }


@router.get("/plan-real/monthly")
def get_plan_real_monthly(
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    metric_id: str = Query(default="trips"),
    plan_version: str = Query(default=None),
):
    """Monthly Plan vs Real matrix."""
    response = build_monthly_plan_real_matrix(
        country=country, city=city,
        date_from=date_from, date_to=date_to,
        metric_id=metric_id, plan_version=plan_version,
    )
    return response.to_dict()


@router.get("/plan-real/versions")
def get_plan_real_versions():
    """List available plan versions."""
    return {"versions": get_plan_versions()}
