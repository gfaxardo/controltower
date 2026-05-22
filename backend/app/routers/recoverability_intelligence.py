"""
Recoverability Intelligence API - Fase 2C.1
Prefijo: /recoverability
Shadow mode: diagnostico solamente, sin recomendaciones ni automatizacion.

Endpoints:
  GET /recoverability/summary
  GET /recoverability/top-recoverable
  GET /recoverability/distribution
  GET /recoverability/driver/{driver_id}
  GET /recoverability/shadow-priority
"""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.services.recoverability_intelligence_service import (
    get_recoverability_summary,
    get_top_recoverable,
    get_recoverability_distribution,
    get_driver_recoverability,
    get_shadow_priority,
    get_recoverability_segments,
    get_recoverability_explainability,
    get_recoverability_risk_distribution,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/recoverability",
    tags=["recoverability"],
)


@router.get("/summary")
async def recoverability_summary(
    country: Optional[str] = Query(None, description="Filtrar por pais"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Dias de la ventana de analisis"),
):
    try:
        return get_recoverability_summary(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.exception("recoverability summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-recoverable")
async def recoverability_top(
    country: Optional[str] = Query(None, description="Filtrar por pais"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Dias de la ventana de analisis"),
    limit: int = Query(20, ge=1, le=200, description="Cantidad de drivers a devolver"),
):
    try:
        return get_top_recoverable(
            country=country,
            city=city,
            period_days=period_days,
            limit=limit,
        )
    except Exception as e:
        logger.exception("recoverability top: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distribution")
async def recoverability_distribution(
    country: Optional[str] = Query(None, description="Filtrar por pais"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Dias de la ventana de analisis"),
):
    try:
        return get_recoverability_distribution(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.exception("recoverability distribution: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/driver/{driver_id}")
async def driver_recoverability(
    driver_id: str,
    period_days: int = Query(28, ge=7, le=180, description="Dias de la ventana de analisis"),
):
    try:
        result = get_driver_recoverability(
            driver_id=driver_id,
            period_days=period_days,
        )
        if not result.get("available"):
            raise HTTPException(status_code=404, detail=result.get("reason", "Driver not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("driver recoverability: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shadow-priority")
async def recoverability_shadow_priority(
    country: Optional[str] = Query(None, description="Filtrar por pais"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Dias de la ventana de analisis"),
    limit: int = Query(50, ge=1, le=500, description="Cantidad de drivers a devolver"),
):
    try:
        return get_shadow_priority(
            country=country,
            city=city,
            period_days=period_days,
            limit=limit,
        )
    except Exception as e:
        logger.exception("recoverability shadow priority: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/segments")
async def recoverability_segments(
    country: Optional[str] = Query(None, description="Filtrar por pais"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Dias de la ventana de analisis"),
):
    try:
        return get_recoverability_segments(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.exception("recoverability segments: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explainability/{driver_id}")
async def recoverability_explainability(
    driver_id: str,
    period_days: int = Query(28, ge=7, le=180, description="Dias de la ventana de analisis"),
):
    try:
        result = get_recoverability_explainability(
            driver_id=driver_id,
            period_days=period_days,
        )
        if not result.get("available"):
            raise HTTPException(status_code=404, detail=result.get("reason", "Driver not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("recoverability explainability: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-distribution")
async def recoverability_risk_distribution(
    country: Optional[str] = Query(None, description="Filtrar por pais"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Dias de la ventana de analisis"),
):
    try:
        return get_recoverability_risk_distribution(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.exception("recoverability risk distribution: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
