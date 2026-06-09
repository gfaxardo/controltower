"""YEGO Lima Growth — Diagnostic Trace Router (LG-DIAG-R1.4A)"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_diagnostic_trace_service import (
    get_driver_diagnostic_trace, get_program_traces, get_transition_traces
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/diagnostic-trace", tags=["yego-lima-growth-diagnostic-trace"])

@router.get("/{driver_id}")
async def driver_diagnostic(driver_id: str):
    return get_driver_diagnostic_trace(driver_id)

@router.get("/program/list")
async def program_traces(
    driver_id: str = Query(None), snapshot_date: str = Query(None),
    selected_program: str = Query(None), run_id: str = Query(None),
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
):
    return get_program_traces(driver_id, snapshot_date, selected_program, run_id, limit, offset)

@router.get("/transition/list")
async def transition_traces(
    driver_id: str = Query(None), snapshot_before: str = Query(None),
    snapshot_after: str = Query(None), run_id: str = Query(None),
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
):
    return get_transition_traces(driver_id, snapshot_before, snapshot_after, run_id, limit, offset)
