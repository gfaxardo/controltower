"""
Yango Loyalty / Oro Tracker API
Prefix: /yango-loyalty

Endpoints:
  GET  /yango-loyalty/summary       - Full KPI summary with category per city
  GET  /yango-loyalty/kpis           - Detailed KPI table
  GET  /yango-loyalty/reachability   - Reachability summary per city/KPI
  GET  /yango-loyalty/rules          - Official loyalty rules
  POST /yango-loyalty/manual-kpi     - Upload manual KPI value
  POST /yango-loyalty/target         - Upload single target
  POST /yango-loyalty/batch-targets  - Batch upload targets per city
  POST /yango-loyalty/ensure-tables  - Create loyalty tables
"""

from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services.yango_loyalty_service import (
    get_loyalty_summary,
    get_loyalty_kpis,
    get_loyalty_reachability,
    get_loyalty_rules,
    upsert_manual_kpi,
    upsert_target,
    upsert_batch_targets,
    ensure_loyalty_tables,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yango-loyalty", tags=["yango-loyalty"])


class ManualKpiPayload(BaseModel):
    kpi_key: str
    city: str
    month: str
    kpi_value: float


class TargetPayload(BaseModel):
    kpi_key: str
    city: str
    month: str
    target_value: float


class BatchTargetPayload(BaseModel):
    city: str
    month: str
    targets: dict[str, float]


@router.get("/summary")
async def loyalty_summary():
    try:
        return get_loyalty_summary()
    except Exception as e:
        logger.exception("yango-loyalty summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpis")
async def loyalty_kpis(city: Optional[str] = Query(None)):
    try:
        return get_loyalty_kpis(city=city)
    except Exception as e:
        logger.exception("yango-loyalty kpis: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reachability")
async def loyalty_reachability(city: Optional[str] = Query(None)):
    try:
        return get_loyalty_reachability(city=city)
    except Exception as e:
        logger.exception("yango-loyalty reachability: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def loyalty_rules():
    try:
        return get_loyalty_rules()
    except Exception as e:
        logger.exception("yango-loyalty rules: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-kpi")
async def loyalty_manual_kpi(payload: ManualKpiPayload):
    try:
        return upsert_manual_kpi(payload.kpi_key, payload.city, payload.month, payload.kpi_value)
    except Exception as e:
        logger.exception("yango-loyalty manual-kpi: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/target")
async def loyalty_target(payload: TargetPayload):
    try:
        return upsert_target(payload.kpi_key, payload.city, payload.month, payload.target_value)
    except Exception as e:
        logger.exception("yango-loyalty target: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-targets")
async def loyalty_batch_targets(payload: BatchTargetPayload):
    try:
        return upsert_batch_targets(payload.city, payload.month, payload.targets)
    except Exception as e:
        logger.exception("yango-loyalty batch-targets: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ensure-tables")
async def loyalty_ensure_tables():
    try:
        return ensure_loyalty_tables()
    except Exception as e:
        logger.exception("yango-loyalty ensure-tables: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
