"""YEGO Lima Growth — Result Sync Router (LG-C2.0)"""
import logging
from fastapi import APIRouter, Query, Body
from typing import Any, Dict, List, Optional
from app.services.yego_lima_result_sync_service import sync_results, get_result_summary, get_result_records

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/loopcontrol/results", tags=["yego-lima-growth-result-sync"])

@router.post("/sync")
async def results_sync(payload: Dict[str, Any] = Body(...)):
    return sync_results(payload)

@router.get("/summary")
async def results_summary(campaign_id_external: str = Query(..., description="Campaign external ID")):
    return get_result_summary(campaign_id_external)

@router.get("")
async def results_records(
    campaign_id_external: str = Query(..., description="Campaign external ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return get_result_records(campaign_id_external, limit=limit, offset=offset)
