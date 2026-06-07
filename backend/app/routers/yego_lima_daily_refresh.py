"""
YEGO Lima Growth — Daily Refresh Router (LG-UX-R2.9G.3)
"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_daily_refresh_service import (
    get_refresh_status, run_daily_refresh, get_refresh_history,
    detect_latest_closed_data_date,
)
from app.services.yego_lima_refresh_governance_service import get_governance_status

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/refresh",
    tags=["yego-lima-growth-refresh"],
)


@router.get("/status")
async def refresh_status():
    return get_refresh_status()


@router.post("/run")
async def refresh_run(
    date: str = Query(None, description="Target date YYYY-MM-DD (default: latest)"),
    dry_run: bool = Query(False),
):
    return run_daily_refresh(target_date=date, dry_run=dry_run)


@router.get("/history")
async def refresh_history(limit: int = Query(20)):
    return get_refresh_history(limit)


@router.get("/operational-date")
async def operational_date():
    return detect_latest_closed_data_date()


@router.get("/governance-status")
async def governance_status():
    return get_governance_status()
