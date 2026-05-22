"""
Driver Behavior Benchmarking API — Fase 2A.2
Prefijo: /driver-behavior (se monta en main.py)
Endpoints:
  GET /driver-behavior/summary
  GET /driver-behavior/group-benchmarks
  GET /driver-behavior/top-vs-risk
  GET /driver-behavior/distributions
"""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.services.driver_behavior_benchmarking_service import (
    get_behavior_benchmarking_summary,
    get_behavior_benchmarking_groups,
    get_behavior_benchmarking_top_vs_risk,
    get_behavior_benchmarking_distributions,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/driver-behavior", tags=["driver-behavior"])


@router.get("/summary")
async def driver_behavior_summary(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=90, description="Días de la ventana de análisis"),
    enrich_from_trips: bool = Query(False, description="Si True, enriquece con revenue/hour/distance desde trips_2026. Apagado por defecto."),
):
    """
    Resumen de benchmarking de comportamiento de conductores.
    Devuelve total de conductores analizados, conteos por grupo,
    métricas disponibles y faltantes, fuente de datos y rango de fechas.
    """
    try:
        result = get_behavior_benchmarking_summary(
            country=country,
            city=city,
            period_days=period_days,
            enrich_from_trips=enrich_from_trips,
        )
        return result
    except Exception as e:
        logger.error("GET /driver-behavior/summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/group-benchmarks")
async def driver_behavior_group_benchmarks(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=90, description="Días de la ventana de análisis"),
    enrich_from_trips: bool = Query(False, description="Si True, enriquece con revenue/hour/distance desde trips_2026. Apagado por defecto."),
):
    """
    Tabla de benchmarks por grupo lifecycle.
    Incluye: drivers_count, total_trips, avg_trips_per_driver,
    avg_active_days, trips_per_active_day, consistency_score,
    avg_ticket (nullable), revenue_per_driver (nullable),
    peak_hour_share (nullable), weekend_share (nullable).
    """
    try:
        result = get_behavior_benchmarking_groups(
            country=country,
            city=city,
            period_days=period_days,
            enrich_from_trips=enrich_from_trips,
        )
        return result
    except Exception as e:
        logger.error("GET /driver-behavior/group-benchmarks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-vs-risk")
async def driver_behavior_top_vs_risk(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=90, description="Días de la ventana de análisis"),
    enrich_from_trips: bool = Query(False, description="Si True, enriquece con revenue/hour/distance desde trips_2026. Apagado por defecto."),
):
    """
    Comparación directa TOP_PERFORMER vs DECLINING vs AT_RISK.
    Cada fila incluye: metric, top_performer_value, declining_value,
    at_risk_value, gap_top_vs_declining, gap_top_vs_at_risk, interpretation.
    Las interpretaciones son diagnósticas, no recomendaciones accionables.
    """
    try:
        result = get_behavior_benchmarking_top_vs_risk(
            country=country,
            city=city,
            period_days=period_days,
            enrich_from_trips=enrich_from_trips,
        )
        return result
    except Exception as e:
        logger.error("GET /driver-behavior/top-vs-risk: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/distributions")
async def driver_behavior_distributions(
    dimension: str = Query(..., description="Dimensión: city | park | lob | day_of_week | hour"),
    group_name: Optional[str] = Query(None, description="Filtrar por grupo lifecycle (opcional)"),
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=90, description="Días de la ventana de análisis"),
):
    """
    Distribución de viajes por dimensión para cada grupo lifecycle.
    Si la dimensión no existe, responde 200 con available=false y reason claro.
    """
    try:
        result = get_behavior_benchmarking_distributions(
            dimension=dimension,
            group_name=group_name,
            country=country,
            city=city,
            period_days=period_days,
        )
        return result
    except Exception as e:
        logger.error("GET /driver-behavior/distributions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
