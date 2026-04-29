"""
Fase E2E — Diagnósticos de join Plan vs Real.
Prefijo: /api/diagnostics (se monta en main).
Aditivo: no modifica contratos existentes.
"""
from typing import Optional

from fastapi import APIRouter, Query

from app.services.projection_expected_progress_service import (
    _compute_join_diagnostics,
)

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/join-keys")
async def get_join_keys_diagnostics(
    grain: str = Query(..., description="Granularidad: monthly, weekly, daily"),
    plan_version: str = Query("v1", description="Versión del plan"),
    country: Optional[str] = Query(None, description="País (peru, colombia)"),
    city: Optional[str] = Query(None, description="Ciudad"),
    business_slice: Optional[str] = Query(None, description="Business slice"),
    year: Optional[int] = Query(None, description="Año"),
    month: Optional[int] = Query(None, description="Mes"),
):
    """
    Diagnóstico de join Plan vs Real.
    
    Retorna:
    - plan_keys, real_keys, intersection, plan_only, real_only
    - intersection_rate_pct
    - by_cause: desglose por causa de mismatch
    - go_threshold_85: True si >= 85%
    - go_threshold_92: True si >= 92%
    - plan_only_sample, real_only_sample: samples de claves sin match
    
    Úsalo para:
    - Validar que el join canonico funciona
    - Detectar mismatches antes de cerrar fase
    - Monitoreo y alertas
    """
    from datetime import date
    today = date.today()
    
    return _compute_join_diagnostics(
        grain=grain,
        plan_version=plan_version,
        country=country,
        city=city,
        business_slice=business_slice,
        year=year,
        month=month,
        today=today,
    )