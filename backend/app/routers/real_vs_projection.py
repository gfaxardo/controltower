"""
Fase 2A — Endpoints Real vs Proyección.
Prefijo: /ops/real-vs-projection (montado en main con prefix /ops).
Aditivo: no modifica contratos existentes.
"""
from fastapi import APIRouter, Query
from app.services.real_vs_projection_service import (
    get_real_vs_projection_overview,
    get_real_vs_projection_dimensions,
    get_mapping_coverage,
    get_real_metrics,
    get_projection_template_contract,
    get_system_segmentation_view,
    get_projection_segmentation_view,
)

router = APIRouter(prefix="/real-vs-projection", tags=["real-vs-projection"])


@router.get("/overview")
async def real_vs_projection_overview():
    """Resumen: readiness, proyección cargada, mapping, métricas reales disponibles."""
    return get_real_vs_projection_overview()


@router.get("/dimensions")
async def real_vs_projection_dimensions():
    """Dimensiones disponibles para el comparativo (sistema)."""
    return get_real_vs_projection_dimensions()


@router.get("/mapping-coverage")
async def real_vs_projection_mapping_coverage():
    """Cobertura de mapping por dimension_type."""
    return get_mapping_coverage()


@router.get("/real-metrics")
async def real_vs_projection_real_metrics(
    country: str | None = Query(None, description="Filtro país"),
    city: str | None = Query(None, description="Filtro ciudad"),
    period: str | None = Query(None, description="Periodo YYYY-MM"),
    limit: int = Query(500, ge=1, le=2000),
):
    """Métricas reales mensuales para comparativo."""
    return get_real_metrics(country=country, city=city, period=period, limit=limit)


@router.get("/projection-template-contract")
async def real_vs_projection_template_contract():
    """Contrato esperado del Excel de proyección."""
    return get_projection_template_contract()


@router.get("/system-segmentation-view")
async def real_vs_projection_system_segmentation(
    country: str | None = Query(None),
    period: str | None = Query(None),
    limit: int = Query(300, ge=1, le=1000),
):
    """Vista comparativa por segmentación del sistema."""
    return get_system_segmentation_view(country=country, period=period, limit=limit)


@router.get("/projection-segmentation-view")
async def real_vs_projection_projection_segmentation(
    country: str | None = Query(None),
    period: str | None = Query(None),
    limit: int = Query(300, ge=1, le=1000),
):
    """Vista comparativa por segmentación de la proyección."""
    return get_projection_segmentation_view(country=country, period=period, limit=limit)
