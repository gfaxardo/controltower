"""YEGO Lima Growth — Today's Action Plan Router (LG-UX-R2.6)"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_todays_action_plan_service import get_todays_action_plan

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/todays-action-plan", tags=["yego-lima-growth-todays-plan"])

@router.get("")
async def todays_action_plan(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    return get_todays_action_plan(date)
