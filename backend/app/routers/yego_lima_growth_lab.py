"""
YEGO Lima Fleet Growth Tower — API Lab Router (Fases 0, 1, 2B, 2B-R0).

Endpoints:
  GET  /yego-lima-growth/lab/health
  POST /yego-lima-growth/lab/test-orders-connection
  POST /yego-lima-growth/lab/capture-orders-range
  GET  /yego-lima-growth/lab/raw-orders-summary
  GET  /yego-lima-growth/lab/recent-raw-orders

  Fase 2B — Loyalty Sub-50:
  POST /yego-lima-growth/lab/build-loyalty-sub50
  GET  /yego-lima-growth/lab/loyalty-sub50-summary
  GET  /yego-lima-growth/lab/loyalty-sub50-top-opportunities
  GET  /yego-lima-growth/lab/loyalty-sub50-supply-opportunities

  Fase 2B-R0 — Historical Bootstrap:
  POST /yego-lima-growth/lab/bootstrap-history
  GET  /yego-lima-growth/lab/history-summary
  GET  /yego-lima-growth/lab/history-sample
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.settings import settings
from app.integrations.yango_api_client import test_orders_connection
from app.services.yego_lima_growth_capture_service import capture_orders_range
from app.services.yego_lima_loyalty_sub50_service import (
    build_loyalty_sub50,
    get_sub50_summary,
    get_top_opportunities,
    get_supply_opportunities,
    get_recoverable,
)
from app.services.yego_lima_growth_history_service import (
    bootstrap_history,
    history_summary,
    history_sample,
)
from app.services.yego_lima_driver_segmentation_service import (
    build_driver_segments,
    get_segments_summary,
    get_segments_distribution,
    get_top_opportunities as get_seg_top_opportunities,
    get_recoverable_list,
    get_churn_risk,
    get_14_90,
)
from app.repositories.yego_lima_growth_repository import (
    get_raw_orders_summary,
    get_recent_raw_orders,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/lab",
    tags=["yego-lima-growth-lab"],
)

# ── Pydantic models ──

class CaptureOrdersRangeRequest(BaseModel):
    from_: str = Field(..., alias="from", description="ISO 8601 start datetime in America/Lima")
    to: str = Field(..., description="ISO 8601 end datetime in America/Lima")
    max_pages: int = Field(20, ge=1, le=50, description="Max pages to fetch")


class BuildLoyaltySub50Request(BaseModel):
    week_start_date: str = Field(..., description="Week start date (YYYY-MM-DD), e.g. 2026-06-01")
    target_weekly_trips: Optional[int] = Field(None, ge=1, le=200, description="Optional target override, defaults to LIMA_GROWTH_WEEKLY_TRIPS_TARGET")


class BootstrapHistoryRequest(BaseModel):
    from_date: str = Field(..., description="Start date YYYY-MM-DD")
    to_date: str = Field(..., description="End date YYYY-MM-DD")


class BuildDriverSegmentsRequest(BaseModel):
    snapshot_date: str = Field(..., description="Snapshot date YYYY-MM-DD, e.g. 2026-06-02")


# ── Endpoints ──

@router.get("/health")
async def health():
    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()

    has_client_id = bool(client_id)
    has_api_key = bool(api_key)
    has_lima_park_id = bool(park_id)
    enabled = bool(settings.YANGO_API_ENABLED)
    ready = enabled and has_client_id and has_api_key and has_lima_park_id

    return {
        "module": "yego_lima_growth_lab",
        "enabled": enabled,
        "base_url": settings.YANGO_API_BASE_URL,
        "has_client_id": has_client_id,
        "has_api_key": has_api_key,
        "has_lima_park_id": has_lima_park_id,
        "ready": ready,
    }


@router.post("/test-orders-connection")
async def test_orders():
    result = await test_orders_connection()
    return result


@router.post("/capture-orders-range")
async def capture_orders(payload: CaptureOrdersRangeRequest):
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )

    result = await capture_orders_range(
        from_str=payload.from_,
        to_str=payload.to,
        max_pages=payload.max_pages,
    )
    return result


@router.get("/raw-orders-summary")
async def raw_orders_summary():
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )
    return get_raw_orders_summary()


@router.get("/recent-raw-orders")
async def recent_raw_orders(limit: int = Query(20, ge=1, le=100)):
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )
    return get_recent_raw_orders(limit=limit)


# ── Fase 2B — Loyalty Sub-50 ──

@router.post("/build-loyalty-sub50")
async def build_loyalty_sub50_endpoint(payload: BuildLoyaltySub50Request):
    result = build_loyalty_sub50(payload.week_start_date, payload.target_weekly_trips)
    return result


@router.get("/loyalty-sub50-summary")
async def loyalty_sub50_summary(week_start_date: Optional[str] = Query(None, description="Week start date YYYY-MM-DD")):
    result = get_sub50_summary(week_start_date)
    return result


@router.get("/loyalty-sub50-top-opportunities")
async def loyalty_sub50_top_opportunities(
    week_start_date: Optional[str] = Query(None, description="Week start date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_top_opportunities(week_start_date, limit=limit)
    return result


@router.get("/loyalty-sub50-supply-opportunities")
async def loyalty_sub50_supply_opportunities(
    week_start_date: Optional[str] = Query(None, description="Week start date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_supply_opportunities(week_start_date, limit=limit)
    return result


# ── Fase 2B-R0 — Historical Bootstrap ──

@router.post("/bootstrap-history")
async def bootstrap_history_endpoint(payload: BootstrapHistoryRequest):
    result = bootstrap_history(payload.from_date, payload.to_date)
    return result


@router.get("/history-summary")
async def history_summary_endpoint():
    result = history_summary()
    return result


@router.get("/history-sample")
async def history_sample_endpoint(limit: int = Query(20, ge=1, le=100)):
    result = history_sample(limit=limit)
    return result


@router.get("/loyalty-sub50-recoverable")
async def loyalty_sub50_recoverable(
    week_start_date: Optional[str] = Query(None, description="Week start date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_recoverable(week_start_date, limit=limit)
    return result


# ── Fase 2B-R2 — Unified Driver Segmentation ──

@router.post("/build-driver-segments")
async def build_driver_segments_endpoint(payload: BuildDriverSegmentsRequest):
    result = build_driver_segments(payload.snapshot_date)
    return result


@router.get("/driver-segments-summary")
async def driver_segments_summary(snapshot_date: Optional[str] = Query(None, description="Snapshot date YYYY-MM-DD")):
    result = get_segments_summary(snapshot_date)
    return result


@router.get("/driver-segments-distribution")
async def driver_segments_distribution(snapshot_date: Optional[str] = Query(None)):
    result = get_segments_distribution(snapshot_date)
    return result


@router.get("/driver-segments-top-opportunities")
async def driver_segments_top_opportunities(
    snapshot_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_seg_top_opportunities(snapshot_date, limit)
    return result


@router.get("/driver-segments-recoverable")
async def driver_segments_recoverable(
    snapshot_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_recoverable_list(snapshot_date, limit)
    return result


@router.get("/driver-segments-churn-risk")
async def driver_segments_churn_risk(
    snapshot_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_churn_risk(snapshot_date, limit)
    return result


@router.get("/driver-segments-14-90")
async def driver_segments_14_90(
    snapshot_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_14_90(snapshot_date, limit)
    return result
