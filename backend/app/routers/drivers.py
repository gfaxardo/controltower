"""
Drivers Router — D2 + D3 + D4 + D5 + H1 + H2 + H3.2 + H3.3 + H3.4 + H3.5A
Control Foundation: Identity + Activity + Lifecycle + Actionable Supply + Workflow
H1: Operational Hardening
H2: Real Operations Pilot
H3.2: Campaign Intelligence
H3.3: CRM Bridge
H3.4: Campaign Effectiveness
H3.5A: Supply Selectors + Segment Migration Hotfix
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
    compute_lifecycle_distribution,
)
from app.services.driver_actionable_supply_service import (
    generate_actionable_list, generate_actionable_summary,
)
from app.services.driver_workflow_service import (
    create_workflow_schema, assign_workflow, update_workflow_status,
    log_action, get_workflow, list_workflows, get_accountability_metrics,
)
from app.services.driver_pilot_service import (
    evaluate_pilot_readiness, preview_cohort, create_pilot_cohort,
    assign_pilot_owners, get_pilot_metrics, add_learning_log, get_learning_log,
)
from app.services.driver_campaign_service import (
    preview_campaign, create_campaign, list_campaigns,
    get_campaign_detail, get_campaign_members, ingest_campaign_outcome,
    get_campaign_summary,
)
from app.services.driver_crm_bridge_service import (
    generate_crm_export, import_crm_outcomes, compute_campaign_progress,
    get_sync_health, get_sync_history, check_bridge_health,
)
from app.services.driver_campaign_effectiveness_service import (
    compute_campaign_effectiveness, get_effectiveness_summary,
)
from app.services.driver_operational_loop_service import (
    get_operational_loop_model, get_campaign_loop_status,
    get_campaign_follow_up, get_campaign_qa_checklist, get_operating_board,
)
from app.services.driver_segment_migration_service import compute_segment_migration
from app.services.driver_operational_priority_service import get_actionable_movements
from app.services.driver_serving_freshness_service import check_all_facts, check_fact_freshness
from app.utils.json_sanitizer import sanitize_for_json

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


# ─── H2: Pilot models ─────────────────────────────────────────────────────────

class PilotCohortBody(BaseModel):
    country: str = ""
    city: str = ""
    park_id: str = ""
    queue_types: list[str] = []
    max_drivers: int = 100
    has_phone_only: bool = True


class PilotAssignBody(BaseModel):
    cohort_id: str
    owners: list[str]
    strategy: str = "balanced_by_priority"


class PilotLearningLogBody(BaseModel):
    cohort_id: str = ""
    driver_id: str = ""
    owner: str = ""
    observation_type: str
    observation_note: str = ""


# ─── H3.2: Campaign models ────────────────────────────────────────────────────

class CampaignPreviewBody(BaseModel):
    campaign_name: str = ""
    campaign_type: str = "RECOVERY"
    campaign_objective: str = ""
    source_queue_types: list[str] = []
    country: str = ""
    city: str = ""
    park_id: str = ""
    priority: list[str] = []
    lifecycle_stage: str = ""
    has_phone: bool = True
    max_drivers: int = 1000


class CampaignCreateBody(BaseModel):
    campaign_name: str = ""
    campaign_type: str = "RECOVERY"
    campaign_objective: str = ""
    source_queue_types: list[str] = []
    country: str = ""
    city: str = ""
    park_id: str = ""
    priority: list[str] = []
    lifecycle_stage: str = ""
    has_phone: bool = True
    max_drivers: int = 1000
    created_by: str = "system"


class CampaignOutcomeBody(BaseModel):
    campaign_member_id: str = ""
    driver_id: str = ""
    crm_status: str = "CONTACTED"
    outcome_note: str = ""
    outcome_at: str = ""


# ─── H3.3: CRM Bridge models ──────────────────────────────────────────────────

class CrmExportBody(BaseModel):
    crm_system_name: str = "generic"
    actor: str = "system"


class CrmImportOutcomesBody(BaseModel):
    crm_system_name: str = "generic"
    crm_campaign_reference: str = ""
    outcomes: list[dict] = []


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


@router.get("/lifecycle-distribution")
async def lifecycle_distribution(
    country: Optional[str] = Query(None), city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
):
    """Lightweight lifecycle distribution from serving facts. <2s SLA."""
    return JSONResponse(content=sanitize_for_json(compute_lifecycle_distribution(
        country=country, city=city, park_id=park_id,
    )))


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


# ─── H1: Health Check ─────────────────────────────────────────────────────────

@router.get("/health")
async def drivers_health():
    """
    Lightweight health check for all drivers foundation services.
    No full scans. Each check does a minimal probe (1 row, 1 query, timeout 10s).
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    checks = []

    async def probe(name, fn, remediation=""):
        try:
            loop = asyncio.get_running_loop()
            with ThreadPoolExecutor(max_workers=1) as pool:
                result = await asyncio.wait_for(
                    loop.run_in_executor(pool, fn), timeout=10.0
                )
            ok = result is not None and not isinstance(result, Exception)
            return {
                "name": name,
                "status": "ok" if ok else "warning",
                "message": "Responding" if ok else "No response",
                "remediation": "" if ok else remediation,
            }
        except asyncio.TimeoutError:
            return {
                "name": name,
                "status": "blocked",
                "message": "Timeout after 10s",
                "remediation": remediation,
            }
        except Exception as e:
            return {
                "name": name,
                "status": "blocked",
                "message": str(e)[:200],
                "remediation": remediation,
            }

    probes = [
        ("serving-facts",
         lambda: _probe_serving_facts(),
         "Run refresh_driver_supply_facts.py para crear/refrescar facts"),
        ("geo-parks-source",
         lambda: _probe_geo_parks(),
         "Verify geo/park dimension source (dim.dim_park)"),
        ("identity-probe",
         lambda: _probe_table_rows("public.drivers", "Tabla drivers no encontrada"),
         "Verify public.drivers table"),
        ("activity-fact-probe",
         lambda: _probe_table_rows("ops.driver_daily_activity_fact", "Fact de actividad no encontrada"),
         "Verify ops.driver_daily_activity_fact exists. Run refresh_driver_supply_facts.py"),
        ("lifecycle-mv-probe",
         lambda: _probe_table_rows("ops.mv_driver_lifecycle_base", "MV de lifecycle no encontrada"),
         "Verify ops.mv_driver_lifecycle_base exists"),
        ("workflow-tables",
         lambda: _probe_table_rows("ops.driver_supply_workflow", "Tabla de workflow no encontrada"),
         "Verify ops.driver_supply_workflow exists"),
        ("campaigns-table",
         lambda: _probe_table_rows("ops.driver_campaigns", "Tabla de campañas no encontrada"),
         "Verify ops.driver_campaigns exists"),
        ("geo-options-probe",
         lambda: _probe_table_rows("ops.driver_supply_overview_weekly_fact", "Fact de supply overview no encontrada"),
         "Run refresh_driver_supply_facts.py"),
    ]

    results = []
    for name, fn, remediation in probes:
        result = await probe(name, fn, remediation)
        checks.append(result)
        results.append(result)

    blocking = [c for c in checks if c["status"] == "blocked"]
    warnings_list = [c for c in checks if c["status"] == "warning"]

    if blocking:
        overall = "blocked"
    elif warnings_list:
        overall = "warning"
    else:
        overall = "ok"

    return JSONResponse(content={
        "status": overall,
        "checks": checks,
        "blocking_gaps": blocking,
        "warnings": warnings_list,
        "remediation": "Run: cd backend && python scripts/refresh_driver_supply_facts.py" if blocking else "",
    })


