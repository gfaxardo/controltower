"""
Yego Pro Profitability — Fleet Project API
Prefix: /fleet-project/yego-pro/profitability

Phase 1 Foundation: read-only serving layer for historical profitability.
Control Foundation (serving layer). No forecast/suggestion/decision/action.

Park: 64085dd85e124e2c808806f70d527ea8 (Lima)
"""
from typing import Optional

from fastapi import APIRouter, Query

from app.services.yego_pro_profitability_service import (
    get_overview,
    get_weekly,
    get_daily,
    get_drivers,
    get_vehicles,
    get_shifts,
    get_input_mapping,
    get_quality,
    PARK_ID,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fleet-project/yego-pro/profitability",
    tags=["yego-pro-profitability"],
)


@router.get("/overview")
def overview(
    park_id: str = Query(default=PARK_ID, description="Park ID (default: Yego Lima)"),
):
    """
    Overview KPIs: last 30 days trips + last closed billing week.
    Returns structured KPIs with source, metric_type, confidence metadata.
    """
    return get_overview(park_id=park_id)


@router.get("/weekly")
def weekly(
    park_id: str = Query(default=PARK_ID),
    weeks: int = Query(default=12, ge=1, le=52, description="Number of weeks to return"),
):
    """
    Weekly profitability from module_weekly_billing.
    Each row includes: revenue, costs, profit, productivity metrics.
    """
    return get_weekly(park_id=park_id, weeks=weeks)


@router.get("/daily")
def daily(
    park_id: str = Query(default=PARK_ID),
    days: int = Query(default=30, ge=1, le=90, description="Number of days to return"),
):
    """
    Daily profitability from trips_2026 (operational only, no financial).
    Includes day/night shift split per day.
    """
    return get_daily(park_id=park_id, days=days)


@router.get("/drivers")
def drivers(
    park_id: str = Query(default=PARK_ID),
    week_start: Optional[str] = Query(default=None, description="ISO date of week start (default: latest)"),
):
    """
    Driver-level profitability for a given week.
    Source: module_weekly_billing joined with drivers master.
    """
    return get_drivers(park_id=park_id, week_start=week_start)


@router.get("/vehicles")
def vehicles(
    park_id: str = Query(default=PARK_ID),
):
    """
    Vehicle fleet configuration and quota structure.
    LIMITED: no vehicle-to-driver assignment exists.
    """
    return get_vehicles(park_id=park_id)


@router.get("/shifts")
def shifts(
    park_id: str = Query(default=PARK_ID),
    weeks: int = Query(default=8, ge=1, le=26),
):
    """
    Day vs Night shift profitability (weekly aggregation).
    Source: trips_2026 with EXTRACT(HOUR) classification.
    """
    return get_shifts(park_id=park_id, weeks=weeks)


@router.get("/input-mapping")
def input_mapping(
    park_id: str = Query(default=PARK_ID),
):
    """
    Input mapping: REAL / ASSUMPTION / NOT_AVAILABLE inputs.
    Includes payment tiers and configurable parameters.
    """
    return get_input_mapping(park_id=park_id)


@router.get("/quality")
def quality(
    park_id: str = Query(default=PARK_ID),
):
    """
    Data quality check: serving view existence, freshness, row counts.
    Returns overall health status for the profitability module.
    """
    return get_quality(park_id=park_id)
