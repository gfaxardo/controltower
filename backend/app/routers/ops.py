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
from app.services.real_drill_service import (
    get_real_drill_summary,
    get_real_drill_summary_countries,
    get_real_drill_by_lob,
    get_real_drill_by_park,
    get_real_drill_totals,
    get_real_drill_meta,
    get_real_drill_coverage,
    refresh_real_drill_mv,
    RealDrillMvNotPopulatedError,
)
from app.services.real_lob_drill_pro_service import get_drill as get_real_lob_drill_pro, get_drill_children as get_real_lob_drill_pro_children
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


# ─── Real LOB Drill PRO (MV ops.mv_real_lob_drill_agg; calendario completo, KPIs por país) ─────────────────
@router.get("/real-lob/drill")
async def get_real_lob_drill_pro_endpoint(
    period: Literal["month", "week"] = Query("month", description="month | week"),
    desglose: Literal["LOB", "PARK"] = Query("PARK", description="Desglose al expandir: LOB | PARK"),
    segmento: Optional[Literal["all", "b2c", "b2b"]] = Query("all", description="all | b2c | b2b"),
    country: Optional[Literal["all", "pe", "co"]] = Query("all", description="all | pe | co"),
):
    """
    Real LOB Drill PRO: countries[] con coverage, kpis (sobre lo visible), rows por periodo.
    Orden: PE primero, CO segundo; filas periodo más reciente → más antiguo.
    """
    try:
        return get_real_lob_drill_pro(
            period=period,
            desglose=desglose,
            segmento=segmento,
            country=country,
        )
    except Exception as e:
        logger.error("Real LOB drill PRO: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/drill/children")
