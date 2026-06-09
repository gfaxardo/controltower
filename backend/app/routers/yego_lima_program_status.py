"""YEGO Lima Growth — Program Status Router (LG-UX-R2.4)"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_program_status_service import get_program_operational_status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/programs/status", tags=["yego-lima-growth-programs-status"])

@router.get("")
async def program_status(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    return get_program_operational_status(date)
