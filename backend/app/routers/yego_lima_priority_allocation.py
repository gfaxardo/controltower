"""
YEGO Lima Growth — Priority Allocation Router (LG-2.3 V1).

Deterministic allocation of daily capacity to programs by priority.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.yego_lima_priority_allocation_service import get_priority_allocation

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/priority-allocation",
    tags=["yego-lima-growth-priority-allocation"],
)


class ProgramAllocation(BaseModel):
    program_code: str
    program_name: str
    priority_rank: int
    available_opportunities: int
    allocated_capacity: int
    unmet_opportunities: int
    allocation_rate: float


class PriorityAllocationResponse(BaseModel):
    date: Optional[str] = None
    total_capacity: int
    total_opportunities: int
    total_allocated: int
    unmet_total: int
    remaining_capacity: int
    coverage_rate: float
    programs: List[ProgramAllocation]


@router.get("", response_model=PriorityAllocationResponse)
async def priority_allocation_get(
    date: str = Query(..., description="Date YYYY-MM-DD"),
):
    return get_priority_allocation(date)
