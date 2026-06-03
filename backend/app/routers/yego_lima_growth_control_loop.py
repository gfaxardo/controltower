"""
YEGO Lima Growth — Control Loop Router (Fases 2C, 2C.1).

Endpoints:
  POST /yego-lima-growth/control-loop/build-actionable-lists
  POST /yego-lima-growth/control-loop/close-unmanaged-items
  GET  /yego-lima-growth/control-loop/actionable-list
  POST /yego-lima-growth/control-loop/actions
  PATCH /yego-lima-growth/control-loop/actions/{action_id}/status
  POST /yego-lima-growth/control-loop/build-daily-impact
  GET  /yego-lima-growth/control-loop/agent-performance-summary
  GET  /yego-lima-growth/control-loop/driver-impact-timeline/{driver_profile_id}

  Fase 2C.1 — Segment Migration + List Outcomes:
  POST /yego-lima-growth/control-loop/build-segment-transitions
  POST /yego-lima-growth/control-loop/build-list-outcomes
  GET  /yego-lima-growth/control-loop/transition-summary
  GET  /yego-lima-growth/control-loop/movement-matrix
  GET  /yego-lima-growth/control-loop/list-outcome-summary
  GET  /yego-lima-growth/control-loop/driver-transition-timeline/{driver_id}
  GET  /yego-lima-growth/control-loop/agent-movement-summary
  GET  /yego-lima-growth/control-loop/campaign-movement-summary
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.services.yego_lima_actionable_list_service import (
    build_daily_actionable_lists,
    close_unmanaged_items,
    get_daily_actionable_list,
)
from app.services.yego_lima_action_registry_service import (
    create_action,
    confirm_action,
    update_action_status,
    list_actions,
)
from app.services.yego_lima_action_impact_service import (
    build_daily_impact_for_date,
    summarize_agent_performance,
    get_driver_impact_timeline,
)
from app.services.yego_lima_segment_migration_service import (
    build_segment_transitions,
    get_transition_summary,
    get_movement_matrix,
    get_driver_transition_timeline,
    get_movements_by_agent,
    get_movements_by_campaign,
)
from app.services.yego_lima_list_outcome_service import (
    build_list_outcomes,
    get_list_outcome_summary,
)
from app.services.yego_lima_impact_attribution_service import (
    build_daily_attribution,
    get_attribution_summary,
    get_attribution_by_scope,
    get_top_performing,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/control-loop",
    tags=["yego-lima-growth-control-loop"],
)

# ── Pydantic models ──

class ListDateRequest(BaseModel):
    list_date: str = Field(..., description="Date YYYY-MM-DD")

class ImpactDateRequest(BaseModel):
    impact_date: str = Field(..., description="Date YYYY-MM-DD")

class CreateActionRequest(BaseModel):
    driver_profile_id: str = Field(...)
    list_date: Optional[str] = None
    list_type: Optional[str] = None
    source_segment_snapshot_date: str = Field(...)
    action_date: str = Field(...)
    action_type: str = Field(...)
    action_channel: Optional[str] = None
    action_owner: Optional[str] = None
    action_status: str = Field(default="attempted")
    action_confirmed: bool = False
    confirmation_source: Optional[str] = None
    action_reason: Optional[str] = None
    campaign_code: Optional[str] = None
    notes: Optional[str] = None

class UpdateStatusRequest(BaseModel):
    action_status: str = Field(...)
    action_confirmed: bool = False


# ── Endpoints ──

@router.post("/build-actionable-lists")
async def build_actionable_lists(payload: ListDateRequest):
    return build_daily_actionable_lists(payload.list_date)


@router.post("/close-unmanaged-items")
async def close_unmanaged(payload: ListDateRequest):
    return close_unmanaged_items(payload.list_date)


@router.get("/actionable-list")
async def actionable_list(
    list_date: Optional[str] = Query(None),
    list_type: Optional[str] = Query(None),
    management_status: Optional[str] = Query(None),
    assigned_agent: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    return get_daily_actionable_list(list_date, list_type, management_status, assigned_agent, limit)


@router.post("/actions")
async def create_action_endpoint(payload: CreateActionRequest):
    return create_action(
        driver_profile_id=payload.driver_profile_id,
        action_date_str=payload.action_date,
        action_type=payload.action_type,
        source_segment_snapshot_date=payload.source_segment_snapshot_date,
        list_date=payload.list_date,
        list_type=payload.list_type,
        action_channel=payload.action_channel,
        action_owner=payload.action_owner,
        action_status=payload.action_status,
        action_confirmed=payload.action_confirmed,
        confirmation_source=payload.confirmation_source,
        action_reason=payload.action_reason,
        campaign_code=payload.campaign_code,
        notes=payload.notes,
    )


@router.patch("/actions/{action_id}/status")
async def update_action_status_endpoint(action_id: str, payload: UpdateStatusRequest):
    return update_action_status(action_id, payload.action_status, payload.action_confirmed)


@router.post("/build-daily-impact")
async def build_daily_impact(payload: ImpactDateRequest):
    return build_daily_impact_for_date(payload.impact_date)


@router.get("/agent-performance-summary")
async def agent_performance(
    date_from: str = Query(...),
    date_to: str = Query(...),
    action_owner: Optional[str] = Query(None),
):
    return summarize_agent_performance(date_from, date_to, action_owner)


@router.get("/driver-impact-timeline/{driver_profile_id}")
async def driver_impact_timeline(driver_profile_id: str, limit: int = Query(30, ge=1, le=100)):
    return get_driver_impact_timeline(driver_profile_id, limit)


# ── Fase 2C.1 — Segment Migration + List Outcomes ──

class TransitionDateRequest(BaseModel):
    transition_date: str = Field(..., description="Date YYYY-MM-DD")


@router.post("/build-segment-transitions")
async def build_transitions(payload: TransitionDateRequest):
    return build_segment_transitions(payload.transition_date)


@router.post("/build-list-outcomes")
async def build_outcomes(payload: ListDateRequest):
    return build_list_outcomes(payload.list_date)


@router.get("/transition-summary")
async def transition_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    segment_level_2: Optional[str] = Query(None),
    movement_direction: Optional[str] = Query(None),
    action_owner: Optional[str] = Query(None),
    campaign_code: Optional[str] = Query(None),
):
    return get_transition_summary(date_from, date_to, segment_level_2, movement_direction, action_owner, campaign_code)


@router.get("/movement-matrix")
async def movement_matrix(
    date_from: str = Query(...),
    date_to: str = Query(...),
    level: str = Query("3", regex="^[123]$"),
):
    return get_movement_matrix(date_from, date_to, level)


@router.get("/list-outcome-summary")
async def list_outcome_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    list_type: Optional[str] = Query(None),
):
    return get_list_outcome_summary(date_from, date_to, list_type)


@router.get("/driver-transition-timeline/{driver_profile_id}")
async def driver_transition_timeline(driver_profile_id: str, limit: int = Query(30, ge=1, le=100)):
    return get_driver_transition_timeline(driver_profile_id, limit)


@router.get("/agent-movement-summary")
async def agent_movement_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
):
    return get_movements_by_agent(date_from, date_to)


@router.get("/campaign-movement-summary")
async def campaign_movement_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
):
    return get_movements_by_campaign(date_from, date_to)


# ── Fase 2C.2 — Impact Attribution ──

class AttributionDateRequest(BaseModel):
    attribution_date: str = Field(..., description="Date YYYY-MM-DD")


@router.post("/build-impact-attribution")
async def build_attribution(payload: AttributionDateRequest):
    return build_daily_attribution(payload.attribution_date)


@router.get("/attribution-summary")
async def attribution_summary(
    date_from: str = Query(...),
    date_to: str = Query(...),
    scope: Optional[str] = Query(None),
):
    return get_attribution_summary(date_from, date_to, scope)


@router.get("/attribution-agents")
async def attribution_agents(
    date_from: str = Query(...),
    date_to: str = Query(...),
):
    return get_attribution_by_scope(date_from, date_to, "AGENT")


@router.get("/attribution-campaigns")
async def attribution_campaigns(
    date_from: str = Query(...),
    date_to: str = Query(...),
):
    return get_attribution_by_scope(date_from, date_to, "CAMPAIGN")


@router.get("/attribution-segments")
async def attribution_segments(
    date_from: str = Query(...),
    date_to: str = Query(...),
):
    return get_attribution_by_scope(date_from, date_to, "SEGMENT")


@router.get("/attribution-action-types")
async def attribution_action_types(
    date_from: str = Query(...),
    date_to: str = Query(...),
):
    return get_attribution_by_scope(date_from, date_to, "ACTION_TYPE")


@router.get("/attribution-channels")
async def attribution_channels(
    date_from: str = Query(...),
    date_to: str = Query(...),
):
    return get_attribution_by_scope(date_from, date_to, "ACTION_CHANNEL")


@router.get("/top-performing-agents")
async def top_performing_agents(
    date_from: str = Query(...),
    date_to: str = Query(...),
    metric: str = Query("improvement_rate"),
    limit: int = Query(10, ge=1, le=50),
):
    return get_top_performing(date_from, date_to, "AGENT", metric, limit)


@router.get("/top-performing-campaigns")
async def top_performing_campaigns(
    date_from: str = Query(...),
    date_to: str = Query(...),
    metric: str = Query("improvement_rate"),
    limit: int = Query(10, ge=1, le=50),
):
    return get_top_performing(date_from, date_to, "CAMPAIGN", metric, limit)
