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
from app.services.real_lob_service import (
    get_real_lob_monthly as get_real_lob_monthly_svc,
    get_real_lob_weekly as get_real_lob_weekly_svc,
    get_real_lob_meta,
)
from app.services.real_lob_service_v2 import (
    get_real_lob_monthly_v2,
    get_real_lob_weekly_v2,
    get_real_lob_meta_v2,
)
from app.services.real_lob_filters_service import get_real_lob_filters
from app.services.real_lob_v2_data_service import get_real_lob_v2_data
from app.services.real_strategy_service import (
    get_real_strategy_country,
    get_real_strategy_lob,
    get_real_strategy_cities,
)
from app.settings import settings
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
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    real_tipo_servicio: Optional[str] = Query(None, description="Filtrar por tipo de servicio (dimensión real)"),
    park_id: Optional[str] = Query(None, description="Filtrar por park_id"),
    month: Optional[str] = Query(None, description="Filtrar por mes (formato: YYYY-MM o YYYY-MM-DD)")
):
    """
    Obtiene comparación Plan vs Real mensual desde ops.v_plan_vs_real_realkey_final.
    Llave: (country, city, park_id, real_tipo_servicio, period_date). Sin LOB/homologación.
    """
    try:
        data = get_plan_vs_real_monthly(
            country=country,
            city=city,
            real_tipo_servicio=real_tipo_servicio,
            park_id=park_id,
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
    Obtiene alertas Plan vs Real desde ops.v_plan_vs_real_realkey_final (solo matched).
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

def _real_lob_meta():
    meta = get_real_lob_meta()
    return {
        "last_available_month": meta.get("max_month"),
        "last_available_week": meta.get("max_week"),
    }


@router.get("/real-lob/monthly")
async def get_real_lob_monthly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    lob_name: Optional[str] = Query(None, description="Filtrar por LOB"),
    month: Optional[str] = Query(None, description="Filtrar por mes YYYY-MM; si vacío, último mes disponible"),
    year_real: Optional[int] = Query(None, description="Filtrar por año (todos los meses del año)")
):
    """
    REAL LOB Observability: viajes REAL agregados por LOB (mensual).
    Sin month ni year_real: devuelve el último mes disponible.
    """
    try:
        data = get_real_lob_monthly_svc(
            country=country, city=city, lob_name=lob_name, month=month, year_real=year_real
        )
        meta = _real_lob_meta()
        resp = {"data": data, "total_records": len(data), **meta}
        if not data:
            resp["reason"] = "no_data_for_filters"
        return resp
    except Exception as e:
        logger.error(f"Error Real LOB monthly: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/weekly")
async def get_real_lob_weekly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    lob_name: Optional[str] = Query(None, description="Filtrar por LOB"),
    week_start: Optional[str] = Query(None, description="Lunes de la semana YYYY-MM-DD; si vacío, última semana disponible"),
    year_real: Optional[int] = Query(None, description="Filtrar por año (todas las semanas del año)")
):
    """
    REAL LOB Observability: viajes REAL agregados por LOB (semanal).
    Sin week_start ni year_real: devuelve la última semana disponible.
    """
    try:
        data = get_real_lob_weekly_svc(
            country=country, city=city, lob_name=lob_name, week_start=week_start, year_real=year_real
        )
        meta = _real_lob_meta()
        resp = {"data": data, "total_records": len(data), **meta}
        if not data:
            resp["reason"] = "no_data_for_filters"
        return resp
    except Exception as e:
        logger.error(f"Error Real LOB weekly: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/debug")
async def get_real_lob_debug_endpoint():
    """
    Devuelve max_month, max_week, count_month, count_week. Solo disponible en entorno dev.
    """
    env = (getattr(settings, "ENVIRONMENT", "") or "").lower()
    if env not in ("dev", "development"):
        raise HTTPException(status_code=404, detail="Solo disponible en desarrollo")
    try:
        return get_real_lob_meta()
    except Exception as e:
        logger.error(f"Error Real LOB debug: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _real_lob_meta_v2():
    meta = get_real_lob_meta_v2()
    return {"last_available_month": meta.get("max_month"), "last_available_week": meta.get("max_week")}


@router.get("/real-lob/monthly-v2")
async def get_real_lob_monthly_v2_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    park_id: Optional[str] = Query(None, description="Filtrar por park_id"),
    lob_group: Optional[str] = Query(None, description="LOB_GROUP: auto taxi, delivery, tuk tuk, taxi moto, UNCLASSIFIED"),
    real_tipo_servicio: Optional[str] = Query(None, description="Tipo de servicio normalizado"),
    segment_tag: Optional[str] = Query(None, description="Segmento: B2B o B2C"),
    month: Optional[str] = Query(None, description="Mes YYYY-MM; si vacío, último mes"),
    year_real: Optional[int] = Query(None, description="Año (rango de meses)")
):
    """Real LOB v2: mensual con filtros country, city, park_id, lob_group, real_tipo_servicio, segment_tag."""
    try:
        data = get_real_lob_monthly_v2(
            country=country, city=city, park_id=park_id,
            lob_group=lob_group, real_tipo_servicio=real_tipo_servicio, segment_tag=segment_tag,
            month=month, year_real=year_real
        )
        meta = _real_lob_meta_v2()
        resp = {"data": data, "total_records": len(data), **meta}
        if not data:
            resp["reason"] = "no_data_for_filters"
        return resp
    except Exception as e:
        logger.error(f"Error Real LOB monthly v2: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/weekly-v2")
