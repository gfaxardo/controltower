"""
YEGO Lima Growth — Executive Metrics Router (Fase 2D.0).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.services.yego_lima_executive_metrics_service import (
    executive_summary, executive_segments, executive_movements,
    executive_actions, executive_agents, executive_campaigns, executive_freshness,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yego-lima-growth/executive", tags=["yego-lima-growth-executive"])


@router.get("/summary")
async def exec_summary(date: Optional[str] = Query(None)):
    return executive_summary(date)


@router.get("/segments")
async def exec_segments(date: Optional[str] = Query(None)):
    return executive_segments(date)


@router.get("/movements")
async def exec_movements(date_from: str = Query(...), date_to: str = Query(...)):
    return executive_movements(date_from, date_to)


@router.get("/actions")
async def exec_actions(date: Optional[str] = Query(None)):
    return executive_actions(date)


@router.get("/agents")
async def exec_agents(date_from: str = Query(...), date_to: str = Query(...)):
    return executive_agents(date_from, date_to)


@router.get("/campaigns")
async def exec_campaigns(date_from: str = Query(...), date_to: str = Query(...)):
    return executive_campaigns(date_from, date_to)


@router.get("/freshness")
async def exec_freshness():
    return executive_freshness()