async def get_real_lob_drill_children_endpoint(
    country: str = Query(..., description="País (pe | co)"),
    period: Literal["month", "week"] = Query("month"),
    period_start: str = Query(..., description="YYYY-MM-DD o YYYY-MM-01"),
    desglose: Literal["LOB", "PARK"] = Query("PARK"),
    segmento: Optional[Literal["all", "b2c", "b2b"]] = Query("all"),
    drill_lob_id: Optional[str] = Query(None, description="Filtro LOB (solo válido si desglose=LOB)"),
    drill_park_id: Optional[str] = Query(None, description="Filtro Park (solo válido si desglose=PARK)"),
):
    """
    Desglose por Park (city, park_name) o LOB (lob_group, tipo_servicio_norm). Orden: viajes DESC.

    Contrato params por dimensión (FASE 2D):
    - desglose=LOB  => permitido drill_lob_id; 400 si llega drill_park_id.
    - desglose=PARK => permitido drill_park_id; 400 si llega drill_lob_id.
    """
    if desglose == "PARK" and drill_lob_id is not None and str(drill_lob_id).strip() != "":
        raise HTTPException(
            status_code=400,
            detail="Incompatible drill params for groupBy=PARK: drill_lob_id is not allowed when desglose is PARK.",
        )
    if desglose == "LOB" and drill_park_id is not None and str(drill_park_id).strip() != "":
        raise HTTPException(
            status_code=400,
            detail="Incompatible drill params for groupBy=LOB: drill_park_id is not allowed when desglose is LOB.",
        )
    try:
        data = get_real_lob_drill_pro_children(
            country=country,
            period=period,
            period_start=period_start,
            desglose=desglose,
            segmento=segmento,
        )
        return {"data": data}
    except Exception as e:
        logger.error("Real LOB drill PRO children: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Real LOB Drill-down (timeline por país, drill LOB/Park) [legacy; preferir /real-lob/drill] ─────────────────
@router.get("/real-drill/summary")
async def get_real_drill_summary_endpoint(
    period_type: Literal["monthly", "weekly"] = Query("monthly", description="monthly | weekly"),
    segment: Optional[Literal["Todos", "B2B", "B2C"]] = Query("Todos", description="Todos | B2B | B2C"),
    limit_periods: Optional[int] = Query(None, description="Máx periodos (default 24 meses o 26 semanas)"),
):
    """
    Timeline por país: countries[] con coverage, kpis (sobre lo visible) y rows.
    Orden: PE primero, CO segundo. KPIs calculados sobre los periodos devueltos.
    """
    try:
        seg = None if segment == "Todos" else segment
        result = get_real_drill_summary_countries(
            period_type=period_type,
            segment=seg,
            limit_periods=limit_periods,
        )
        return result
    except RealDrillMvNotPopulatedError as e:
        return {
            "countries": [
                {"country": "pe", "coverage": {}, "kpis": {}, "rows": []},
                {"country": "co", "coverage": {}, "kpis": {}, "rows": []},
            ],
            "meta": {
                "last_period_monthly": None,
                "last_period_weekly": None,
                "hint": e.hint,
            },
        }
    except Exception as e:
        logger.error("Real drill summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-drill/by-lob")
async def get_real_drill_by_lob_endpoint(
    period_type: Literal["monthly", "weekly"] = Query("monthly"),
    country: str = Query(..., description="País (requerido)"),
    period_start: str = Query(..., description="Fecha inicio periodo (YYYY-MM-DD o YYYY-MM)"),
    segment: Optional[Literal["Todos", "B2B", "B2C"]] = Query("Todos"),
):
    """Desglose por LOB para un país y periodo. Orden: trips DESC."""
    try:
        seg = None if segment == "Todos" else segment
        data = get_real_drill_by_lob(
            period_type=period_type,
            country=country,
            period_start=period_start,
            segment=seg,
        )
        meta = get_real_drill_meta()
        return {
            "data": data,
            "meta": {
                "last_period_monthly": meta.get("last_period_monthly"),
                "last_period_weekly": meta.get("last_period_weekly"),
            },
        }
    except RealDrillMvNotPopulatedError as e:
        return {
            "data": [],
            "meta": {"last_period_monthly": None, "last_period_weekly": None, "hint": e.hint},
        }
    except Exception as e:
        logger.error("Real drill by-lob: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-drill/by-park")
async def get_real_drill_by_park_endpoint(
    period_type: Literal["monthly", "weekly"] = Query("monthly"),
    country: str = Query(..., description="País (requerido)"),
    period_start: str = Query(..., description="Fecha inicio periodo (YYYY-MM-DD)"),
    segment: Optional[Literal["Todos", "B2B", "B2C"]] = Query("Todos"),
):
    """Desglose por park para un país y periodo. Orden: trips DESC."""
    try:
        seg = None if segment == "Todos" else segment
        data = get_real_drill_by_park(
            period_type=period_type,
            country=country,
            period_start=period_start,
            segment=seg,
        )
        meta = get_real_drill_meta()
        return {
            "data": data,
            "meta": {
                "last_period_monthly": meta.get("last_period_monthly"),
                "last_period_weekly": meta.get("last_period_weekly"),
            },
        }
    except RealDrillMvNotPopulatedError as e:
        return {
            "data": [],
            "meta": {"last_period_monthly": None, "last_period_weekly": None, "hint": e.hint},
        }
    except Exception as e:
        logger.error("Real drill by-park: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/real-drill/refresh")
async def refresh_real_drill_endpoint():
    """
    Refresca la MV ops.mv_real_rollup_day. Uso interno (cron, admin).
    Ejecuta REFRESH MATERIALIZED VIEW CONCURRENTLY.
    """
    try:
        return refresh_real_drill_mv()
    except Exception as e:
        logger.error("Real drill refresh: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-drill/coverage")
async def get_real_drill_coverage_endpoint():
    """Cobertura por país: last_trip_date, last_month_with_data, last_week_with_data."""
    try:
        data = get_real_drill_coverage()
        return {"data": data}
    except Exception as e:
        msg = str(e) or ""
        if "does not exist" in msg or "relation" in msg.lower() or "aborted" in msg.lower():
            return {"data": []}
        logger.error("Real drill coverage: %s", e)
        raise HTTPException(status_code=500, detail=msg)


@router.get("/real-drill/totals")
async def get_real_drill_totals_endpoint(
    period_type: Literal["monthly", "weekly"] = Query("monthly"),
    segment: Optional[Literal["Todos", "B2B", "B2C"]] = Query("Todos"),
    limit_periods: Optional[int] = Query(None),
):
    """Totales (total_trips, b2b_ratio) sobre el rango mostrado en summary."""
    try:
        seg = None if segment == "Todos" else segment
        data = get_real_drill_totals(
            period_type=period_type,
            segment=seg,
            limit_periods=limit_periods,
        )
        return data
    except RealDrillMvNotPopulatedError as e:
        return {
            "total_trips": 0,
            "total_b2b_trips": 0,
            "b2b_ratio_pct": None,
            "margin_total": None,
            "margin_unit_avg_global": None,
            "distance_total_km": None,
            "distance_km_avg_global": None,
            "last_trip_ts": None,
            "hint": e.hint,
        }
    except Exception as e:
        logger.error("Real drill totals: %s", e)
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
