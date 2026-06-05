"""
OV2-A — OMNIBUILDER V2 ROUTER (PLACEHOLDER)

Fase: OV2-A — Blindaje Lógico
Estado: SOLO DOCUMENTACIÓN — No implementar hasta OV2-B

Este archivo es un placeholder. Los endpoints aquí definidos NO están activos.
Se implementarán en OV2-B cuando OMNI-P0 cierre con GO real.

Endpoints propuestos:
    GET  /v2/matrix/{grain}              — Matriz OV2 completa
    GET  /v2/cell/{grain}/{country}/{city}/{slice}/{period} — Celda individual
    GET  /v2/audit/lineage/{metric_id}   — Lineage de métrica
    GET  /v2/audit/freshness             — Frescura de serving facts
    GET  /v2/audit/coverage              — Matriz de cobertura
    GET  /v2/audit/risk                  — Riesgos activos
    GET  /v2/registry/metrics            — Catálogo de métricas
    GET  /v2/registry/sources            — Catálogo de fuentes
"""

from fastapi import APIRouter

router = APIRouter(prefix="/v2", tags=["omnibuilder-v2"])

# ── PLACEHOLDER: No implementar hasta OV2-B ──────────────────────────


@router.get("/matrix/{grain}")
async def get_ov2_matrix(grain: str):
    """
    PLACEHOLDER — OV2-B
    
    Devuelve la matriz OV2 completa con contrato canónico de celda.
    Grain: daily | weekly | monthly
    """
    raise NotImplementedError("OV2-B: Implementar cuando OMNI-P0 cierre con GO real")


@router.get("/cell/{grain}/{country}/{city}/{slice}/{period}")
async def get_ov2_cell(grain: str, country: str, city: str, slice: str, period: str):
    """
    PLACEHOLDER — OV2-B
    
    Devuelve celda individual con trazabilidad completa.
    """
    raise NotImplementedError("OV2-B: Implementar cuando OMNI-P0 cierre con GO real")


@router.get("/audit/lineage/{metric_id}")
async def get_metric_lineage(metric_id: str):
    """
    PLACEHOLDER — OV2-B
    
    Devuelve árbol de lineage RAW → FACT → SERVING → API → UI.
    """
    raise NotImplementedError("OV2-B: Implementar cuando OMNI-P0 cierre con GO real")


@router.get("/audit/freshness")
async def get_audit_freshness():
    """
    PLACEHOLDER — OV2-B
    
    Devuelve frescura de todos los serving facts OV2.
    """
    raise NotImplementedError("OV2-B: Implementar cuando OMNI-P0 cierre con GO real")


@router.get("/audit/coverage")
async def get_audit_coverage():
    """
    PLACEHOLDER — OV2-B
    
    Devuelve matriz de cobertura grain × metric × country.
    """
    raise NotImplementedError("OV2-B: Implementar cuando OMNI-P0 cierre con GO real")


@router.get("/audit/risk")
async def get_audit_risk():
    """
    PLACEHOLDER — OV2-B
    
    Devuelve riesgos activos del risk register con status.
    """
    raise NotImplementedError("OV2-B: Implementar cuando OMNI-P0 cierre con GO real")


@router.get("/registry/metrics")
async def get_registry_metrics():
    """
    PLACEHOLDER — OV2-B
    
    Devuelve catálogo canónico de métricas OV2.
    """
    raise NotImplementedError("OV2-B: Implementar cuando OMNI-P0 cierre con GO real")


@router.get("/registry/sources")
async def get_registry_sources():
    """
    PLACEHOLDER — OV2-B
    
    Devuelve catálogo de fuentes de datos OV2.
    """
    raise NotImplementedError("OV2-B: Implementar cuando OMNI-P0 cierre con GO real")
