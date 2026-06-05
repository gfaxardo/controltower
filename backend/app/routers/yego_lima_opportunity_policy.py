"""
YEGO Lima Growth — Opportunity Policy Router (Fase 5B.1).

Policy governance: converts ELIGIBLE into ACTIONABLE TODAY.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.yego_lima_opportunity_policy_service import (
    get_active_policy,
    create_default_policy_if_missing,
    activate_policy,
    build_prioritized_opportunities,
    get_prioritized_opportunities,
    get_policy_quality_summary,
    compare_policy_vs_raw_opportunities,
    close_unmanaged_prioritized_opportunities,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/policy",
    tags=["yego-lima-growth-policy"],
)


class BuildPrioritizedRequest(BaseModel):
    opportunity_date: str
    max_drivers: Optional[int] = None


class CloseUnmanagedRequest(BaseModel):
    opportunity_date: str


@router.get("/active")
async def policy_active():
    return get_active_policy()


@router.post("/default")
async def policy_create_default():
    return create_default_policy_if_missing()


@router.post("/activate/{policy_id}")
async def policy_activate(policy_id: str):
    return activate_policy(policy_id)


@router.post("/build-prioritized-opportunities")
async def policy_build_prioritized(payload: BuildPrioritizedRequest):
    return build_prioritized_opportunities(payload.opportunity_date, payload.max_drivers)


@router.get("/prioritized-opportunities")
async def policy_get_prioritized(
    opportunity_date: str = Query(..., description="Date YYYY-MM-DD"),
    program_code: Optional[str] = Query(None),
    is_actionable_today: Optional[bool] = Query(None),
    productivity_bucket: Optional[str] = Query(None),
    value_tier: Optional[str] = Query(None),
    risk_tier: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
):
    return get_prioritized_opportunities(
        opportunity_date, program_code, is_actionable_today,
        productivity_bucket, value_tier, risk_tier, limit,
    )


@router.get("/quality-summary")
async def policy_quality_summary(opportunity_date: str = Query(...)):
    return get_policy_quality_summary(opportunity_date)


@router.get("/compare-raw-vs-prioritized")
async def policy_compare(opportunity_date: str = Query(...)):
    return compare_policy_vs_raw_opportunities(opportunity_date)


@router.post("/close-unmanaged")
async def policy_close_unmanaged(payload: CloseUnmanagedRequest):
    return close_unmanaged_prioritized_opportunities(payload.opportunity_date)
