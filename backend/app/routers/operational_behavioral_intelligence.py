"""
Operational Behavioral Intelligence API — Fase 2B
Prefijo: /operational-intelligence

Endpoints:
  GET /operational-intelligence/summary
  GET /operational-intelligence/efficiency
  GET /operational-intelligence/sessions
  GET /operational-intelligence/zones
  GET /operational-intelligence/time-patterns
  GET /operational-intelligence/pre-churn-signals
  GET /operational-intelligence/archetypes
  GET /operational-intelligence/top-vs-churned

Reglas:
  - NO genera recomendaciones automáticas.
  - NO automatiza acciones.
  - Diagnóstico determinístico solamente.
"""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.services.operational_behavioral_intelligence_service import (
    get_operational_summary,
    get_efficiency_analytics,
    get_session_analytics,
    get_zone_analytics,
    get_time_patterns,
    get_pre_churn_signals,
    get_operational_archetypes,
    get_top_vs_churned,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/operational-intelligence",
    tags=["operational-intelligence"],
)


@router.get("/summary")
async def operational_intelligence_summary(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Días de la ventana de análisis"),
):
    """
    Resumen operacional: KPIs agregados, fuentes disponibles, metadatos.
    """
    try:
        return get_operational_summary(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.error("GET /operational-intelligence/summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/efficiency")
async def operational_intelligence_efficiency(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Días de la ventana de análisis"),
):
    """
    KPIs de eficiencia operacional: revenue/hour, revenue/km, trips/hour,
    trips/day, peak-hour share, weekend share, zone concentration.
    """
    try:
        return get_efficiency_analytics(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.error("GET /operational-intelligence/efficiency: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def operational_intelligence_sessions(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Días de la ventana de análisis"),
):
    """
    Analítica de sesiones operacionales: duración, trips/session,
    revenue/session, idle time, idle ratio, distribución por sesión.
    """
    try:
        return get_session_analytics(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.error("GET /operational-intelligence/sessions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/zones")
async def operational_intelligence_zones(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Días de la ventana de análisis"),
):
    """
    Comportamiento por zona (park_id como proxy): trips, revenue,
    drivers únicos, peak-hour share, weekend share, concentración.
    """
    try:
        return get_zone_analytics(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.error("GET /operational-intelligence/zones: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/time-patterns")
async def operational_intelligence_time_patterns(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Días de la ventana de análisis"),
):
    """
    Patrones de comportamiento por hora del día y día de la semana.
    Incluye comparación peak vs off-peak.
    """
    try:
        return get_time_patterns(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.error("GET /operational-intelligence/time-patterns: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pre-churn-signals")
async def operational_intelligence_pre_churn_signals(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(56, ge=14, le=180, description="Ventana de análisis (mín 14 días para comparar mitades)"),
):
    """
    Señales tempranas de deterioro operacional previo al churn.
    Compara primera mitad vs segunda mitad del período.
    Clasifica: EARLY_WARNING, MODERATE_DEGRADATION, STRONG_DEGRADATION.
    NO recomendaciones.
    """
    try:
        return get_pre_churn_signals(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.error("GET /operational-intelligence/pre-churn-signals: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/archetypes")
async def operational_intelligence_archetypes(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Días de la ventana de análisis"),
):
    """
    Clasificación determinística de arquetipos operacionales.
    Reglas auditables, sin ML.
    Arquetipos: FULLTIMER, PART_TIMER, WEEKEND_SPECIALIST,
    PEAK_HOUR_SPECIALIST, HIGH_EFFICIENCY, HIGH_VOLUME_LOW_EFFICIENCY,
    CONSISTENT_OPERATOR, INCONSISTENT_OPERATOR, BURNOUT_PATTERN.
    """
    try:
        return get_operational_archetypes(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.error("GET /operational-intelligence/archetypes: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-vs-churned")
async def operational_intelligence_top_vs_churned(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=180, description="Días de la ventana de análisis"),
):
    """
    Comparación operacional entre conductores TOP vs CHURNED.
    TOP = top 20% por revenue.
    CHURNED = sin actividad en últimos 14 días.
    """
    try:
        return get_top_vs_churned(
            country=country,
            city=city,
            period_days=period_days,
        )
    except Exception as e:
        logger.error("GET /operational-intelligence/top-vs-churned: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