def _probe_table_rows(table_name: str, fail_message: str = ""):
    """Lightweight probe: check if a table exists and has at least 1 row."""
    from app.db.connection import get_db
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout = '5000'")
            cur.execute(f"SELECT COUNT(*) FROM (SELECT 1 FROM {table_name} LIMIT 1) t")
            row = cur.fetchone()
            if row and row[0] > 0:
                return {"exists": True, "has_rows": True}
            return {"exists": True, "has_rows": False, "message": fail_message or f"{table_name} is empty"}
    except Exception as e:
        return None


def _probe_geo_parks():
    """Lightweight probe: check dim.dim_park exists and has rows."""
    from app.db.connection import get_db
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout = '5000'")
            cur.execute("SELECT 1 FROM dim.dim_park LIMIT 1")
            cur.fetchone()
        return {"exists": True}
    except Exception:
        return None


def _probe_serving_facts():
    """Check if driver serving facts exist and are fresh."""
    from app.db.connection import get_db
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout = '5000'")
            cur.execute("""
                SELECT fact_name, freshness_status, row_count,
                       refreshed_at, max_operational_period
                FROM ops.driver_serving_freshness_fact
                ORDER BY fact_name
                LIMIT 10
            """)
            rows = cur.fetchall()
            if not rows:
                return {"exists": False, "message": "No serving facts found. Run refresh_driver_supply_facts.py"}
            facts = []
            for r in rows:
                facts.append({
                    "name": r[0], "status": r[1], "rows": r[2],
                    "refreshed_at": r[3].isoformat() if r[3] else None,
                    "max_period": r[4].isoformat()[:10] if r[4] and hasattr(r[4], 'isoformat') else str(r[4]) if r[4] else None,
                })
            stale = [f for f in facts if f["status"] in ("stale", "blocked")]
            return {
                "exists": True,
                "facts": facts,
                "stale_count": len(stale),
                "status": "warning" if stale else "ok",
            }
    except Exception:
        return None


