from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import logging

from app.services.phase2c_accountability_service import (
    get_scoreboard,
    get_backlog,
    get_breaches,
    run_snapshot
)
from app.services.lob_universe_service import (
    get_universe_lob_summary,
    get_unmatched_trips_summary
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phase2c", tags=["phase2c"])


@router.get("/scoreboard")
async def get_scoreboard_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    week_from: Optional[str] = Query(None, description="Semana desde (YYYY-MM-DD)"),
    week_to: Optional[str] = Query(None, description="Semana hasta (YYYY-MM-DD)")
):
    """
    Fase 2C: Scoreboard semanal de ejecución.
    Muestra métricas de alertas, acciones y SLA por semana y país.
    """
    try:
        data = get_scoreboard(
            country=country,
            week_from=week_from,
            week_to=week_to
        )
        return {"data": data, "total": len(data)}
    except Exception as e:
        logger.error(f"Error al obtener scoreboard: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener scoreboard: {str(e)}")


@router.get("/backlog")
async def get_backlog_endpoint(
    owner_role: Optional[str] = Query(None, description="Filtrar por rol del owner")
):
    """
    Fase 2C: Backlog de acciones por owner.
    Muestra acciones abiertas, próximas a vencer y vencidas.
    """
    try:
        data = get_backlog(owner_role=owner_role)
        return {"data": data, "total": len(data)}
    except Exception as e:
        logger.error(f"Error al obtener backlog: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener backlog: {str(e)}")


@router.get("/breaches")
async def get_breaches_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    week_start: Optional[str] = Query(None, description="Filtrar por semana (YYYY-MM-DD)")
):
    """
    Fase 2C: Lista de breaches de SLA.
    Muestra alertas críticas sin acción o con acción tardía.
    """
    try:
        data = get_breaches(
            country=country,
            week_start=week_start
        )
        return {"data": data, "total": len(data)}
    except Exception as e:
        logger.error(f"Error al obtener breaches: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener breaches: {str(e)}")


@router.post("/run-snapshot")
async def run_snapshot_endpoint():
    """
    Fase 2C: Ejecuta snapshot de alertas y evaluación de SLA.
    Solo para administradores. Ejecuta el script de snapshot.
    """
    try:
        result = run_snapshot()
        return result
    except Exception as e:
        logger.error(f"Error al ejecutar snapshot: {e}")
        raise HTTPException(status_code=500, detail=f"Error al ejecutar snapshot: {str(e)}")


# ========== FASE 2C+: Universo & LOB Mapping ==========

@router.get("/lob-universe")
async def get_lob_universe_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    lob_name: Optional[str] = Query(None, description="Filtrar por nombre de LOB")
):
    """
    Fase 2C+: Universo LOB - PLAN vs REAL.
    Muestra qué LOB del plan tienen viajes reales y cuáles no.
    Incluye KPIs de cobertura.
    """
    try:
        summary = get_universe_lob_summary(
            country=country,
            city=city,
            lob_name=lob_name
        )
        return summary
    except Exception as e:
        if "does not exist" in str(e).lower():
            logger.debug("Universo LOB: vistas/tablas no creadas aún, devolviendo vacío. %s", e)
        else:
            logger.warning("Universo LOB no disponible: %s", e)
        return {
            "universe": [],
            "has_plan_catalog": False,
            "kpis": {
                "total_lob_plan": 0,
                "lob_with_real": 0,
                "lob_without_real": 0,
                "pct_lob_with_real": 0,
                "total_real_trips": 0,
                "pct_unmatched": 0,
                "total_unmatched": 0,
                "total_trips": 0,
                "count_ok": 0,
                "count_plan_only": 0,
                "count_real_only": 0,
                "pct_real_only": 0
            },
            "quality_metrics": {"pct_unmatched": 0, "total_unmatched": 0, "total_trips": 0},
            "hint": "Vistas/tablas Phase 2C no disponibles. Ejecutar migraciones (ej. 019, 021)."
        }


@router.get("/lob-universe/unmatched")
async def get_unmatched_trips_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad")
):
    """
    Fase 2C+: Viajes reales sin mapeo a LOB del plan.
    Muestra viajes que no encajan en ninguna LOB del plan.
    """
    try:
        summary = get_unmatched_trips_summary(
            country=country,
            city=city
        )
        return summary
    except Exception as e:
        if "does not exist" in str(e).lower():
            logger.debug("Viajes unmatched: vistas no creadas aún, devolviendo vacío. %s", e)
        else:
            logger.warning("Viajes unmatched no disponibles: %s", e)
        return {
            "unmatched_trips": [],
            "unmatched_by_location": [],
            "total_unmatched": 0,
            "total_groups": 0,
            "hint": "Vistas Phase 2C no disponibles. Ejecutar migraciones."
        }
