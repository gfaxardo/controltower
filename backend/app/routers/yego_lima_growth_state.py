"""
YEGO Lima Growth — State-Based Loyalty Router (Fase 2D-R).

Endpoints:
  POST /yego-lima-growth/state/build-driver-states
  GET  /yego-lima-growth/state/summary
  GET  /yego-lima-growth/state/drivers
  GET  /yego-lima-growth/state/driver/{driver_profile_id}

  POST /yego-lima-growth/programs/build-eligibility
  GET  /yego-lima-growth/programs/summary
  GET  /yego-lima-growth/programs/drivers

  POST /yego-lima-growth/opportunities/build-daily
  POST /yego-lima-growth/opportunities/close-unmanaged
  GET  /yego-lima-growth/opportunities/daily
  POST /yego-lima-growth/opportunities/assign-agent
  POST /yego-lima-growth/opportunities/link-action
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.yego_lima_driver_state_service import (
    build_driver_state_snapshot,
    get_state_summary,
    get_drivers_by_state,
    get_driver_state,
)
from app.services.yego_lima_program_eligibility_service import (
    build_program_eligibility,
    get_program_summary,
    get_program_drivers,
)
from app.services.yego_lima_daily_opportunity_service import (
    build_daily_opportunity_lists,
    close_unmanaged_opportunities,
    get_daily_opportunities,
    assign_agent,
    link_action,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yego-lima-growth", tags=["yego-lima-growth-state"])


# ── Pydantic models ──

class BuildDriverStatesRequest(BaseModel):
    snapshot_date: str = Field(..., description="Date YYYY-MM-DD")


class BuildEligibilityRequest(BaseModel):
    eligibility_date: str = Field(..., description="Date YYYY-MM-DD")


class BuildOpportunitiesRequest(BaseModel):
    opportunity_date: str = Field(..., description="Date YYYY-MM-DD")


class CloseUnmanagedRequest(BaseModel):
    opportunity_date: str = Field(..., description="Date YYYY-MM-DD")


class AssignAgentRequest(BaseModel):
    opportunity_date: str = Field(..., description="Date YYYY-MM-DD")
    driver_profile_id: str = Field(...)
    opportunity_type: str = Field(...)
    agent: str = Field(...)


class LinkActionRequest(BaseModel):
    opportunity_date: str = Field(..., description="Date YYYY-MM-DD")
    driver_profile_id: str = Field(...)
    opportunity_type: str = Field(...)
    action_id: str = Field(...)
    management_status: str = Field(default="ACTION_CONFIRMED")


# ── Driver State Endpoints ──

@router.post("/state/build-driver-states")
async def build_states(payload: BuildDriverStatesRequest):
    return build_driver_state_snapshot(payload.snapshot_date)


@router.get("/state/summary")
async def state_summary(date: Optional[str] = Query(None)):
    return get_state_summary(date)


@router.get("/state/drivers")
async def state_drivers(
    date: Optional[str] = Query(None),
    lifecycle_state: Optional[str] = Query(None),
    performance_state: Optional[str] = Query(None),
    retention_state: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    return get_drivers_by_state(date, lifecycle_state, performance_state, retention_state, limit)


@router.get("/state/driver/{driver_profile_id}")
async def state_driver(driver_profile_id: str, date: Optional[str] = Query(None)):
    result = get_driver_state(driver_profile_id, date)
    if not result:
        return {"error": "Driver not found", "driver_profile_id": driver_profile_id}
    return result


# ── Program Eligibility Endpoints ──

@router.post("/programs/build-eligibility")
async def build_eligibility(payload: BuildEligibilityRequest):
    return build_program_eligibility(payload.eligibility_date)


@router.get("/programs/summary")
async def program_summary(date: Optional[str] = Query(None)):
    return get_program_summary(date)


@router.get("/programs/drivers")
async def program_drivers(
    date: Optional[str] = Query(None),
    program_code: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    return get_program_drivers(date, program_code, limit)


# ── Daily Opportunity Endpoints ──

@router.post("/opportunities/build-daily")
async def build_opportunities(payload: BuildOpportunitiesRequest):
    return build_daily_opportunity_lists(payload.opportunity_date)


@router.post("/opportunities/close-unmanaged")
async def close_unmanaged(payload: CloseUnmanagedRequest):
    return close_unmanaged_opportunities(payload.opportunity_date)


@router.get("/opportunities/daily")
async def daily_opportunities(
    opportunity_date: Optional[str] = Query(None),
    opportunity_type: Optional[str] = Query(None),
    management_status: Optional[str] = Query(None),
    assigned_agent: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    return get_daily_opportunities(opportunity_date, opportunity_type, management_status, assigned_agent, limit)


@router.post("/opportunities/assign-agent")
async def assign_agent_endpoint(payload: AssignAgentRequest):
    return assign_agent(payload.opportunity_date, payload.driver_profile_id, payload.opportunity_type, payload.agent)


@router.post("/opportunities/link-action")
async def link_action_endpoint(payload: LinkActionRequest):
    return link_action(payload.opportunity_date, payload.driver_profile_id, payload.opportunity_type,
                       payload.action_id, payload.management_status)