# ─── H2: Pilot Operations ─────────────────────────────────────────────────────

@router.get("/pilot-readiness")
async def pilot_readiness():
    """Evaluate system readiness for operational pilot."""
    return JSONResponse(content=evaluate_pilot_readiness())


@router.post("/pilot/cohort-preview")
async def pilot_cohort_preview(body: PilotCohortBody):
    """Preview a pilot cohort without persisting."""
    country = body.country or None
    city = body.city or None
    park_id = body.park_id or None
    queue_types = body.queue_types if body.queue_types else None
    return JSONResponse(content=preview_cohort(
        country=country, city=city, park_id=park_id,
        queue_types=queue_types, max_drivers=body.max_drivers,
        has_phone_only=body.has_phone_only,
    ))


@router.post("/pilot/cohort")
async def pilot_cohort_create(body: PilotCohortBody):
    """Create a frozen pilot cohort persisted to ops.driver_pilot_cohort."""
    country = body.country or None
    city = body.city or None
    park_id = body.park_id or None
    queue_types = body.queue_types if body.queue_types else None
    return JSONResponse(content=create_pilot_cohort(
        country=country, city=city, park_id=park_id,
        queue_types=queue_types, max_drivers=body.max_drivers,
        has_phone_only=body.has_phone_only,
    ))


@router.post("/pilot/assign")
async def pilot_assign(body: PilotAssignBody):
    """Distribute cohort cases among owners."""
    return JSONResponse(content=assign_pilot_owners(
        cohort_id=body.cohort_id, owners=body.owners, strategy=body.strategy,
    ))


@router.get("/pilot/metrics")
async def pilot_metrics(cohort_id: str = Query("")):
    """Get pilot descriptive metrics."""
    return JSONResponse(content=get_pilot_metrics(cohort_id=cohort_id or None))


@router.post("/pilot/learning-log")
async def pilot_learning_log_add(body: PilotLearningLogBody):
    """Record an operational observation to the learning log."""
    return JSONResponse(content=add_learning_log(
        cohort_id=body.cohort_id or None, driver_id=body.driver_id or None,
        owner=body.owner or None, observation_type=body.observation_type,
        observation_note=body.observation_note or None,
    ))


@router.get("/pilot/learning-log")
async def pilot_learning_log_get(
    cohort_id: str = Query(""), owner: str = Query(""),
    observation_type: str = Query(""),
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
):
    """Query pilot learning log entries."""
    return JSONResponse(content=get_learning_log(
        cohort_id=cohort_id or None, owner=owner or None,
        observation_type=observation_type or None, limit=limit, offset=offset,
    ))


# ─── H3.2: Campaign Intelligence ──────────────────────────────────────────────

