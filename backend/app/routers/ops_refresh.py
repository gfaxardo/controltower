"""
Router para endpoints de monitoreo de refresh de materialized views.
Prefix: /ops
"""
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.services.refresh_service import (
    get_last_refresh_status,
    get_combined_refresh_status,
    list_refresh_history,
    run_refresh_job,
)

router = APIRouter(tags=["refresh"])


@router.get("/refresh-status")
async def get_refresh_status(
    dataset: Optional[str] = Query(None, description="Nombre del dataset (default: 'all')"),
    threshold_minutes: int = Query(120, description="Minutos para considerar datos stale"),
):
    """
    Obtiene el estado del último refresh de materialized views.
    
    Returns:
        {
            "dataset": str,
            "last_refresh_at": str (ISO datetime),
            "minutes_since_last_refresh": float,
            "status": "fresh" | "stale" | "failed",
            "last_status": "success" | "failed",
            "last_error": str | null,
            "threshold_minutes": int
        }
    """
    try:
        result = get_last_refresh_status(
            dataset_name=dataset,
            threshold_minutes=threshold_minutes,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/refresh-history")
async def get_refresh_history(
    dataset: Optional[str] = Query(None, description="Filtrar por dataset"),
    limit: int = Query(10, description="Cantidad de registros a retornar"),
):
    """
    Lista el historial de refresh de materialized views.
    
    Returns:
        Lista de registros de auditoría ordenados por fecha descendente.
    """
    try:
        result = list_refresh_history(
            dataset_name=dataset,
            limit=limit,
        )
        return {
            "records": result,
            "count": len(result),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-run")
async def trigger_refresh(
    dataset: Optional[str] = Query(None, description="Dataset específico a refrescar (default: todos)"),
):
    """
    Ejecuta manualmente el refresh de materialized views.
    
    Returns:
        Resultado de la operación de refresh.
    """
    try:
        result = run_refresh_job(dataset_name=dataset)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/refresh-status-v2")
async def get_refresh_status_v2(
    dataset: Optional[str] = Query(None, description="Nombre del dataset (default: 'mv_real_trips_monthly')"),
    refresh_threshold_minutes: int = Query(120, description="Minutos para considerar refresh stale"),
    data_threshold_minutes: int = Query(1440, description="Sin uso en modo D-1_CLOSED; reservado por compatibilidad"),
):
    """
    Estado COMBINADO: refresh de MVs + freshness y calidad en modo D-1_CLOSED (solo día cerrado).

    Returns:
        {
            "dataset": str,
            "overall_status": "OK" | "WARNING" | "CRITICAL" | "ERROR" | "UNKNOWN",
            "overall_message": str,
            "refresh": { ... },
            "data": {
                "target_date": str | null,
                "target_date_mode": "D-1_CLOSED",
                "row_count_target_date": int | null,
                "avg_last_7_closed_days": float | null,
                "volume_ratio": float | null,
                "data_quality_status": str,
                "data_status": "fresh" | "stale" | ...
            }
        }
    """
    try:
        result = get_combined_refresh_status(
            dataset_name=dataset,
            refresh_threshold_minutes=refresh_threshold_minutes,
            data_threshold_minutes=data_threshold_minutes,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
