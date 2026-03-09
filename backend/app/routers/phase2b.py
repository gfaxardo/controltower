from fastapi import APIRouter, Query, HTTPException, Body
from typing import Optional
import logging
from datetime import date
from uuid import UUID

from app.services.phase2b_weekly_service import (
    get_plan_vs_real_weekly,
    get_alerts_weekly
)
from app.services.phase2b_actions_service import (
    create_action,
    get_actions,
    get_action_by_id,
    update_action,
    mark_missed_actions
)
from app.models.schemas import (
    Phase2BActionCreate,
    Phase2BActionUpdate,
    Phase2BActionResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phase2b", tags=["phase2b"])


@router.get("/weekly/plan-vs-real")
async def get_plan_vs_real_weekly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad (usa city_norm)"),
    lob_base: Optional[str] = Query(None, description="Filtrar por línea de negocio base"),
    segment: Optional[str] = Query(None, description="Filtrar por segmento (b2b, b2c)"),
    week_start_from: Optional[str] = Query(None, description="Semana desde (YYYY-MM-DD)"),
    week_start_to: Optional[str] = Query(None, description="Semana hasta (YYYY-MM-DD)")
):
    """
    Fase 2B semanal: Plan vs Real (explicable).
    """
    try:
        data = get_plan_vs_real_weekly(
            country=country,
            city=city,
            lob_base=lob_base,
            segment=segment,
            week_start_from=week_start_from,
            week_start_to=week_start_to
        )
        return {"data": data, "total_records": len(data)}
    except Exception as e:
        logger.warning(f"Plan vs Real semanal (vista ops.v_plan_vs_real_weekly puede no existir): {e}")
        # Si la vista no existe en la BD, devolver vacío para que la UI no rompa
        return {"data": [], "total_records": 0, "hint": "Vista ops.v_plan_vs_real_weekly no disponible. Ejecutar migraciones Phase 2B."}


@router.get("/weekly/alerts")
async def get_alerts_weekly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad (usa city_norm)"),
    lob_base: Optional[str] = Query(None, description="Filtrar por línea de negocio base"),
    segment: Optional[str] = Query(None, description="Filtrar por segmento (b2b, b2c)"),
    week_start_from: Optional[str] = Query(None, description="Semana desde (YYYY-MM-DD)"),
    week_start_to: Optional[str] = Query(None, description="Semana hasta (YYYY-MM-DD)"),
    dominant_driver: Optional[str] = Query(None, description="Filtrar por driver dominante (UNIT/VOL)"),
    unit_alert: Optional[bool] = Query(None, description="Filtrar solo alertas unitarias (true/false)")
):
    """
    Fase 2B semanal: alertas accionables.
    Ordenado por severity_score (prioriza money).
    """
    try:
        data = get_alerts_weekly(
            country=country,
            city=city,
            lob_base=lob_base,
            segment=segment,
            week_start_from=week_start_from,
            week_start_to=week_start_to,
            dominant_driver=dominant_driver,
            unit_alert=unit_alert
        )
        return {"data": data, "total_alerts": len(data)}
    except Exception as e:
        logger.warning(f"Alertas semanales (vista ops.v_alerts_2b_weekly puede no existir): {e}")
        return {"data": [], "total_alerts": 0, "hint": "Vista ops.v_alerts_2b_weekly no disponible. Ejecutar migraciones Phase 2B."}


@router.post("/actions", response_model=Phase2BActionResponse)
async def create_action_endpoint(action: Phase2BActionCreate):
    """
    Crea una nueva acción para una alerta.
    """
    try:
        result = create_action(
            week_start=action.week_start,
            country=action.country,
            city_norm=action.city_norm,
            lob_base=action.lob_base,
            segment=action.segment,
            alert_type=action.alert_type,
            root_cause=action.root_cause,
            action_type=action.action_type,
            action_description=action.action_description,
            owner_role=action.owner_role,
            owner_user_id=action.owner_user_id,
            due_date=action.due_date
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al crear acción: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear acción: {str(e)}")


@router.get("/actions", response_model=dict)
async def get_actions_endpoint(
    week_start: Optional[str] = Query(None, description="Filtrar por semana (YYYY-MM-DD)"),
    owner_role: Optional[str] = Query(None, description="Filtrar por rol del owner"),
    status: Optional[str] = Query(None, description="Filtrar por status (OPEN, IN_PROGRESS, DONE, MISSED)")
):
    """
    Obtiene acciones con filtros opcionales.
    """
    try:
        week_start_date = None
        if week_start:
            week_start_date = date.fromisoformat(week_start)
        
        data = get_actions(
            week_start=week_start_date,
            owner_role=owner_role,
            status=status
        )
        return {"data": data, "total": len(data)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Formato de fecha inválido: {str(e)}")
    except Exception as e:
        logger.error(f"Error al obtener acciones: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener acciones: {str(e)}")


@router.patch("/actions/{action_id}", response_model=Phase2BActionResponse)
async def update_action_endpoint(
    action_id: int,
    action_update: Phase2BActionUpdate
):
    """
    Actualiza una acción (solo status y description).
    No permite modificar acciones con status DONE.
    """
    try:
        result = update_action(
            action_id=action_id,
            status=action_update.status,
            action_description=action_update.action_description
        )
        if not result:
            raise HTTPException(status_code=404, detail="Acción no encontrada")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al actualizar acción: {e}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar acción: {str(e)}")


@router.post("/actions/mark-missed")
async def mark_missed_actions_endpoint():
    """
    Auto-marca acciones como MISSED si due_date < today y status != DONE.
    Se ejecuta automáticamente al consultar acciones, pero puede llamarse manualmente.
    """
    try:
        count = mark_missed_actions()
        return {"message": f"Marcadas {count} acciones como MISSED", "count": count}
    except Exception as e:
        logger.error(f"Error al marcar acciones MISSED: {e}")
        raise HTTPException(status_code=500, detail=f"Error al marcar acciones MISSED: {str(e)}")
