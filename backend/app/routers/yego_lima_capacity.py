"""
YEGO Lima Growth — Daily Capacity Router (LG-2.2B).

Persistent capacity config: GET config, GET summary, PUT upsert.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.yego_lima_capacity_service import (
    get_capacity_config,
    upsert_capacity_config,
    calculate_capacity_summary,
    seed_default_capacity_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/capacity",
    tags=["yego-lima-growth-capacity"],
)


class ChannelEntry(BaseModel):
    channel: str
    agents: int
    capacity_per_agent: int


class UpsertCapacityRequest(BaseModel):
    config_date: Optional[str] = None
    channels: list[ChannelEntry]


@router.get("/config")
async def capacity_get_config(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD. NULL = default global."),
):
    return get_capacity_config(date)


@router.get("/summary")
async def capacity_get_summary(
    date: Optional[str] = Query(None, description="Date YYYY-MM-DD. NULL = default global."),
    actionable_count: int = Query(0, description="Actionable count for gap/coverage calculations"),
):
    return calculate_capacity_summary(date, actionable_count)


@router.put("/config")
async def capacity_upsert_config(payload: UpsertCapacityRequest):
    channels = [ch.model_dump() for ch in payload.channels]
    return upsert_capacity_config(payload.config_date, channels)


@router.post("/seed")
async def capacity_seed_default():
    return seed_default_capacity_config()
