"""
YEGO Lima Growth — Intraday Signals Router (LG-INFRA-R1.3)
"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_intraday_signal_service import (
    build_intraday_signals,
    get_signal_summary,
    get_signals_by_campaign,
    get_signals_by_program,
    get_signals_list,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/intraday-signals",
    tags=["yego-lima-growth-intraday-signals"],
)


@router.get("/summary")
async def intraday_signal_summary(date: str = Query(..., description="Action date (YYYY-MM-DD)")):
    return get_signal_summary(date)


@router.get("/by-campaign")
async def intraday_signal_by_campaign(date: str = Query(..., description="Action date (YYYY-MM-DD)")):
    return {
        "signal_date": date,
        "campaigns": get_signals_by_campaign(date),
    }


@router.get("/by-program")
async def intraday_signal_by_program(date: str = Query(..., description="Action date (YYYY-MM-DD)")):
    return {
        "signal_date": date,
        "programs": get_signals_by_program(date),
    }


@router.get("")
async def intraday_signal_list(
    date: str = Query(..., description="Action date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: str = Query(None, description="Filter by signal_status"),
):
    return get_signals_list(date, limit=limit, offset=offset, signal_status=status)


@router.post("/build")
async def intraday_signal_build(date: str = Query(..., description="Action date (YYYY-MM-DD)")):
    """
    Admin/dev only. Build intraday signals for a given action date.
    Reads active actions from assignment_queue, checks Yango live activity,
    and upserts observation signals.
    """
    result = build_intraday_signals(date)
    return result
