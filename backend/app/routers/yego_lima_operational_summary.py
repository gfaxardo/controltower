"""
YEGO Lima Growth — Operational Summary + Driver State (LG-C1.4-P0).
"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_operational_summary_service import get_operational_summary
from app.services.yego_lima_driver_state_summary_service import get_driver_state_summary
from app.services.yego_lima_queue_summary_service import get_queue_summary

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth",
    tags=["yego-lima-growth-operational-summary"],
)


@router.get("/operational-summary")
async def operational_summary(date: str = Query(..., description="YYYY-MM-DD")):
    return get_operational_summary(date)


@router.get("/driver-state/summary")
async def driver_state_summary(date: str = Query(..., description="YYYY-MM-DD")):
    return get_driver_state_summary(date)


@router.get("/assignment-queue/summary")
async def queue_summary(date: str = Query(..., description="YYYY-MM-DD")):
    return get_queue_summary(date)
