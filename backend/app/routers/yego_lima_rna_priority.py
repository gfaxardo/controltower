"""LG-RNA-2A — RNA Priority Router"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_rna_priority_service import (
    build_rna_priority, get_rna_priority_summary, get_rna_drivers, get_rna_driver_detail
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/rna-priority", tags=["yego-lima-growth-rna-priority"])


@router.post("/build")
async def rna_build():
    return build_rna_priority()


@router.get("/summary")
async def rna_summary():
    return get_rna_priority_summary()


@router.get("/drivers")
async def rna_drivers(band: str = Query(None), limit: int = Query(100, ge=1, le=10000), offset: int = Query(0, ge=0)):
    return get_rna_drivers(band, limit, offset)


@router.get("/driver/{driver_id}")
async def rna_driver_detail(driver_id: str):
    return get_rna_driver_detail(driver_id)


@router.get("/bands")
async def rna_bands():
    return {
        "bands": [
            {"band": "HOT", "min_score": 35, "description": "High priority — contactable, recent activity, high value"},
            {"band": "WARM", "min_score": 15, "description": "Medium priority — some signals, moderate potential"},
            {"band": "COLD", "max_score": 14, "description": "Low priority — dormant, churned, limited signals"},
        ],
        "scoring_signals": [
            {"signal": "contactable", "weight": 20},
            {"signal": "cancelled_signal", "weight": 15},
            {"signal": "recent_activity", "weight": 15},
            {"signal": "high_value", "weight": 10},
            {"signal": "positive_momentum", "weight": 10},
            {"signal": "has_program", "weight": 10},
            {"signal": "positive_movement", "weight": 5},
            {"signal": "trips_30d", "weight": 5},
            {"signal": "dormant_30d", "weight": -10},
            {"signal": "churned_lifecycle", "weight": -15},
        ],
    }
