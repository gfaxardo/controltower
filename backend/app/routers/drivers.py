"""
Drivers Router — D2 + D3 + D4 + D5
Control Foundation: Identity + Activity + Lifecycle + Actionable Supply + Workflow
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.driver_raw_freshness_service import get_raw_freshness_map
from app.services.driver_identity_service import search_driver_identities, get_driver_identity
from app.services.driver_activity_service import search_driver_activity, compute_driver_activity
from app.services.driver_lifecycle_service import (
    classify_lifecycle_from_identity, compute_lifecycle_summary,
)
from app.services.driver_actionable_supply_service import (
    generate_actionable_list, generate_actionable_summary,
)
from app.services.driver_workflow_service import (
    create_workflow_schema, assign_workflow, update_workflow_status,
    log_action, get_workflow, list_workflows, get_accountability_metrics,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drivers", tags=["drivers-foundation"])

# Ensure workflow tables exist on first request
try:
    create_workflow_schema()
except Exception as e:
    logger.warning("Workflow schema creation deferred: %s", e)


# ─── Pydantic models for workflow ────────────────────────────────────────────

class WorkflowAssignBody(BaseModel):
    driver_id: str
    queue_type: str
    assigned_owner: str


class WorkflowActionBody(BaseModel):
    workflow_id: str
    action_type: str
    action_note: str = ""
    action_result: str = ""
    action_channel: str = "manual"


class WorkflowStatusBody(BaseModel):
    workflow_id: str
    workflow_status: str


# ─── D2: Identity & Freshness ───────────────────────────────────────────────

@router.get("/raw-freshness")
async def raw_freshness():
    return JSONResponse(content=get_raw_freshness_map())


@router.get("/identity")
async def driver_identity(
    driver_id: Optional[str] = Query(None), country: Optional[str] = Query(None),
    city: Optional[str] = Query(None), park_id: Optional[str] = Query(None),
    has_phone: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
):
    results = search_driver_identities(
        driver_id=driver_id, country=country, city=city,
        park_id=park_id, has_phone=has_phone, limit=limit, offset=offset,
    )
    return JSONResponse(content={"total": len(results), "limit": limit, "offset": offset, "drivers": results})


@router.get("/identity/{driver_id}")
async def driver_identity_detail(driver_id: str):
    return JSONResponse(content=get_driver_identity(driver_id))


# ─── D3: Activity & Lifecycle ────────────────────────────────────────────────

@router.get("/activity-summary")
async def activity_summary(
    driver_id: Optional[str] = Query(None), country: Optional[str] = Query(None),
    city: Optional[str] = Query(None), park_id: Optional[str] = Query(None),
    lifecycle_stage: Optional[str] = Query(None), activity_trend: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
):
    results = search_driver_activity(
        driver_id=driver_id, country=country, city=city, park_id=park_id,
        lifecycle_stage=lifecycle_stage, activity_trend=activity_trend,
        limit=limit, offset=offset,
    )
    return JSONResponse(content={"total": len(results), "limit": limit, "offset": offset, "drivers": results})


@router.get("/lifecycle-summary")
async def lifecycle_summary(
    country: Optional[str] = Query(None), city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
):
    return JSONResponse(content=compute_lifecycle_summary(country=country, city=city, park_id=park_id))


@router.get("/lifecycle/{driver_id}")
async def driver_lifecycle(driver_id: str):
    identity = get_driver_identity(driver_id)
    return JSONResponse(content=classify_lifecycle_from_identity(driver_id, identity))


# ─── D4: Actionable Supply ───────────────────────────────────────────────────

@router.get("/actionable-list")
async def actionable_list(
    queue_type: Optional[str] = Query(None),
    queue_priority: Optional[str] = Query(None),
    lifecycle_stage: Optional[str] = Query(None),
    country: Optional[str] = Query(None), city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None), has_phone: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
):
    return JSONResponse(content=generate_actionable_list(
        queue_type=queue_type, queue_priority=queue_priority,
        lifecycle_stage=lifecycle_stage, country=country, city=city,
        park_id=park_id, has_phone=has_phone, limit=limit, offset=offset,
    ))


@router.get("/actionable-summary")
async def actionable_summary(
    country: Optional[str] = Query(None), city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
):
    return JSONResponse(content=generate_actionable_summary(country=country, city=city, park_id=park_id))


# ─── D5: Workflow & Execution ────────────────────────────────────────────────

@router.post("/workflow/assign")
async def workflow_assign(body: WorkflowAssignBody):
    result = assign_workflow(body.driver_id, body.queue_type, body.assigned_owner)
    return JSONResponse(content=result or {"error": "assignment_failed"})


@router.post("/workflow/action")
async def workflow_action(body: WorkflowActionBody):
    result = log_action(
        body.workflow_id, "", body.action_type,
        body.action_note, body.action_result, body.action_channel,
        actor=body.action_type or "operator",
    )
    return JSONResponse(content=result or {"error": "action_log_failed"})


@router.post("/workflow/status")
async def workflow_status(body: WorkflowStatusBody):
    result = update_workflow_status(body.workflow_id, body.workflow_status)
    if result and "error" in result:
        return JSONResponse(content=result, status_code=400)
    return JSONResponse(content=result or {"error": "status_update_failed"})


@router.get("/workflow")
async def workflow_list(
    owner: Optional[str] = Query(None), status: Optional[str] = Query(None),
    queue_type: Optional[str] = Query(None), driver_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
):
    results = list_workflows(owner=owner, status=status, queue_type=queue_type,
                             driver_id=driver_id, limit=limit, offset=offset)
    return JSONResponse(content={"total": len(results), "workflows": results})


@router.get("/workflow/{workflow_id}")
async def workflow_detail(workflow_id: str):
    result = get_workflow(workflow_id)
    return JSONResponse(content=result or {"error": "not_found"})


@router.get("/workflow-metrics")
async def workflow_metrics():
    return JSONResponse(content=get_accountability_metrics())
