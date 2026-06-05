"""
YEGO Lima Growth — Opportunity Worklist Router (LG-2.5A V1).

Executive worklist of actionable drivers with profile enrichment.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.yego_lima_opportunity_worklist_service import (
    get_opportunity_worklist,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/opportunity-worklist",
    tags=["yego-lima-growth-opportunity-worklist"],
)


class WorklistRecord(BaseModel):
    driver_id: str
    driver_name: str
    phone: Optional[str] = None
    program_code: str
    program_name: str
    priority_rank: int
    assigned_channel: str
    opportunity_reason: str
    last_trip_date: Optional[str] = None
    recent_trips: int
    country: str
    city: str
    park: str
    lifecycle_state: Optional[str] = None
    productivity_bucket: Optional[str] = None
    final_rank: Optional[int] = None


class OpportunityWorklistResponse(BaseModel):
    date: Optional[str] = None
    total_records: int
    records: List[WorklistRecord]


@router.get("", response_model=OpportunityWorklistResponse)
async def opportunity_worklist_get(
    date: str = Query(..., description="Date YYYY-MM-DD"),
    program: Optional[str] = Query(None, description="Filter by program_code"),
    channel: Optional[str] = Query(None, description="Filter by assigned_channel"),
    city: Optional[str] = Query(None, description="Filter by city"),
    park: Optional[str] = Query(None, description="Filter by park_name"),
):
    return get_opportunity_worklist(
        date_str=date,
        program=program,
        channel=channel,
        city=city,
        park=park,
    )
