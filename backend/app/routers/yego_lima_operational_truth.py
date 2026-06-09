"""YEGO Lima Growth — Operational Truth Router (LG-UX-R2.1)"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_operational_truth_service import get_operational_truth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/operational-truth", tags=["yego-lima-growth-operational-truth"])

@router.get("")
async def operational_truth(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    return get_operational_truth(date)