async def get_real_lob_weekly_v2_endpoint(
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    lob_group: Optional[str] = Query(None),
    real_tipo_servicio: Optional[str] = Query(None),
    segment_tag: Optional[str] = Query(None),
    week_start: Optional[str] = Query(None, description="Lunes semana YYYY-MM-DD"),
    year_real: Optional[int] = Query(None)
):
    """Real LOB v2: semanal con mismos filtros."""
    try:
        data = get_real_lob_weekly_v2(
            country=country, city=city, park_id=park_id,
            lob_group=lob_group, real_tipo_servicio=real_tipo_servicio, segment_tag=segment_tag,
            week_start=week_start, year_real=year_real
        )
        meta = _real_lob_meta_v2()
        resp = {"data": data, "total_records": len(data), **meta}
        if not data:
            resp["reason"] = "no_data_for_filters"
        return resp
    except Exception as e:
        logger.error(f"Error Real LOB weekly v2: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/filters")
async def get_real_lob_filters_endpoint(
    country: Optional[str] = Query(None, description="Filtrar ciudades/parks por país"),
    city: Optional[str] = Query(None, description="Filtrar parks por ciudad"),
):
    """Opciones para dropdowns: countries, cities, parks, lob_groups, tipo_servicio, segments, years. Cache 5 min."""
    try:
        return get_real_lob_filters(country=country, city=city)
    except Exception as e:
        logger.error(f"Error Real LOB filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/v2/data")
async def get_real_lob_v2_data_endpoint(
    period_type: Literal["monthly", "weekly"] = Query("monthly"),
    agg_level: str = Query("DETALLE", description="DETALLE|TOTAL_PAIS|TOTAL_CIUDAD|TOTAL_PARK|PARK_X_MES|PARK_X_MES_X_LOB|PARK_X_SEMANA|PARK_X_SEMANA_X_LOB"),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    lob_group: Optional[str] = Query(None),
    tipo_servicio: Optional[str] = Query(None),
    segment_tag: Optional[str] = Query(None, description="Todos|B2B|B2C"),
    year: Optional[int] = Query(None, description="Año; si vacío, últimos 12 meses"),
):
    """Datos Real LOB v2 con consolidación. Devuelve totals (trips, b2b_ratio, rows), rows y meta."""
    try:
        return get_real_lob_v2_data(
            period_type=period_type,
            agg_level=agg_level,
            country=country,
            city=city,
            park_id=park_id,
            lob_group=lob_group,
            tipo_servicio=tipo_servicio,
            segment_tag=segment_tag,
            year=year,
        )
    except Exception as e:
        logger.error(f"Error Real LOB v2 data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Real LOB Strategy (KPIs ejecutivos, forecast, rankings) ─────────────────
@router.get("/real-strategy/country")
async def get_real_strategy_country_endpoint(
    country: str = Query(..., description="País (requerido)"),
    year_real: Optional[int] = Query(None, description="Año para filtrar (opcional)"),
    segment_tag: Optional[Literal["B2B", "B2C"]] = Query(None, description="Segmento B2B/B2C (opcional)"),
    period_type: str = Query("monthly", description="Tipo de periodo (monthly por defecto)"),
):
    """
    KPIs estratégicos por país: total_trips_ytd, growth_mom, b2b_ratio, forecast_next_month,
    acceleration_index, concentration_index. Incluye tendencia 12 meses y ranking ciudades.
    """
    try:
        return get_real_strategy_country(
            country=country,
            year_real=year_real,
            segment_tag=segment_tag,
            period_type=period_type,
        )
    except Exception as e:
        logger.error(f"Error Real strategy country: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-strategy/lob")
async def get_real_strategy_lob_endpoint(
    country: str = Query(..., description="País (requerido)"),
    year_real: Optional[int] = Query(None, description="Año para filtrar (opcional)"),
    segment_tag: Optional[Literal["B2B", "B2C"]] = Query(None, description="Segmento B2B/B2C (opcional)"),
    lob_group: Optional[str] = Query(None, description="Filtrar por LOB_GROUP (opcional)"),
    period_type: str = Query("monthly", description="Tipo de periodo (monthly por defecto)"),
):
    """
    Distribución LOB por país: trips, participation_pct, growth_mom, forecast_next_month, momentum_score.
    """
    try:
        return get_real_strategy_lob(
            country=country,
            year_real=year_real,
            segment_tag=segment_tag,
            lob_group=lob_group,
            period_type=period_type,
        )
    except Exception as e:
        logger.error(f"Error Real strategy LOB: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-strategy/cities")
async def get_real_strategy_cities_endpoint(
    country: str = Query(..., description="País (requerido)"),
    year_real: Optional[int] = Query(None, description="Año para filtrar (opcional)"),
    segment_tag: Optional[Literal["B2B", "B2C"]] = Query(None, description="Segmento B2B/B2C (opcional)"),
    period_type: str = Query("monthly", description="Tipo de periodo (monthly por defecto)"),
):
    """
    Ranking ciudades por país: city, trips, growth_mom, % país, expansion_index.
    """
    try:
        return get_real_strategy_cities(
            country=country,
            year_real=year_real,
            segment_tag=segment_tag,
            period_type=period_type,
        )
    except Exception as e:
        logger.error(f"Error Real strategy cities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real/monthly")
async def get_real_monthly_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
    lob_base: Optional[str] = Query(None, description="Filtrar por línea de negocio base"),
    segment: Optional[str] = Query(None, description="Filtrar por segmento (b2b, b2c)"),
    year: int = Query(2025, description="Año del Real")
):
    """
    Obtiene datos REAL mensuales agregados desde ops.mv_real_trips_monthly (sin proxies).
    Retorna month, trips_real_completed, revenue_real_yego, active_drivers_real, avg_ticket_real.
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