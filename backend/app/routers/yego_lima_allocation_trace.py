"""
YEGO Lima Growth — Capacity Allocation Trace Router. Serving-first (R2.9H.1).
"""
import logging
import time
from fastapi import APIRouter, Query
from app.services.yego_lima_allocation_trace_service import get_allocation_trace
from app.services.yego_lima_serving_facts_service import serving_or_missing, audit_force_refresh

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/capacity",
    tags=["yego-lima-growth-allocation-trace"],
)


@router.get("/allocation-trace")
async def allocation_trace(date: str = Query(..., description="YYYY-MM-DD"),
                            force_refresh: bool = Query(False)):
    result = serving_or_missing(date, "allocation_trace", force_refresh)
    if result["payload"] is not None:
        return result["payload"]
    if force_refresh and result["source"] == "RUNTIME_FORCE_REFRESH":
        t0 = time.time()
        data = get_allocation_trace(date)
        elapsed = int((time.time() - t0) * 1000)
        audit_force_refresh("capacity/allocation-trace", "allocation_trace", date, "RUNTIME_FORCE_REFRESH", elapsed)
        return data
    return result