@router.post("/campaigns/preview")
async def campaign_preview(body: CampaignPreviewBody):
    """Preview a campaign cohort without persisting."""
    return JSONResponse(content=preview_campaign(
        campaign_name=body.campaign_name,
        campaign_type=body.campaign_type,
        campaign_objective=body.campaign_objective,
        source_queue_types=body.source_queue_types if body.source_queue_types else None,
        country=body.country or None, city=body.city or None,
        park_id=body.park_id or None,
        priority=body.priority if body.priority else None,
        lifecycle_stage=body.lifecycle_stage or None,
        has_phone=body.has_phone if body.has_phone else None,
        max_drivers=body.max_drivers,
    ))


@router.post("/campaigns")
async def campaign_create(body: CampaignCreateBody):
    """Create a campaign with frozen member snapshots."""
    return JSONResponse(content=create_campaign(
        campaign_name=body.campaign_name,
        campaign_type=body.campaign_type,
        campaign_objective=body.campaign_objective,
        source_queue_types=body.source_queue_types if body.source_queue_types else None,
        country=body.country or None, city=body.city or None,
        park_id=body.park_id or None,
        priority=body.priority if body.priority else None,
        lifecycle_stage=body.lifecycle_stage or None,
        has_phone=body.has_phone if body.has_phone else None,
        max_drivers=body.max_drivers,
        created_by=body.created_by or "system",
    ))


@router.get("/campaigns")
async def campaign_list(
    campaign_status: str = Query(""), campaign_type: str = Query(""),
    country: str = Query(""), city: str = Query(""),
    created_from: str = Query(""), created_to: str = Query(""),
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
):
    """List campaigns with filters."""
    return JSONResponse(content=list_campaigns(
        campaign_status=campaign_status or None,
        campaign_type=campaign_type or None,
        country=country or None, city=city or None,
        created_from=created_from or None, created_to=created_to or None,
        limit=limit, offset=offset,
    ))


@router.get("/campaigns/effectiveness-summary")
async def campaign_effectiveness_summary():
    """Get effectiveness summary across all campaigns with measurements."""
    return JSONResponse(content=get_effectiveness_summary())


@router.get("/campaigns/sync-health")
async def campaigns_sync_health(campaign_id: str = Query("")):
    """Get overall CRM sync health status."""
    return JSONResponse(content=get_sync_health(campaign_id=campaign_id or None))


@router.get("/campaigns/{campaign_id}")
async def campaign_detail(campaign_id: str):
    """Get campaign detail with member summary and sample."""
    return JSONResponse(content=get_campaign_detail(campaign_id))


@router.get("/campaigns/{campaign_id}/members")
async def campaign_members(
    campaign_id: str,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    only_with_phone: bool = Query(True),
):
    """Get campaign members for CRM consumption."""
    return JSONResponse(content=get_campaign_members(
        campaign_id=campaign_id, limit=limit, offset=offset,
        only_with_phone=only_with_phone,
    ))


@router.post("/campaigns/{campaign_id}/outcomes")
async def campaign_outcome(campaign_id: str, body: CampaignOutcomeBody):
    """Ingest a campaign outcome from CRM or operator."""
    outcome_at_val = body.outcome_at if body.outcome_at else None
    return JSONResponse(content=ingest_campaign_outcome(
        campaign_id=campaign_id,
        campaign_member_id=body.campaign_member_id or None,
        driver_id=body.driver_id or None,
        crm_status=body.crm_status,
        outcome_note=body.outcome_note,
        outcome_at=outcome_at_val,
    ))


@router.get("/campaigns/{campaign_id}/summary")
async def campaign_summary(campaign_id: str):
    """Get campaign aggregate summary."""
    return JSONResponse(content=get_campaign_summary(campaign_id=campaign_id))


# ─── H3.3: CRM Bridge & Sync ──────────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/crm-export")
async def campaign_crm_export(campaign_id: str, crm_system_name: str = Query("generic"), actor: str = Query("system")):
    """Generate CRM-ready export payload and register sync."""
    return JSONResponse(content=generate_crm_export(
        campaign_id=campaign_id, crm_system_name=crm_system_name, actor=actor,
    ))


