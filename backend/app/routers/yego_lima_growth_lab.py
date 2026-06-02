"""
YEGO Lima Fleet Growth Tower — API Lab Router (Fases 0 y 1).

Endpoints:
  GET  /yego-lima-growth/lab/health
  POST /yego-lima-growth/lab/test-orders-connection
  POST /yego-lima-growth/lab/capture-orders-range
  GET  /yego-lima-growth/lab/raw-orders-summary
  GET  /yego-lima-growth/lab/recent-raw-orders
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.settings import settings
from app.integrations.yango_api_client import test_orders_connection
from app.services.yego_lima_growth_capture_service import capture_orders_range
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
