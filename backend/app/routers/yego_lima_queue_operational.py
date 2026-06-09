"""YEGO Lima Growth — Queue Operational Router (LG-UX-R2.5)"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_queue_operational_service import get_queue_operational_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/assignment-queue/operational-summary", tags=["yego-lima-growth-queue-operational"])

@router.get("")
async def queue_operational_summary(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    return get_queue_operational_summary(date)