@router.post("/campaigns/{campaign_id}/crm-sync/outcomes")
async def campaign_crm_import(campaign_id: str, body: CrmImportOutcomesBody):
    """Import outcomes from CRM and update campaign progress."""
    return JSONResponse(content=import_crm_outcomes(
        campaign_id=campaign_id,
        crm_system_name=body.crm_system_name or "generic",
        crm_campaign_reference=body.crm_campaign_reference or None,
        outcomes=body.outcomes,
    ))


@router.get("/campaigns/{campaign_id}/progress")
async def campaign_progress(campaign_id: str):
    """Get campaign execution progress with outcomes and sync history."""
    return JSONResponse(content=compute_campaign_progress(campaign_id))


@router.get("/campaigns/{campaign_id}/sync-history")
async def campaign_sync_history(campaign_id: str, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """Get sync history for a campaign."""
    return JSONResponse(content=get_sync_history(campaign_id=campaign_id, limit=limit, offset=offset))



@router.get("/crm-bridge/health")
async def crm_bridge_health():
    """Check CRM Bridge operational health. Graceful degradation: CRM failure does NOT block Drivers."""
    return JSONResponse(content=check_bridge_health())


# ─── H3.4: Campaign Effectiveness ─────────────────────────────────────────────

@router.get("/campaigns/{campaign_id}/effectiveness")
async def campaign_effectiveness(
    campaign_id: str,
    window_days: int = Query(7, ge=1, le=30),
    include_members: bool = Query(False),
    group_by: str = Query(""),
):
    """
    Compute campaign effectiveness metrics.
    Measured: pre/post trip activity, reactivation rate, by segment.
    Language: "observed lift", NOT "caused by campaign".
    """
    return JSONResponse(content=compute_campaign_effectiveness(
        campaign_id=campaign_id, window_days=window_days,
        include_members=include_members,
        group_by=group_by if group_by else None,
    ))


# ─── OLM1: Operational Loop ───────────────────────────────────────────────────

@router.get("/operational-loop/model")
async def operational_loop_model():
    """Get the operational loop model definition."""
    return JSONResponse(content=get_operational_loop_model())


@router.get("/campaigns/operating-board")
async def campaigns_operating_board():
    """Campaign Operating Board: campaigns grouped by loop stage."""
    return JSONResponse(content=get_operating_board())


@router.get("/campaigns/{campaign_id}/loop-status")
async def campaign_loop_status(campaign_id: str):
    """Derived operational loop status for a campaign."""
    return JSONResponse(content=get_campaign_loop_status(campaign_id))


@router.get("/campaigns/{campaign_id}/follow-up")
async def campaign_follow_up(campaign_id: str):
    """Follow-up classification for campaign members based on outcomes."""
    return JSONResponse(content=get_campaign_follow_up(campaign_id))


@router.get("/campaigns/{campaign_id}/qa-checklist")
async def campaign_qa_checklist(campaign_id: str):
    """Human QA checklist for campaign supervision."""
    return JSONResponse(content=get_campaign_qa_checklist(campaign_id))


# ─── H3.5A: Segment Migration ─────────────────────────────────────────────────

@router.get("/segment-migration")
async def segment_migration(
    country: str = Query(""), city: str = Query(""),
    park_id: str = Query(""),
    period_grain: str = Query("weekly"),
    current_period: str = Query(""),
    previous_period: str = Query(""),
    include_same_segment: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    allow_runtime: bool = Query(False),
):
    """Driver-level segment migration. Fact-first; allow_runtime=true for legacy dev mode."""
    return JSONResponse(content=compute_segment_migration(
        country=country or None, city=city or None, park_id=park_id or None,
        period_grain=period_grain,
        current_period=current_period or None,
        previous_period=previous_period or None,
        include_same_segment=include_same_segment,
        limit=limit, offset=offset,
        allow_runtime=allow_runtime,
    ))


# ─── H3.5B: Operational Priorities ────────────────────────────────────────────

@router.get("/movements/actionable")
async def actionable_movements(
    country: str = Query(""), city: str = Query(""),
    park_id: str = Query(""),
    operational_priority: str = Query(""),
    movement_type: str = Query(""),
    recoverability_band: str = Query(""),
    execution_ready_only: bool = Query(False),
    campaignable_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    allow_runtime: bool = Query(False),
):
    """Operational priorities. Fact-first; allow_runtime=true for legacy dev mode. NO AI. NO ML."""
    return JSONResponse(content=get_actionable_movements(
        country=country or None, city=city or None, park_id=park_id or None,
        operational_priority=operational_priority or None,
        movement_type=movement_type or None,
        recoverability_band=recoverability_band or None,
        execution_ready_only=execution_ready_only,
        campaignable_only=campaignable_only,
        allow_runtime=allow_runtime,
        limit=limit, offset=offset,
    ))


# ─── SH3: Fact Path Endpoints ─────────────────────────────────────────────────

@router.get("/supply-overview-fact")
async def supply_overview_fact(
    country: str = Query(""), city: str = Query(""),
    park_id: str = Query(""),
    limit: int = Query(52, ge=1, le=200), offset: int = Query(0, ge=0),
):
    """Supply Overview from serving fact. No runtime compute."""
    from app.services.driver_serving_freshness_service import require_fact
    freshness = require_fact("driver_supply_overview_weekly_fact")
    if not freshness["ready"]:
        return JSONResponse(content={
            "status": freshness["freshness_status"],
            "serving_source": None,
            "remediation": freshness["remediation"],
            "series": [], "summary": {},
        })

    try:
        from app.db.connection import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout = '8000'")
            conditions = ["1=1"]
            params = {}
            if country:
                conditions.append("country = %(country)s"); params["country"] = country
            if city:
                conditions.append("city = %(city)s"); params["city"] = city
            if park_id:
                conditions.append("park_id = %(park_id)s"); params["park_id"] = park_id
            where = " AND ".join(conditions)

            cur.execute(f"""
                SELECT week_start, activations, active_drivers, trips, churned,
                       reactivated, net_growth, refreshed_at
                FROM ops.driver_supply_overview_weekly_fact
                WHERE {where}
                ORDER BY week_start DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, {**params, "limit": limit, "offset": offset})
            rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]

        if not rows:
            return JSONResponse(content=sanitize_for_json({
                "status": "ok",
                "serving_source": "driver_supply_overview_weekly_fact",
                "freshness_status": freshness["freshness_status"],
                "refreshed_at": freshness.get("refreshed_at"),
                "series": [],
                "summary": {},
                "message": "Sin datos para filtros actuales.",
            }))

        return JSONResponse(content=sanitize_for_json({
            "status": "ok",
            "serving_source": "driver_supply_overview_weekly_fact",
            "freshness_status": freshness["freshness_status"],
            "refreshed_at": freshness.get("refreshed_at"),
            "series": rows,
            "summary": {},
        }))
    except Exception as e:
        error_msg = str(e)[:200]
        is_timeout = "cancel" in error_msg.lower() or "timeout" in error_msg.lower()
        return JSONResponse(content=sanitize_for_json({
            "status": "blocked",
            "error": error_msg,
            "error_type": "query_timeout" if is_timeout else "db_error",
            "serving_source": "driver_supply_overview_weekly_fact",
            "remediation": "Query cancelada por timeout. Verificar indices en driver_supply_overview_weekly_fact." if is_timeout else "Run refresh_driver_supply_facts.py and verify DB connectivity.",
            "series": [],
            "summary": {},
        }))


@router.get("/segment-composition-fact")
async def segment_composition_fact(
    country: str = Query(""), city: str = Query(""),
    park_id: str = Query(""),
    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
):
    """Segment Composition from serving fact. Aggregated from driver_weekly_segment_fact."""
    from app.services.driver_serving_freshness_service import require_fact
    freshness = require_fact("driver_weekly_segment_fact")
    if not freshness["ready"]:
        return JSONResponse(content={
            "status": freshness["freshness_status"],
            "serving_source": None,
            "remediation": freshness["remediation"],
            "data": [],
        })

    try:
        from app.db.connection import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout = '10000'")
            conditions = ["1=1"]
            params = {}
            if country:
                conditions.append("country = %(country)s"); params["country"] = country
            if city:
                conditions.append("city = %(city)s"); params["city"] = city
            if park_id:
                conditions.append("park_id = %(park_id)s"); params["park_id"] = park_id
            where = " AND ".join(conditions)

            cur.execute(f"""
                SELECT week_start, segment,
                       COUNT(DISTINCT driver_id) as drivers_count,
                       SUM(trips_completed) as trips,
                       ROUND(COUNT(DISTINCT driver_id) * 100.0 / NULLIF(SUM(COUNT(DISTINCT driver_id)) OVER (PARTITION BY week_start), 0), 1) as share_of_active,
                       ROUND(AVG(trips_completed), 1) as avg_trips_per_driver
                FROM ops.driver_weekly_segment_fact
                WHERE {where} AND trips_completed > 0
                GROUP BY week_start, segment
                ORDER BY week_start DESC, segment
                LIMIT %(limit)s OFFSET %(offset)s
            """, {**params, "limit": limit, "offset": offset})
            rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]

        return JSONResponse(content=sanitize_for_json({
            "status": "ok",
            "serving_source": "driver_weekly_segment_fact",
            "freshness_status": freshness["freshness_status"],
            "refreshed_at": freshness.get("refreshed_at"),
            "data": rows,
        }))
    except Exception as e:
        return JSONResponse(content=sanitize_for_json({
            "status": "blocked", "error": str(e)[:200],
            "serving_source": "driver_weekly_segment_fact",
            "remediation": "Run refresh_driver_supply_facts.py and verify DB connectivity.",
        }))


@router.get("/serving-freshness")
async def serving_freshness(fact_name: str = Query("")):
    """Check freshness of all or a specific serving fact."""
    if fact_name:
        return JSONResponse(content=check_fact_freshness(fact_name))
    return JSONResponse(content=check_all_facts())


@router.get("/geo-options")
async def geo_options():
    """Geo options (countries, cities, parks) from serving facts. No dim.v_geo_park dependency."""
    from app.db.connection import get_db
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET LOCAL statement_timeout = '10000'")

            # From supply overview fact (fast, pre-aggregated)
            cur.execute("""
                SELECT
                    ARRAY_AGG(DISTINCT country ORDER BY country) FILTER (WHERE country IS NOT NULL AND country != 'Unknown') AS countries,
                    ARRAY_AGG(DISTINCT city ORDER BY city) FILTER (WHERE city IS NOT NULL AND city != 'Unknown') AS cities,
                    ARRAY_AGG(DISTINCT park_id ORDER BY park_id) FILTER (WHERE park_id IS NOT NULL AND park_id != 'Unknown') AS parks
                FROM ops.driver_supply_overview_weekly_fact
            """)
            row = cur.fetchone()

            countries = row[0] if row and row[0] else []
            cities = row[1] if row and row[1] else []
            parks_raw = row[2] if row and row[2] else []

            # Enrich parks with park_name from dim_park (optional, graceful)
            parks = []
            if parks_raw:
                try:
                    cur.execute("""
                        SELECT park_id, park_name, city, country
                        FROM dim.dim_park
                        WHERE park_id = ANY(%(pids)s)
                    """, {"pids": parks_raw})
                    park_map = {r[0]: {"park_id": r[0], "park_name": r[1], "city": r[2], "country": r[3]} for r in cur.fetchall()}
                    for pid in parks_raw:
                        parks.append(park_map.get(pid, {"park_id": pid, "park_name": None, "city": "", "country": ""}))
                except Exception:
                    parks = [{"park_id": p, "park_name": None, "city": "", "country": ""} for p in parks_raw]

            warnings_list = []
            if not countries and not cities:
                warnings_list.append("No geo data in supply facts. Verify driver_daily_activity_fact refresh.")

        return JSONResponse(content={
            "status": "warning" if warnings_list else "ok",
            "countries": countries,
            "cities": cities,
            "parks": parks,
            "serving_source": "driver_supply_overview_weekly_fact + dim.dim_park",
            "warnings": warnings_list,
        })
    except Exception as e:
        return JSONResponse(content={
            "status": "warning",
            "countries": [],
            "cities": [],
            "parks": [],
            "warnings": [f"Geo options from facts failed: {str(e)[:100]}. Supply remains operational with base options."],
        })
