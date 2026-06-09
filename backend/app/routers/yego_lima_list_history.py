"""
YEGO Lima Growth — Driver List History Router (LG-INFRA-R1.5)
"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_driver_list_history_service import (
    snapshot_queue_to_history,
    get_driver_list_history,
    get_history_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/list-history",
    tags=["yego-lima-growth-list-history"],
)


@router.get("/summary")
async def list_history_summary(date: str = Query(..., description="Action date (YYYY-MM-DD)")):
    return get_history_summary(date)


@router.get("")
async def list_history_query(
    date: str = Query(None, description="Action date"),
    driver: str = Query(None, description="Driver profile ID"),
    program: str = Query(None, description="Program code"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return get_driver_list_history(
        action_date=date,
        driver_profile_id=driver,
        program_code=program,
        limit=limit,
        offset=offset,
    )


@router.post("/snapshot")
async def list_history_snapshot(
    date: str = Query(..., description="Action date (YYYY-MM-DD)"),
    run_id: str = Query(None),
):
    return snapshot_queue_to_history(date, source_run_id=run_id)
