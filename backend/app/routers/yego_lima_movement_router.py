"""YEGO Lima Growth — Movement Router (LG-ATTR-1.0A)"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_movement_service import (
    get_daily_movement_summary, get_driver_movement_history, get_movement_list
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/movement", tags=["yego-lima-growth-movement"])

@router.get("/summary")
async def movement_summary(date: str = Query(..., description="Snapshot date")):
    return get_daily_movement_summary(date)

@router.get("/driver/{driver_id}")
async def driver_movements(driver_id: str):
    return get_driver_movement_history(driver_id)

@router.get("/list")
async def movement_list(
    date: str = Query(None), driver_id: str = Query(None),
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
):
    return get_movement_list(date, driver_id, limit, offset)
