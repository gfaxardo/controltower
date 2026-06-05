"""
YEGO Lima Growth — Channel Allocation Router (LG-2.4 V1).

Distributes priority-allocated capacity across operational channels.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.yego_lima_channel_allocation_service import get_channel_allocation

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/channel-allocation",
    tags=["yego-lima-growth-channel-allocation"],
)


class ChannelAllocationEntry(BaseModel):
    channel_code: str
    channel_name: str
    allocated_capacity: int


class ProgramChannelAllocation(BaseModel):
    program_code: str
    program_name: str
    priority_rank: int
    program_allocated_capacity: int
    channel_allocations: List[ChannelAllocationEntry]
    unassigned_capacity: int


class ChannelSummary(BaseModel):
    channel_code: str
    channel_name: str
    total_capacity: int
    allocated_capacity: int
    remaining_capacity: int
    utilization_rate: float


class ChannelAllocationResponse(BaseModel):
    date: Optional[str] = None
    total_capacity: int
    total_channel_capacity: int
    total_priority_allocated: int
    total_channel_allocated: int
    unassigned_capacity: int
    channels: List[ChannelSummary]
    programs: List[ProgramChannelAllocation]


@router.get("", response_model=ChannelAllocationResponse)
async def channel_allocation_get(
    date: str = Query(..., description="Date YYYY-MM-DD"),
):
    return get_channel_allocation(date)
