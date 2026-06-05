"""
YEGO Lima Growth — LoopControl Export Router (Fase LC-1).

DRAFT campaign export only. No execution. No automation.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.yego_lima_loopcontrol_export_service import (
    validate_loopcontrol_config,
    build_contacts_payload,
    export_campaign_draft,
    get_export_history,
    get_export_status,
)
from app.services.yego_lima_loopcontrol_export_job_service import (
    get_job_config,
    run_export_job,
    get_job_history,
    get_job_run_detail,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/loopcontrol",
    tags=["yego-lima-growth-loopcontrol"],
)


class ExportDraftRequest(BaseModel):
    opportunity_date: str
    program_code: str
    limit: int = 100
    campaign_name: Optional[str] = None
    created_by: Optional[str] = None


class RunJobRequest(BaseModel):
    run_date: str
    programs: Optional[List[str]] = None
    dry_run: Optional[bool] = None
    force: bool = False


@router.get("/config")
async def lc_config():
    return validate_loopcontrol_config()


@router.post("/export-draft")
async def lc_export_draft(payload: ExportDraftRequest):
    return export_campaign_draft(
        payload.opportunity_date,
        payload.program_code,
        payload.limit,
        payload.campaign_name,
        payload.created_by,
    )


@router.get("/exports")
async def lc_exports(limit: int = Query(20, ge=1, le=100)):
    return get_export_history(limit)


@router.get("/exports/{export_id}")
async def lc_export_detail(export_id: str):
    return get_export_status(export_id)


# ── Job endpoints (Fase LC-1.1) ──

@router.get("/export-job-config")
async def lc_job_config():
    return get_job_config()


@router.post("/run-export-job")
async def lc_run_job(payload: RunJobRequest):
    return run_export_job(
        payload.run_date,
        payload.programs,
        payload.dry_run,
        payload.force,
        "manual",
    )


@router.get("/export-job-runs")
async def lc_job_runs(limit: int = Query(20, ge=1, le=100)):
    return get_job_history(limit)


@router.get("/export-job-runs/{job_run_id}")
async def lc_job_run_detail(job_run_id: str):
    return get_job_run_detail(job_run_id)
