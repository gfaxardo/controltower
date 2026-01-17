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
from app.services.plan_real_split_service import (
    get_real_monthly,
    get_plan_monthly,
    get_overlap_monthly
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

@router.get("/real/monthly")
async def get_real_monthly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    lob_base: Optional[str] = Query(None, description="Filtrar por línea de negocio base"),
    segment: Optional[str] = Query(None, description="Filtrar por segmento (b2b, b2c)"),
    year: int = Query(2025, description="Año del Real")
):
    """
    Obtiene datos REAL mensuales agregados desde ops.mv_real_trips_monthly.
    Retorna month, trips_real_completed, revenue_real_proxy, active_drivers_real, avg_ticket_real.
    """
    try:
        data = get_real_monthly(
            country=country,
            city=city,
            lob_base=lob_base,
            segment=segment,
            year=year
        )
        return {
            "data": data,
            "total_periods": len(data),
            "year": year
        }
    except Exception as e:
        logger.error(f"Error al obtener Real monthly: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener Real monthly: {str(e)}")

@router.get("/plan/monthly")
async def get_plan_monthly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    lob_base: Optional[str] = Query(None, description="Filtrar por línea de negocio base"),
    segment: Optional[str] = Query(None, description="Filtrar por segmento (b2b, b2c)"),
    year: int = Query(2026, description="Año del Plan")
):
    """
    Obtiene datos PLAN mensuales agregados desde ops.v_plan_trips_monthly_latest.
    Retorna month, projected_trips, projected_revenue, projected_drivers, projected_ticket.
    """
    try:
        data = get_plan_monthly(
            country=country,
            city=city,
            lob_base=lob_base,
            segment=segment,
            year=year
        )
        return {
            "data": data,
            "total_periods": len(data),
            "year": year
        }
    except Exception as e:
        logger.error(f"Error al obtener Plan monthly: {e}")
        raise HTTPException(status_code=500, detail=f"Error al obtener Plan monthly: {str(e)}")

@router.get("/compare/overlap-monthly")
async def get_overlap_monthly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    lob_base: Optional[str] = Query(None, description="Filtrar por línea de negocio base"),
    segment: Optional[str] = Query(None, description="Filtrar por segmento (b2b, b2c)"),
    year: Optional[int] = Query(None, description="Año específico para overlap (opcional)")
):
    """
    Obtiene comparación Plan vs Real SOLO para meses donde hay overlap temporal.
    Retorna lista vacía si no hay overlap, sin error.
    """
    try:
        data = get_overlap_monthly(
            country=country,
            city=city,
            lob_base=lob_base,
            segment=segment,
            year=year
        )
        return {
            "data": data,
            "total_periods": len(data),
            "has_overlap": len(data) > 0
        }
    except Exception as e:
        logger.error(f"Error al obtener overlap monthly: {e}")
        # Tolerante: retornar lista vacía en caso de error
        return {
            "data": [],
            "total_periods": 0,
            "has_overlap": False,
            "error": str(e)
        }
