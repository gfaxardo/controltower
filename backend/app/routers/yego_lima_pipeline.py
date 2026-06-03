"""
YEGO Lima Growth — Daily Pipeline Router (Fase 2D.0).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.yego_lima_daily_pipeline_service import (
    run_daily_pipeline, get_pipeline_status, consistency_check,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yego-lima-growth/pipeline", tags=["yego-lima-growth-pipeline"])


class RunDailyRequest(BaseModel):
    run_date: str = Field(..., description="Date YYYY-MM-DD")
    max_drivers: int = Field(250, ge=10, le=5000)
    include_warm: bool = False
    dry_run: bool = False
    requested_by: Optional[str] = None


@router.post("/run-daily")
async def run_daily(payload: RunDailyRequest):
    return run_daily_pipeline(
        payload.run_date, payload.max_drivers,
        payload.include_warm, payload.dry_run, payload.requested_by,
    )


@router.get("/status")
async def pipeline_status(date: Optional[str] = Query(None)):
    return get_pipeline_status(date)


@router.get("/consistency-check")
async def consistency(date: Optional[str] = Query(None)):
    return consistency_check(date)
