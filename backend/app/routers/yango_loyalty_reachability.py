"""
Yango Loyalty Reachability API — Fase 3A + 3A.1 Operating Layer.
Prefijo: /yango-loyalty

Fase 3A:
  GET  /summary, /kpis, /city-status, /gaps, /reachability
  POST /goals, /manual-results

Fase 3A.1 — Operating Layer:
  GET  /completeness      — Data completeness por KPI/ciudad/mes
  GET  /freshness          — Freshness de KPIs manuales
  GET  /daily-snapshot     — Snapshot diario: hoy vs esperado
  GET  /historical         — Tracking histórico mensual
  POST /goals/copy         — Copiar metas de mes anterior
  POST /manual-results/bulk — Bulk input con validación
"""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Body

from app.services.yango_loyalty_reachability_service import (
    get_summary, get_kpis, get_city_status, get_gaps, get_reachability,
    upsert_goals, upsert_manual_results,
    compute_loyalty_data_completeness,
    compute_kpi_freshness,
    get_daily_snapshot,
    get_historical_monthly,
    copy_goals_from_month,
    upsert_manual_results_bulk,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yango-loyalty",
    tags=["yango-loyalty"],
)


# ═══════════════════════════════════════════════
# Fase 3A — Original endpoints
# ═══════════════════════════════════════════════

@router.get("/summary")
async def yango_loyalty_summary(
    month: Optional[str] = Query(None, description="Mes en formato YYYY-MM."),
    country: str = Query("PE", description="Código de país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad."),
):
    try:
        return get_summary(month=month, country=country, city=city)
    except Exception as e:
        logger.exception("yango_loyalty_summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kpis")
async def yango_loyalty_kpis(
    month: Optional[str] = Query(None, description="Mes en formato YYYY-MM."),
):
    try:
        return {"kpis": get_kpis(month=month)}
    except Exception as e:
        logger.exception("yango_loyalty_kpis: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/city-status")
async def yango_loyalty_city_status(
    month: Optional[str] = Query(None),
    country: str = Query("PE"),
    city: str = Query("Lima", description="Lima, Trujillo, Arequipa"),
):
    valid_cities = {"Lima", "Trujillo", "Arequipa"}
    if city not in valid_cities:
        raise HTTPException(status_code=400, detail=f"Ciudad inválida. Opciones: {', '.join(sorted(valid_cities))}")
    try:
        return get_city_status(month=month, country=country, city=city)
    except Exception as e:
        logger.exception("yango_loyalty_city_status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gaps")
async def yango_loyalty_gaps(
    month: Optional[str] = Query(None),
    country: str = Query("PE"),
    city: Optional[str] = Query(None),
    min_gap_pct: Optional[float] = Query(None, ge=0, le=100),
):
    try:
        return get_gaps(month=month, country=country, city=city, min_gap_pct=min_gap_pct)
    except Exception as e:
        logger.exception("yango_loyalty_gaps: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reachability")
async def yango_loyalty_reachability(
    month: Optional[str] = Query(None),
    country: str = Query("PE"),
    city: Optional[str] = Query(None),
):
    try:
        return get_reachability(month=month, country=country, city=city)
    except Exception as e:
        logger.exception("yango_loyalty_reachability: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goals")
async def yango_loyalty_post_goals(
    goals: list[dict] = Body(...),
    owner: Optional[str] = Body(None),
):
    try:
        return upsert_goals(goals, owner=owner)
    except Exception as e:
        logger.exception("yango_loyalty_post_goals: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-results")
async def yango_loyalty_post_manual_results(
    results: list[dict] = Body(...),
    owner: Optional[str] = Body(None),
):
    try:
        return upsert_manual_results(results, owner=owner)
    except Exception as e:
        logger.exception("yango_loyalty_post_manual_results: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════
# Fase 3A.1 — Operating Layer endpoints
# ═══════════════════════════════════════════════

@router.get("/completeness")
async def yango_loyalty_completeness(
    month: Optional[str] = Query(None),
    country: str = Query("PE"),
    city: Optional[str] = Query(None),
):
    try:
        return compute_loyalty_data_completeness(month=month, country=country, city=city)
    except Exception as e:
        logger.exception("yango_loyalty_completeness: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/freshness")
async def yango_loyalty_freshness(
    month: Optional[str] = Query(None),
    country: str = Query("PE"),
    city: Optional[str] = Query(None),
):
    try:
        return compute_kpi_freshness(month=month, country=country, city=city)
    except Exception as e:
        logger.exception("yango_loyalty_freshness: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-snapshot")
async def yango_loyalty_daily_snapshot(
    month: Optional[str] = Query(None),
    country: str = Query("PE"),
    city: Optional[str] = Query(None),
):
    try:
        return get_daily_snapshot(month=month, country=country, city=city)
    except Exception as e:
        logger.exception("yango_loyalty_daily_snapshot: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical")
async def yango_loyalty_historical(
    country: str = Query("PE"),
    city: Optional[str] = Query(None),
    months_back: int = Query(6, ge=1, le=24, description="Meses hacia atrás"),
    kpi_code: Optional[str] = Query(None, description="Filtrar por KPI específico"),
):
    try:
        return get_historical_monthly(country=country, city=city, months_back=months_back, kpi_code=kpi_code)
    except Exception as e:
        logger.exception("yango_loyalty_historical: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/goals/copy")
async def yango_loyalty_copy_goals(
    from_month: str = Body(..., embed=True, description="Mes origen YYYY-MM"),
    to_month: str = Body(..., embed=True, description="Mes destino YYYY-MM"),
    country: str = Body("PE"),
    city: Optional[str] = Body(None),
    owner: Optional[str] = Body(None),
):
    try:
        return copy_goals_from_month(from_month=from_month, to_month=to_month, country=country, city=city, owner=owner)
    except Exception as e:
        logger.exception("yango_loyalty_copy_goals: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-results/bulk")
async def yango_loyalty_manual_results_bulk(
    results: list[dict] = Body(...),
    owner: Optional[str] = Body(None),
):
    """Bulk input con validación de rango, ciudades y KPIs."""
    try:
        return upsert_manual_results_bulk(results, owner=owner)
    except Exception as e:
        logger.exception("yango_loyalty_manual_results_bulk: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
