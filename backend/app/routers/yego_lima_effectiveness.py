"""LG-IMP-1B — Program Effectiveness Router"""
import logging
from fastapi import APIRouter
from app.services.yego_lima_effectiveness_service import (
    get_effectiveness_summary, get_program_effectiveness, get_driver_effectiveness
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/effectiveness", tags=["yego-lima-growth-effectiveness"])


@router.get("/summary")
async def effectiveness_summary():
    return get_effectiveness_summary()


@router.get("/programs")
async def effectiveness_programs():
    return get_effectiveness_summary()


@router.get("/program/{program_code}")
async def program_effectiveness(program_code: str):
    return get_program_effectiveness(program_code)


@router.get("/driver/{driver_id}")
async def driver_effectiveness(driver_id: str):
    return get_driver_effectiveness(driver_id)
