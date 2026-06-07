"""
YEGO Lima Growth — Scheduler Router (LG-R2.9I.2)
"""
import logging
from fastapi import APIRouter
from app.services.yego_lima_scheduler_service import (
    get_scheduler_status, start_scheduler, stop_scheduler, scheduler_tick,
    run_daily_closed_pipeline, run_live_monitoring,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/scheduler",
    tags=["yego-lima-growth-scheduler"],
)


@router.get("/status")
async def scheduler_status():
    return get_scheduler_status()


@router.post("/start")
async def scheduler_start():
    return start_scheduler()


@router.post("/stop")
async def scheduler_stop():
    return stop_scheduler()


@router.post("/tick")
async def scheduler_tick_endpoint():
    return run_live_monitoring()


@router.post("/run-daily-closed")
async def scheduler_daily_closed(date: str = Query(None)):
    return run_daily_closed_pipeline(date)


@router.post("/run-live-monitoring")
async def scheduler_live_monitoring():
    return run_live_monitoring()
