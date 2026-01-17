from fastapi import APIRouter, Query, HTTPException
from app.services.ops_universe_service import get_ops_universe
from app.services.territory_quality_service import (
    get_territory_kpis_total,
    get_territory_kpis_weekly,
    get_unmapped_parks
)
from app.services.plan_vs_real_service import (
    get_plan_vs_real_monthly,
    get_alerts_monthly
)
from typing import Optional, Literal
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops"])

@router.get("/universe")
async def get_universe(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad")
):
    """
    Retorna el universo operativo: combinaciones (country, city, line_of_business)
    válidas con actividad real en 2025.
    Soporta filtros opcionales por country y city.
    """
    try:
        universe = get_ops_universe(country=country, city=city)
        return {
            "data": universe,
            "total_combinations": len(universe)
        }
    except Exception as e:
        logger.error(f"Error al obtener universo operativo: {e}")
        raise

@router.get("/territory-quality/kpis")
async def get_territory_quality_kpis(
    granularity: Literal["total", "weekly"] = Query("total", description="Granularidad: total o weekly")
):
    """
    Obtiene KPIs de calidad de mapeo territorial.
    """
    try:
        if granularity == "total":
            kpis = get_territory_kpis_total()
            return {
                "granularity": "total",
                "data": kpis
            }
        else:  # weekly
            kpis = get_territory_kpis_weekly()
            return {
                "granularity": "weekly",
                "data": kpis,
                "total_weeks": len(kpis)
            }
    except Exception as e:
        logger.error(f"Error al obtener KPIs de territorio: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener KPIs de territorio: {str(e)}")

@router.get("/territory-quality/unmapped-parks")
async def get_unmapped_parks_endpoint(
    limit: int = Query(50, description="Límite de resultados", ge=1, le=500)
):
    """
    Obtiene parks que aparecen en trips_all pero no tienen mapeo en dim.dim_park.
    Ordenados por cantidad de trips (descendente).
    """
    try:
        parks = get_unmapped_parks(limit=limit)
        return {
            "data": parks,
            "total_parks": len(parks),
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error al obtener parks unmapped: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener parks unmapped: {str(e)}")

@router.get("/plan-vs-real/monthly")
async def get_plan_vs_real_monthly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad (usa city_norm_real para matching)"),
    lob_base: Optional[str] = Query(None, description="Filtrar por línea de negocio base"),
    segment: Optional[str] = Query(None, description="Filtrar por segmento (b2b, b2c)"),
    month: Optional[str] = Query(None, description="Filtrar por mes (formato: YYYY-MM o YYYY-MM-DD)")
):
    """
    Obtiene comparación Plan vs Real mensual desde ops.v_plan_vs_real_monthly_latest.
    Incluye FULL OUTER JOIN para no perder universo (plan_only, real_only, matched).
    """
    try:
        data = get_plan_vs_real_monthly(
            country=country,
            city=city,
            lob_base=lob_base,
            segment=segment,
            month=month
        )
        return {
            "data": data,
            "total_records": len(data)
        }
    except Exception as e:
        logger.error(f"Error al obtener comparación Plan vs Real: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener comparación Plan vs Real: {str(e)}")

@router.get("/plan-vs-real/alerts")
async def get_plan_vs_real_alerts_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    month: Optional[str] = Query(None, description="Filtrar por mes (formato: YYYY-MM o YYYY-MM-DD)"),
    alert_level: Optional[str] = Query(None, description="Filtrar por nivel de alerta (CRITICO, MEDIO, OK)")
):
    """
    Obtiene alertas Plan vs Real desde ops.v_plan_vs_real_alerts_monthly_latest.
    Solo incluye registros matched (has_plan AND has_real).
    Alertas ordenadas por severidad: CRITICO > MEDIO > OK.
    """
    try:
        data = get_alerts_monthly(
            country=country,
            month=month,
            alert_level=alert_level
        )
        return {
            "data": data,
            "total_alerts": len(data),
            "by_level": {
                "CRITICO": len([a for a in data if a.get("alert_level") == "CRITICO"]),
                "MEDIO": len([a for a in data if a.get("alert_level") == "MEDIO"]),
                "OK": len([a for a in data if a.get("alert_level") == "OK"])
            }
        }
    except Exception as e:
        logger.error(f"Error al obtener alertas Plan vs Real: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener alertas Plan vs Real: {str(e)}")

