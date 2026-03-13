"""
Fase 1 — Endpoints de observabilidad E2E.
Prefijo: /ops/observability (se monta en main con prefix /ops, router prefix observability).
Aditivo: no modifica contratos existentes.
"""
from fastapi import APIRouter
from app.services.observability_service import (
    get_observability_overview,
    get_observability_modules,
    get_observability_artifacts,
    get_observability_lineage,
    get_observability_freshness,
)

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/overview")
async def observability_overview():
    """Resumen: módulos, conteos, refreshes recientes. Para dashboard de observabilidad."""
    return get_observability_overview()


@router.get("/modules")
async def observability_modules():
    """Estado por módulo: artifact_count, latest_refresh_at, all_fresh, observability_coverage_pct."""
    return get_observability_modules()


@router.get("/artifacts")
async def observability_artifacts():
    """Lista de artefactos del registry con último refresh (si existe)."""
    return get_observability_artifacts()


@router.get("/lineage")
async def observability_lineage():
    """Lineage: artefactos activos por módulo (refresh_owner, notes)."""
    return get_observability_lineage()


@router.get("/freshness")
async def observability_freshness():
    """Señales de frescura: artifact_name, latest_refresh_at, source."""
    return get_observability_freshness()
