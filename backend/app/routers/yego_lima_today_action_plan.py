"""
YEGO Lima Growth — Today's Action Plan Router. Serving-first (R2.9H.1).
"""
import logging
import time
from fastapi import APIRouter, Query
from app.services.yego_lima_today_action_plan_service import get_today_action_plan
from app.services.yego_lima_serving_facts_service import serving_or_missing, audit_force_refresh

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth",
    tags=["yego-lima-growth-today-action-plan"],
)


@router.get("/today-action-plan")
async def today_action_plan(date: str = Query(..., description="YYYY-MM-DD"),
                             force_refresh: bool = Query(False)):
    result = serving_or_missing(date, "today_action_plan", force_refresh)
    if result["payload"] is not None:
        return result["payload"]
    if force_refresh and result["source"] == "RUNTIME_FORCE_REFRESH":
        t0 = time.time()
        data = get_today_action_plan(date)
        elapsed = int((time.time() - t0) * 1000)
        audit_force_refresh("today-action-plan", "today_action_plan", date, "RUNTIME_FORCE_REFRESH", elapsed)
        return data
    return result
