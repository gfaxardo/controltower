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
from app.services.refresh_control_service import (
    get_refresh_status as get_refresh_control_status,
)
from app.services.period_closure_service import (
    get_period_closure_status,
    get_period_readiness,
)
from app.services.last_good_data_service import (
    create_snapshot_for_period,
    get_active_snapshot,
    get_serving_source,
    validate_snapshot,
)

router = APIRouter(tags=["refresh"])


@router.get("/refresh/status")
async def get_refresh_control_status_endpoint(
    refresh_name: Optional[str] = Query(None, description="Filtrar por refresh_name (ej: supply_refresh_pipeline)"),
    pipeline_name: Optional[str] = Query(None, description="Filtrar por pipeline_name (ej: supply_refresh)"),
    limit: int = Query(20, ge=1, le=100, description="Cantidad máxima de resultados"),
):
    """
    Estado de refrescos Fase 1B — Refresh Run Log.

    Devuelve las últimas corridas registradas en ops.refresh_run_log
    con metadata de lock, scope, periodo y resultado.

    Campos por registro:
      - refresh_name, pipeline_name, step_name
      - status: success | failed | skipped | blocked
      - started_at, finished_at, duration_seconds
      - lock_acquired, source_max_date
      - period_start, period_end, period_status
      - warning_message, error_message

    stale_warning = true si la última corrida falló, fue skipped/blocked,
    o si no hay registros para el refresh_name solicitado.
    """
    try:
        return get_refresh_control_status(
            refresh_name=refresh_name,
            pipeline_name=pipeline_name,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# ── Period Closure (Fase 1D) ──

@router.get("/period-closure/status")
async def get_period_closure_status_endpoint(
    grain: Optional[str] = Query(None, description="Filtrar por grain: daily, weekly, monthly, ytd"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Estado de cierre de periodos (Fase 1D).
    Devuelve los últimos periodos registrados en ops.period_closure_registry.
    """
    try:
        return get_period_closure_status(grain=grain, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/period-closure/readiness")
async def get_period_closure_readiness_endpoint(
    grain: str = Query(..., description="daily | weekly | monthly"),
    period: str = Query(..., description="YYYY-MM del periodo a evaluar"),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
):
    """
    Evalúa si un periodo puede cerrarse. Retorna can_close, blockers, warnings, qa_summary.
    """
    try:
        return get_period_readiness(grain=grain, period_start=period, country=country, city=city)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Serving Status (Fase 1E) ──

@router.get("/serving/status")
async def get_serving_status_endpoint(
    grain: str = Query("monthly", description="monthly | weekly | daily"),
    period: Optional[str] = Query(None, description="YYYY-MM. Default: mes actual."),
):
    """
    Estado de serving para un periodo (Fase 1E).
    Indica si se sirve desde snapshot, working fact, o si hay fallback.
    """
    from datetime import date as _d
    try:
        ps = _d.today().replace(day=1) if not period else _d.fromisoformat(str(period)[:10] if len(str(period)) >= 10 else str(period) + "-01")
        source = get_serving_source(grain=grain, period_start=ps)
        snap = get_active_snapshot(grain=grain, period_start=ps)
        return {**source, "snapshot_detail": snap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/serving/snapshots")
async def get_serving_snapshots_endpoint(
    grain: str = Query("monthly"),
    period: Optional[str] = Query(None, description="YYYY-MM"),
):
    """
    Lista snapshots disponibles para un periodo (Fase 1E).
    """
    from datetime import date as _d
    try:
        ps = _d.today().replace(day=1) if not period else _d.fromisoformat(str(period)[:10] if len(str(period)) >= 10 else str(period) + "-01")
        snap = get_active_snapshot(grain=grain, period_start=ps)
        return {"snapshots": [snap] if snap.get("active") else [], "period": str(ps)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
