"""YEGO Lima Growth — Operational History Router (LG-OEF-1.0A)"""
import logging
from fastapi import APIRouter
from app.services.yego_lima_operational_history_service import get_driver_operational_history

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/driver-history", tags=["yego-lima-growth-driver-history"])

@router.get("/{driver_id}")
async def driver_history(driver_id: str):
    return get_driver_operational_history(driver_id)
