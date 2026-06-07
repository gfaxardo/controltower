"""
YEGO Lima Growth — Program Capacity Policy Router (LG-UX-R2.8E)

Endpoints for reading, simulating, and managing program capacity policy.
NO auto-apply. NO rebuild. NO export.
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from app.services.yego_lima_program_capacity_policy_service import (
    get_active_policy, get_policy_versions, seed_default_policy,
    simulate_policy, validate_policy,
    save_draft, validate_draft, activate_policy, retire_policy, get_audit_log,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth",
    tags=["yego-lima-growth-program-capacity-policy"],
)


class ProgramPolicyEntry(BaseModel):
    program_code: str
    priority_rank: int
    allocation_mode: str = "STRICT_PRIORITY"
    min_daily_capacity: Optional[int] = None
    max_daily_capacity: Optional[int] = None
    target_share_pct: Optional[float] = None
    is_enabled: bool = True
    policy_reason: Optional[str] = None


class PolicySimulateRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    programs: List[ProgramPolicyEntry]


class PolicySaveDraftRequest(BaseModel):
    programs: List[ProgramPolicyEntry]


@router.get("/program-capacity-policy")
async def program_capacity_policy(date: str = Query(..., description="YYYY-MM-DD")):
    return get_active_policy(date)


@router.get("/program-capacity-policy/versions")
async def policy_versions(program_code: Optional[str] = Query(None)):
    return get_policy_versions(program_code)


@router.post("/program-capacity-policy/seed")
async def policy_seed():
    return seed_default_policy()


@router.post("/program-capacity-policy/simulate")
async def policy_simulate(payload: PolicySimulateRequest):
    policy_dict = {
        "programs": [p.model_dump() for p in payload.programs],
    }
    current = get_active_policy(payload.date)
    simulation = simulate_policy(payload.date, policy_dict)
    return {
        "current_policy": current,
        "simulation": simulation,
        "comparison": {
            "current_unassigned": current.get("programs", []),
            "simulated_unassigned": simulation.get("unassigned_total", 0),
            "total_capacity": simulation["total_capacity"],
            "total_actionable": simulation["total_actionable"],
        },
    }


@router.post("/program-capacity-policy/validate")
async def policy_validate(payload: PolicySimulateRequest):
    policy_dict = {"programs": [p.model_dump() for p in payload.programs]}
    return validate_policy(policy_dict)


# ── GUARDRAILS (R2.8F) ──

@router.post("/program-capacity-policy/save-draft")
async def policy_save_draft(payload: PolicySaveDraftRequest):
    programs = [p.model_dump() for p in payload.programs]
    return save_draft(programs)


@router.post("/program-capacity-policy/validate-draft")
async def policy_validate_draft(date: str = Query(..., description="YYYY-MM-DD")):
    return validate_draft(date)


@router.post("/program-capacity-policy/activate")
async def policy_activate(date: str = Query(..., description="YYYY-MM-DD")):
    return activate_policy(date)


@router.post("/program-capacity-policy/retire")
async def policy_retire(program_code: str = Query(..., description="Program code to retire")):
    return retire_policy(program_code)


@router.get("/program-capacity-policy/audit-log")
async def policy_audit_log(limit: int = Query(50)):
    return get_audit_log(limit)
