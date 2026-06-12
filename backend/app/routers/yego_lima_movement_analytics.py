"""LG-MOV-2A — Movement Analytics Router"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_movement_analytics_service import (
    get_transition_matrix, get_top_winners, get_top_losers, get_movement_stats
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/movement-analytics", tags=["yego-lima-growth-movement-analytics"])


@router.get("/stats")
async def movement_stats():
    return get_movement_stats()


@router.get("/matrix")
async def transition_matrix():
    return get_transition_matrix()


@router.get("/winners")
async def top_winners(limit: int = Query(20, ge=1, le=100)):
    return get_top_winners(limit)


@router.get("/losers")
async def top_losers(limit: int = Query(20, ge=1, le=100)):
    return get_top_losers(limit)
