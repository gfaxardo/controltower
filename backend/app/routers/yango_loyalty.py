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
from app.services.yango_loyalty_performance_service import (
    get_loyalty_performance,
    get_loyalty_bootstrap,
)
from app.services.yango_loyalty_definition_service import (
    get_sources,
    get_definition_sets,
    get_definition_set,
    preview_all_sets,
    get_validation_pack,
    get_operational_flow,
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


@router.get("/bootstrap")
async def loyalty_bootstrap():
    try:
        return get_loyalty_bootstrap()
    except Exception as e:
        logger.exception("yango-loyalty bootstrap: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def loyalty_performance(
    month: Optional[str] = Query(None, description="YYYY-MM"),
    country: str = Query("peru"),
    city: Optional[str] = Query(None),
    include_missing_targets: bool = Query(True),
):
    try:
        return get_loyalty_performance(
            month=month,
            country=country,
            city=city,
            include_missing_targets=include_missing_targets,
        )
    except Exception as e:
        logger.exception("yango-loyalty performance: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# --- Metric Definition Registry endpoints ---

@router.get("/definitions/sources")
async def definition_sources():
    try:
        return get_sources()
    except Exception as e:
        logger.exception("definitions sources: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/definitions/sets")
async def definition_sets():
    try:
        return get_definition_sets()
    except Exception as e:
        logger.exception("definitions sets: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/definitions/sets/{set_id}")
async def definition_set_detail(set_id: str):
    try:
        result = get_definition_set(set_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Definition set {set_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("definitions set detail: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/definitions/validation-pack")
async def definition_validation_pack(
    month: str = Query("2026-04", description="YYYY-MM"),
    country: str = Query("PE"),
    city: str = Query("lima"),
):
    try:
        return get_validation_pack(month, country, city)
    except Exception as e:
        logger.exception("definitions validation-pack: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/operational-flow")
async def loyalty_operational_flow(
    month: Optional[str] = Query(None, description="YYYY-MM"),
    country: str = Query("PE"),
    city: str = Query("lima"),
):
    try:
        return get_operational_flow(month or "2026-04", country, city)
    except Exception as e:
        logger.exception("yango-loyalty operational-flow: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
