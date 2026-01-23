from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import logging

from app.services.phase2c_accountability_service import (
    get_scoreboard,
    get_backlog,
    get_breaches,
    run_snapshot
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
