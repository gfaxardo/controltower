"""YEGO Lima Growth — Governance Router (LG-OEF-2_3_4A)"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_governance_service import (
    get_program_registry, get_daily_runs, get_freshness_status, get_health_status
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/governance", tags=["yego-lima-growth-governance"])

@router.get("/programs")
async def program_registry():
    return get_program_registry()

@router.get("/daily-runs")
async def daily_runs(limit: int = Query(10, ge=1, le=50)):
    return get_daily_runs(limit)

@router.get("/freshness")
async def freshness():
    return get_freshness_status()

@router.get("/health")
async def health():
    return get_health_status()
