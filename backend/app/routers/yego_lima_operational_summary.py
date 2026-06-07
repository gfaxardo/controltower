"""
YEGO Lima Growth — Operational Summary + Driver State + Queue Summary (Serving-first, R2.9H.1).
"""
import logging
import time
from fastapi import APIRouter, Query
from app.services.yego_lima_operational_summary_service import get_operational_summary
from app.services.yego_lima_driver_state_summary_service import get_driver_state_summary
from app.services.yego_lima_queue_summary_service import get_queue_summary
from app.services.yego_lima_serving_facts_service import serving_or_missing, audit_force_refresh

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth",
    tags=["yego-lima-growth-operational-summary"],
)


@router.get("/operational-summary")
async def operational_summary(date: str = Query(..., description="YYYY-MM-DD"),
                               force_refresh: bool = Query(False)):
    result = serving_or_missing(date, "operational_summary", force_refresh)
    if result["payload"] is not None:
        return result["payload"]
    if force_refresh and result["source"] == "RUNTIME_FORCE_REFRESH":
        t0 = time.time()
        data = get_operational_summary(date)
        elapsed = int((time.time() - t0) * 1000)
        audit_force_refresh("operational-summary", "operational_summary", date, "RUNTIME_FORCE_REFRESH", elapsed)
        return data
    return result


@router.get("/driver-state/summary")
async def driver_state_summary(date: str = Query(..., description="YYYY-MM-DD"),
                                force_refresh: bool = Query(False)):
    result = serving_or_missing(date, "driver_state_summary", force_refresh)
    if result["payload"] is not None:
        return result["payload"]
    if force_refresh and result["source"] == "RUNTIME_FORCE_REFRESH":
        t0 = time.time()
        data = get_driver_state_summary(date)
        elapsed = int((time.time() - t0) * 1000)
        audit_force_refresh("driver-state/summary", "driver_state_summary", date, "RUNTIME_FORCE_REFRESH", elapsed)
        return data
    return result


@router.get("/assignment-queue/summary")
async def queue_summary(date: str = Query(..., description="YYYY-MM-DD"),
                         force_refresh: bool = Query(False)):
    result = serving_or_missing(date, "queue_summary", force_refresh)
    if result["payload"] is not None:
        return result["payload"]
    if force_refresh and result["source"] == "RUNTIME_FORCE_REFRESH":
        t0 = time.time()
        data = get_queue_summary(date)
        elapsed = int((time.time() - t0) * 1000)
        audit_force_refresh("assignment-queue/summary", "queue_summary", date, "RUNTIME_FORCE_REFRESH", elapsed)
        return data
    return result
