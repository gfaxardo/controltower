"""
Behavioral Pattern Diagnosis API — Fase 2A.3
Prefijo: /behavioral-patterns
Explica patrones operativos diferenciales entre grupos de conductores.
NO genera recomendaciones automáticas.
"""
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.services.behavioral_pattern_diagnosis_service import (
    get_pattern_diagnosis_summary,
    get_pattern_diagnosis_patterns,
    get_pattern_diagnosis_group_profile,
    get_pattern_diagnosis_decline_signals,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/behavioral-patterns", tags=["behavioral-patterns"])


@router.get("/summary")
async def behavioral_patterns_summary(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=90, description="Días de la ventana de análisis"),
    enrich_from_trips: bool = Query(False, description="Enriquecimiento desde trips_2026. Apagado por defecto."),
):
    """
    Resumen de diagnóstico de patrones. Devuelve conteos por fuerza,
    dimensiones disponibles/faltantes, y modo diagnóstico determinístico.
    """
    try:
        return get_pattern_diagnosis_summary(
            country=country, city=city, period_days=period_days,
            enrich_from_trips=enrich_from_trips,
        )
    except Exception as e:
        logger.error("GET /behavioral-patterns/summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patterns")
async def behavioral_patterns_list(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=90, description="Días de la ventana de análisis"),
    enrich_from_trips: bool = Query(False, description="Enriquecimiento desde trips_2026. Apagado por defecto."),
    dimension: Optional[str] = Query(None, description="Filtrar por dimensión específica"),
    min_strength: Optional[str] = Query(None, description="Filtrar por fuerza mínima: HIGH, MEDIUM, o LOW"),
):
    """
    Lista completa de patrones diagnósticos detectados.
    Cada patrón incluye: dimension, strength, comparison_groups,
    metric_name, gap_abs, gap_pct, interpretation.
    """
    try:
        return get_pattern_diagnosis_patterns(
            country=country, city=city, period_days=period_days,
            enrich_from_trips=enrich_from_trips,
            dimension=dimension, min_strength=min_strength,
        )
    except Exception as e:
        logger.error("GET /behavioral-patterns/patterns: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/group-profile")
async def behavioral_patterns_group_profile(
    group_name: str = Query(..., description="Grupo lifecycle: TOP_PERFORMER, STABLE, GROWING, DECLINING, AT_RISK, DORMANT, CHURNED, REACTIVATED"),
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=90, description="Días de la ventana de análisis"),
    enrich_from_trips: bool = Query(False, description="Enriquecimiento desde trips_2026. Apagado por defecto."),
):
    """
    Perfil diagnóstico completo de un grupo lifecycle.
    Incluye: KPIs, top cities, top parks, métricas disponibles/faltantes.
    """
    try:
        return get_pattern_diagnosis_group_profile(
            group_name=group_name, country=country, city=city,
            period_days=period_days, enrich_from_trips=enrich_from_trips,
        )
    except Exception as e:
        logger.error("GET /behavioral-patterns/group-profile: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decline-signals")
async def behavioral_patterns_decline_signals(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    period_days: int = Query(28, ge=7, le=90, description="Días de la ventana de análisis"),
    enrich_from_trips: bool = Query(False, description="Enriquecimiento desde trips_2026. Apagado por defecto."),
):
    """
    Señales de deterioro operativo comparando STABLE vs DECLINING / AT_RISK.
    Las interpretaciones son diagnósticas, no recomendaciones.
    """
    try:
        return get_pattern_diagnosis_decline_signals(
            country=country, city=city, period_days=period_days,
            enrich_from_trips=enrich_from_trips,
        )
    except Exception as e:
        logger.error("GET /behavioral-patterns/decline-signals: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
