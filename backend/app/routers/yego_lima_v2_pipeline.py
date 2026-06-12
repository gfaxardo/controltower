"""
LG-SCH-2A — Lima Growth V2 Daily Pipeline Router

Shadow mode endpoints. Read-only status + protected manual run.
No cutover. No production impact.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.services.yego_lima_v2_daily_pipeline_service import (
    run_lima_growth_v2_daily_pipeline,
    get_v2_pipeline_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/v2-pipeline",
    tags=["yego-lima-growth-v2-pipeline"],
)


@router.get("/status")
async def v2_pipeline_status():
    return get_v2_pipeline_status()


@router.post("/run")
async def v2_pipeline_run(
    date: str = Query(..., description="Target date YYYY-MM-DD"),
    triggered_by: Optional[str] = Query("manual", description="Trigger source"),
):
    result = run_lima_growth_v2_daily_pipeline(
        target_date=date,
        triggered_by=triggered_by,
    )
    return result
