"""
YEGO Lima Growth — Productivity Governance Router (Fase 4A).

Read-only endpoints:
- GET /productivity/daily
- GET /productivity/weekly
- GET /productivity/monthly
- GET /productivity/supply-vs-production
- GET /productivity/distribution
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

from app.services.yego_lima_productivity_service import (
    get_daily_productivity,
    get_weekly_productivity,
    get_monthly_productivity,
    get_supply_vs_production,
    get_trip_distribution,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/productivity",
    tags=["yego-lima-growth-productivity"],
)


@router.get("/daily")
async def productivity_daily(date: str = Query(..., description="Date YYYY-MM-DD")):
    return get_daily_productivity(date)


@router.get("/weekly")
async def productivity_weekly(
    iso_year: int = Query(..., ge=2025, le=2030, description="ISO year"),
    iso_week: int = Query(..., ge=1, le=53, description="ISO week number"),
):
    return get_weekly_productivity(iso_year, iso_week)


@router.get("/monthly")
async def productivity_monthly(
    year: int = Query(..., ge=2025, le=2030, description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month number"),
):
    return get_monthly_productivity(year, month)


@router.get("/supply-vs-production")
async def productivity_supply_vs_production(
    date: str = Query(..., description="Date YYYY-MM-DD"),
):
    return get_supply_vs_production(date)


@router.get("/distribution")
async def productivity_distribution(
    grain: str = Query(..., description="Grain: daily, weekly, or monthly"),
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD (for daily grain)"),
    iso_year: Optional[int] = Query(None, ge=2025, le=2030, description="ISO year (for weekly grain)"),
    iso_week: Optional[int] = Query(None, ge=1, le=53, description="ISO week number (for weekly grain)"),
    year: Optional[int] = Query(None, ge=2025, le=2030, description="Year (for monthly grain)"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month number (for monthly grain)"),
):
    kwargs = {}
    if date:
        kwargs["date"] = date
    if iso_year is not None:
        kwargs["iso_year"] = iso_year
    if iso_week is not None:
        kwargs["iso_week"] = iso_week
    if year is not None:
        kwargs["year"] = year
    if month is not None:
        kwargs["month"] = month
    return get_trip_distribution(grain, **kwargs)
