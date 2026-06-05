"""
YEGO Lima Growth — Assignment Queue Router (LG-2.5B V1).

Build and query persistent operational queue from worklist.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.yego_lima_assignment_queue_service import (
    create_assignment_batch,
    get_assignment_queue,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/assignment-queue",
    tags=["yego-lima-growth-assignment-queue"],
)


class BuildBatchResponse(BaseModel):
    assignment_batch_id: str
    assignment_date: str
    created_count: int
    ready_count: int
    held_count: int
    skipped_duplicates: int


class QueueRecord(BaseModel):
    id: str
    assignment_batch_id: str
    driver_id: str
    driver_name: Optional[str] = None
    phone: Optional[str] = None
    program_code: str
    program_name: Optional[str] = None
    priority_rank: Optional[int] = None
    assigned_channel: Optional[str] = None
    opportunity_reason: Optional[str] = None
    last_trip_date: Optional[str] = None
    recent_trips: Optional[int] = None
    country: Optional[str] = None
    city: Optional[str] = None
    park: Optional[str] = None
    queue_status: str


class QueueResponse(BaseModel):
    date: Optional[str] = None
    total_records: int
    ready_count: int
    held_count: int
    records: List[QueueRecord]


@router.post("/build", response_model=BuildBatchResponse)
async def assignment_queue_build(
    date: str = Query(..., description="Date YYYY-MM-DD"),
    program: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
):
    return create_assignment_batch(
        date_str=date,
        program=program,
        channel=channel,
        city=city,
    )


@router.get("", response_model=QueueResponse)
async def assignment_queue_get(
    date: str = Query(..., description="Date YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="READY or HELD"),
    program: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
):
    return get_assignment_queue(
        date_str=date,
        status=status,
        program=program,
        channel=channel,
    )
