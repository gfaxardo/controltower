"""
Behavioral Diagnostic MVP API — Fase 2A.3
Motor: Diagnostic Engine
Endpoint: GET /ops/diagnostics/behavioral/mvp

Diagnostico conductual individual usando solo senales disponibles.
NO genera recomendaciones.
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from app.services.behavioral_diagnostic_mvp_service import get_behavioral_diagnosis_mvp
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops/diagnostics/behavioral", tags=["behavioral-mvp"])


@router.get("/mvp")
async def behavioral_diagnosis_mvp(
    country: Optional[str] = Query(None, description="Filtrar por pais (peru, colombia)"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    park_id: Optional[str] = Query(None, description="Filtrar por park_id"),
    window_days: int = Query(28, ge=7, le=90, description="Dias de la ventana de analisis actual"),
    comparison_window_days: Optional[int] = Query(None, ge=7, le=90, description="Dias de la ventana de comparacion previa (default: igual a window_days)"),
    limit: int = Query(100, ge=1, le=500, description="Maximo de conductores a retornar"),
):
    """
    Diagnostico conductual MVP — nivel conductor individual.

    Clasifica conductores usando senales disponibles en ops.driver_daily_activity_fact:
    trips, active_days, days_since_last, weekend_share.

    NO usa revenue, online_hours, cancellations, acceptance, zones, trip_hour.

    Retorna:
    - Lista de conductores con status, severity, dominant_factor, explanation
    - Resumen por status
    - Metadata de senales usadas / faltantes
    """
    try:
        return get_behavioral_diagnosis_mvp(
            country=country,
            city=city,
            park_id=park_id,
            window_days=window_days,
            comparison_window_days=comparison_window_days,
            limit=limit,
        )
    except Exception as e:
        logger.error("GET /ops/diagnostics/behavioral/mvp: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
