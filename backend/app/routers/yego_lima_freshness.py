"""
YEGO Lima Growth — Data Freshness Router (Fase 4B E2E).

Read-only observability endpoints:
- GET /freshness/status
- GET /freshness/health
- GET /freshness/summary
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.services.yego_lima_freshness_service import (
    get_freshness_status,
    get_health,
    get_summary,
    validate_post_cutover_continuity,
    get_hourly_snapshots,
    build_hourly_snapshot,
    validate_incremental_strategy,
    estimate_refresh_capacity,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/freshness",
    tags=["yego-lima-growth-freshness"],
)


@router.get("/status")
async def freshness_status():
    return get_freshness_status()


@router.get("/health")
async def freshness_health():
    return get_health()


@router.get("/summary")
async def freshness_summary():
    return get_summary()


@router.get("/post-cutover-audit")
async def post_cutover_audit():
    return validate_post_cutover_continuity()


@router.get("/hourly-snapshots")
async def hourly_snapshots(limit: int = Query(24, ge=1, le=168)):
    return get_hourly_snapshots(limit)


@router.get("/incremental-validation")
async def incremental_validation():
    return validate_incremental_strategy()


@router.get("/refresh-capacity")
async def refresh_capacity():
    return estimate_refresh_capacity()
