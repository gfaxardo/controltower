"""
LG-SERV-2A — Growth Health API

Endpoints:
  GET /growth/health       → Overall system health
  GET /growth/freshness    → Serving freshness audit
  GET /growth/operability  → Full operability + dependency + root cause
"""

from __future__ import annotations

import logging
from fastapi import APIRouter

from app.services.serving_operability_service import (
    get_health,
    get_freshness,
    get_operability_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/growth",
    tags=["growth-serving-governance"],
)


@router.get("/health")
async def growth_health():
    return get_health()


@router.get("/freshness")
async def growth_freshness():
    return get_freshness()


@router.get("/operability")
async def growth_operability():
    return get_operability_status()
