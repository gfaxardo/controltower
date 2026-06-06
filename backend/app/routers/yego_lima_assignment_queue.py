"""
YEGO Lima Growth — Assignment Queue Router (LG-2.5B V1).

Build and query persistent operational queue from worklist.
Export queue to LoopControl.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.yego_lima_assignment_queue_service import (
    create_assignment_batch,
    get_assignment_queue,
)
from app.services.yego_lima_loopcontrol_export_service import export_from_contacts
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

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
    total_records: int = 0
    ready_count: int = 0
    held_count: int = 0
    records: List[QueueRecord] = []


class ExportRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    program_code: Optional[str] = None
    campaign_name: Optional[str] = None
    created_by: Optional[str] = None
    limit: int = Field(default=500, ge=1, le=500)


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


@router.post("/export")
async def assignment_queue_export(payload: ExportRequest):
    TABLE_QUEUE = "growth.yego_lima_assignment_queue"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        conditions = ["assignment_date = %(d)s", "queue_status = 'READY'"]
        params = {"d": payload.date}
        if payload.program_code:
            conditions.append("program_code = %(p)s")
            params["p"] = payload.program_code
        where = " AND ".join(conditions)

        cur.execute(
            f"SELECT * FROM {TABLE_QUEUE} WHERE {where} "
            f"ORDER BY priority_rank ASC NULLS LAST LIMIT %(lim)s",
            {**params, "lim": payload.limit},
        )
        rows = cur.fetchall()

    if not rows:
        return {"exported": False, "error": "No READY records in queue for this date", "count": 0}

    contacts = []
    for r in rows:
        contacts.append({
            "driver_id": r["driver_id"],
            "phone": r["phone"],
            "driver_name": r["driver_name"],
            "assigned_channel": r["assigned_channel"],
            "priority_rank": r["priority_rank"],
        })

    program_code = payload.program_code or (rows[0]["program_code"] if rows else "UNKNOWN")

    return export_from_contacts(
        contacts=contacts,
        opportunity_date=payload.date,
        program_code=program_code,
        campaign_name=payload.campaign_name,
        created_by=payload.created_by,
    )
