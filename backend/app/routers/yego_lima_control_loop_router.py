"""YEGO Lima Growth — Control Loop Router (LG-CTRL-1.0A)"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_control_loop_service import (
    get_control_loop_summary, get_agent_summary, get_stale_drivers, get_driver_control_loop
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/control-loop", tags=["yego-lima-growth-control-loop"])

@router.get("/summary")
async def cl_summary(date: str = Query(None)):
    return get_control_loop_summary(date)

@router.get("/agents")
async def cl_agents():
    return get_agent_summary()

@router.get("/stale")
async def cl_stale(limit: int = Query(20, ge=1, le=100)):
    return get_stale_drivers(limit)

@router.get("/driver/{driver_id}")
async def cl_driver(driver_id: str):
    return get_driver_control_loop(driver_id)
