"""
Driver Lifecycle Diagnostic Router — Fase 2A.1

Prefix: /driver-lifecycle
Endpoints: summary, funnel, risk-list, cohorts-basic
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from app.services.driver_lifecycle_diagnostic_service import (
    get_diagnostic_summary,
    get_diagnostic_funnel,
    get_diagnostic_risk_list,
    get_diagnostic_cohorts_basic,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/driver-lifecycle", tags=["driver-lifecycle-diagnostic"])


@router.get("/summary")
async def diagnostic_summary(
    country: Optional[str] = Query(None, description="Country filter (peru, colombia)"),
    city: Optional[str] = Query(None, description="City filter"),
    period_days: int = Query(30, description="Lookback window in days (default 30)"),
):
    """Aggregate diagnostic summary with lifecycle and risk counts."""
    try:
        return get_diagnostic_summary(country=country, city=city, period_days=period_days)
    except Exception as e:
        logger.exception("driver-lifecycle diagnostic summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/funnel")
async def diagnostic_funnel(
    country: Optional[str] = Query(None, description="Country filter"),
    city: Optional[str] = Query(None, description="City filter"),
    period_days: int = Query(30, description="Lookback window in days (default 30)"),
):
    """4-layer funnel: input -> retained -> risk -> leakage."""
    try:
        return get_diagnostic_funnel(country=country, city=city, period_days=period_days)
    except Exception as e:
        logger.exception("driver-lifecycle diagnostic funnel: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-list")
async def diagnostic_risk_list(
    country: Optional[str] = Query(None, description="Country filter"),
    city: Optional[str] = Query(None, description="City filter"),
    risk_level: Optional[str] = Query(None, description="Filter by risk: HIGH, MEDIUM, LOW"),
    lifecycle_state: Optional[str] = Query(None, description="Filter by state: CHURNED, DORMANT, AT_RISK, etc."),
    limit: int = Query(200, description="Max results (default 200)"),
):
    """Actionable list of drivers with lifecycle state and risk level."""
    try:
        return get_diagnostic_risk_list(
            country=country, city=city,
            risk_level=risk_level, lifecycle_state=lifecycle_state,
            limit=limit,
        )
    except Exception as e:
        logger.exception("driver-lifecycle diagnostic risk-list: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cohorts-basic")
async def diagnostic_cohorts_basic(
    country: Optional[str] = Query(None, description="Country filter"),
    city: Optional[str] = Query(None, description="City filter"),
):
    """Basic cohort retention grouped by first_trip_month."""
    try:
        return get_diagnostic_cohorts_basic(country=country, city=city)
    except Exception as e:
        logger.exception("driver-lifecycle diagnostic cohorts-basic: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
