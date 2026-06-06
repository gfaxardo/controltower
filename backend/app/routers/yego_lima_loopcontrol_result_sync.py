"""
YEGO Lima Growth — LoopControl Result Sync Router (Fase LC-2A).

LC-2 endpoints (pending Miguel's result endpoint):
  POST /yego-lima-growth/loopcontrol/results/sync
  GET  /yego-lima-growth/loopcontrol/results/summary
  GET  /yego-lima-growth/loopcontrol/results
"""
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.yego_lima_loopcontrol_result_sync_service import (
    sync_campaign_results,
    get_results_summary,
    get_results,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/loopcontrol",
    tags=["yego-lima-growth-loopcontrol-results"],
)


class SyncResultRequest(BaseModel):
    campaign_id_external: int
    calls_made: int = 0
    calls_answered: int = 0
    outcomes: Optional[Dict[str, int]] = None
    synced_by: Optional[str] = None


@router.post("/results/sync")
async def lc_results_sync(payload: SyncResultRequest):
    return sync_campaign_results(
        campaign_id_external=payload.campaign_id_external,
        calls_made=payload.calls_made,
        calls_answered=payload.calls_answered,
        outcomes=payload.outcomes,
        synced_by=payload.synced_by,
    )


@router.get("/results/summary")
async def lc_results_summary(
    campaign_id_external: Optional[int] = Query(None),
):
    return get_results_summary(campaign_id_external=campaign_id_external)


@router.get("/results")
async def lc_results(
    campaign_id_external: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    return get_results(
        campaign_id_external=campaign_id_external,
        limit=limit,
    )
