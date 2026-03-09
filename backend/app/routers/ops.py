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
from app.services.real_lob_drill_pro_service import (
    get_drill as get_real_lob_drill_pro,
    get_drill_children as get_real_lob_drill_pro_children,
    get_drill_parks as get_real_lob_drill_parks,
)
from app.services.period_semantics_service import get_period_semantics
from app.services.comparative_metrics_service import (
    get_weekly_comparative,
    get_monthly_comparative,
)
from app.services.real_lob_daily_service import (
    get_daily_summary,
    get_daily_comparative,
    get_daily_table,
)
from app.services.supply_service import (
    get_supply_geo,
    get_supply_parks,
    get_supply_series,
    get_supply_summary,
    get_supply_global_series,
    get_supply_segments_series,
    get_supply_segment_config,
    get_supply_alerts,
    get_supply_alert_drilldown,
    refresh_supply_alerting_mvs,
    get_supply_overview_enhanced,
    get_supply_composition,
    get_supply_migration,
    get_supply_migration_drilldown,
    get_supply_freshness,
)
from app.services.data_freshness_service import (
    get_freshness_audit,
    get_freshness_alerts,
    get_freshness_expectations,
)
from app.services.supply_definitions import get_definitions
from app.settings import settings
from fastapi.responses import Response
from typing import Optional, Literal
import asyncio
import functools
import csv
import io
import json
import logging
import os
import sys
import time

# Ejecutar función síncrona en thread pool (compatible Python 3.8+; no usar asyncio.to_thread que es 3.9+)
async def _run_sync(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

logger = logging.getLogger(__name__)
logger.info("ops router: _run_sync uses run_in_executor (Python 3.8 compatible)")
# #region agent log
def _debug_log(location: str, message: str, data: dict, hypothesis_id: str):
    try:
        log_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "debug-1c8c83.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId": "1c8c83", "timestamp": int(time.time() * 1000), "location": location, "message": message, "data": data, "hypothesisId": hypothesis_id}) + "\n")
    except Exception:
        pass
# #endregion

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


@router.get("/parks")
async def get_ops_parks(
    country: Optional[str] = Query(None, description="Filtrar por país (mismo criterio que Real LOB)"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
):
    """
    Lista de parks para dropdowns (Driver Lifecycle, etc.).
    Misma fuente y orden que Real LOB: [{ park_id, park_name }].
    La opción "Todos" se arma en frontend.
    """
    try:
        filters = get_real_lob_filters(country=country, city=city)
        parks = filters.get("parks") or []
        return {
            "parks": [
                {"park_id": p.get("park_id"), "park_name": p.get("park_name") or str(p.get("park_id") or "")}
                for p in parks
            ]
        }
    except Exception as e:
        logger.error("GET /ops/parks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Control Tower Supply (REAL) ─────────────────────────────────────────────
@router.get("/supply/geo")
async def get_supply_geo_endpoint(
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
):
    """Geo para filtros: countries, cities (por country), parks (por country/city). Fuente: dim.v_geo_park."""
    try:
        return get_supply_geo(country=country, city=city)
    except Exception as e:
        logger.error("GET /ops/supply/geo: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/parks")
async def get_supply_parks_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país"),
    city: Optional[str] = Query(None, description="Filtrar por ciudad"),
):
    """Parks para Supply (geo). Fuente: dim.v_geo_park. Orden: country, city, park_name."""
    try:
        data = get_supply_parks(country=country, city=city)
        return {"data": data}
    except Exception as e:
        logger.error("GET /ops/supply/parks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _to_csv(rows: list, columns: list) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([r.get(c) for c in columns])
    return buf.getvalue()


@router.get("/supply/series")
async def get_supply_series_endpoint(
    park_id: str = Query(..., description="Park (obligatorio)"),
    from_: str = Query(..., alias="from", description="Fecha inicio YYYY-MM-DD"),
    to: str = Query(..., description="Fecha fin YYYY-MM-DD"),
    grain: Literal["weekly", "monthly"] = Query("weekly"),
    format: Optional[str] = Query(None, description="csv para descarga"),
):
    """Serie por periodo (DESC). park_id obligatorio."""
    try:
        data = get_supply_series(park_id=park_id, from_date=from_, to_date=to, grain=grain)
        if (format or "").lower() == "csv":
            # Regla presentación: no IDs en export; solo columnas legibles (park_name, city, country)
            cols = ["period_start", "park_name", "city", "country", "activations", "active_drivers", "churned", "reactivated", "churn_rate", "reactivation_rate", "net_growth"]
            body = _to_csv(data, [c for c in cols if data and data[0].get(c) is not None] or cols)
            return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=supply_series.csv"})
        return {"data": data}
    except Exception as e:
        logger.error("GET /ops/supply/series: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/segments/series")
async def get_supply_segments_series_endpoint(
    park_id: str = Query(..., description="Park (obligatorio)"),
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    format: Optional[str] = Query(None),
):
    """Serie de segmentos por semana (FT/PT/CASUAL/OCC/DORMANT). Fuente: ops.mv_supply_segments_weekly. Orden: week_start DESC."""
    try:
        data = get_supply_segments_series(park_id=park_id, from_date=from_, to_date=to)
        if (format or "").lower() == "csv":
            cols = ["week_start", "segment_week", "drivers_count", "trips_sum", "share_of_active", "park_name", "city", "country"]
            body = _to_csv(data, cols)
            return Response(
                content=body,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=supply_segments_series.csv"},
            )
        return {"data": data}
    except Exception as e:
        logger.error("GET /ops/supply/segments/series: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/segments/config")
async def get_supply_segment_config_endpoint():
    """Configuración de segmentos (ops.driver_segment_config): segment, min_trips, max_trips, priority. Sustituye umbrales hardcodeados."""
    try:
        return {"data": get_supply_segment_config()}
    except Exception as e:
        logger.error("GET /ops/supply/segments/config: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/summary")
async def get_supply_summary_endpoint(
    park_id: str = Query(..., description="Park (obligatorio)"),
    from_: str = Query(..., alias="from"),
    to: str = Query(..., description="Fecha fin YYYY-MM-DD"),
    grain: Literal["weekly", "monthly"] = Query("weekly"),
):
    """Summary cards del rango visible (sumas y tasas ponderadas)."""
    try:
        return get_supply_summary(park_id=park_id, from_date=from_, to_date=to, grain=grain)
    except Exception as e:
        logger.error("GET /ops/supply/summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/global/series")
async def get_supply_global_series_endpoint(
    from_: str = Query(..., alias="from"),
    to: str = Query(..., description="Fecha fin YYYY-MM-DD"),
    grain: Literal["weekly", "monthly"] = Query("weekly"),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
):
    """Serie global (agregada por periodo; opcional country/city)."""
    try:
        data = get_supply_global_series(from_date=from_, to_date=to, grain=grain, country=country, city=city)
        if (format or "").lower() == "csv":
            cols = ["period_start", "activations", "active_drivers", "churned", "reactivated", "net_growth"]
            if data and any("country" in r for r in data):
                cols = ["period_start", "country", "city"] + [c for c in cols if c != "period_start"]
            body = _to_csv(data, cols)
            return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=supply_global.csv"})
        return {"data": data}
    except Exception as e:
        logger.error("GET /ops/supply/global/series: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/alerts")
async def get_supply_alerts_endpoint(
    park_id: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from", description="Semana desde YYYY-MM-DD"),
    to: Optional[str] = Query(None, description="Semana hasta YYYY-MM-DD"),
    week_start_from: Optional[str] = Query(None),
    week_start_to: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None, description="segment_drop | segment_spike"),
    severity: Optional[str] = Query(None, description="P0 | P1 | P2 | P3"),
    limit: int = Query(200, ge=1, le=500),
    format: Optional[str] = Query(None),
):
    """Alertas Supply PRO por semana, park, segmento. Fuente: ops.mv_supply_alerts_weekly."""
    try:
        from_val = from_ or week_start_from
        to_val = to or week_start_to
        data = get_supply_alerts(
            week_start_from=from_val,
            week_start_to=to_val,
            park_id=park_id,
            country=country,
            city=city,
            alert_type=alert_type,
            severity=severity,
            limit=limit,
        )
        if (format or "").lower() == "csv":
            cols = ["week_start", "severity", "alert_type", "segment_week", "current_value", "baseline_avg", "delta_pct", "message_short", "recommended_action", "park_name", "city", "country"]
            body = _to_csv(data, cols)
            return Response(
                content=body,
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=supply_alerts.csv"},
            )
        return {"data": data, "total": len(data)}
    except Exception as e:
        logger.error("GET /ops/supply/alerts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/alerts/drilldown")
async def get_supply_alert_drilldown_endpoint(
    park_id: str = Query(..., description="Park ID"),
    week_start: str = Query(..., description="Semana (YYYY-MM-DD)"),
    segment_week: Optional[str] = Query(None, description="FT | PT | CASUAL | OCCASIONAL"),
    alert_type: Optional[str] = Query(None, description="segment_drop | segment_spike"),
    format: Optional[str] = Query(None, description="csv para export"),
):
    """Conductores afectados (downshift/drop) para una alerta. Orden: baseline_trips_4w_avg desc."""
    try:
        data = get_supply_alert_drilldown(
            week_start=week_start,
            park_id=park_id,
            segment_week=segment_week,
            alert_type=alert_type,
        )
        if (format or "").lower() == "csv":
            cols = ["driver_key", "prev_segment_week", "segment_week_current", "trips_completed_week", "baseline_trips_4w_avg", "segment_change_type", "week_start", "park_id"]
            body = _to_csv(data, cols)
            return Response(
                content=body,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=supply_alert_drilldown_{week_start}_{park_id or 'all'}.csv"},
            )
        return {"data": data, "total": len(data)}
    except Exception as e:
        logger.error("GET /ops/supply/alerts/drilldown: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/overview-enhanced")
async def get_supply_overview_enhanced_endpoint(
    park_id: str = Query(..., description="Park (obligatorio)"),
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    grain: Literal["weekly", "monthly"] = Query("weekly"),
):
    """Overview enriquecido: trips, avg_trips_per_driver, FT/PT/weak_supply share; WoW cuando grain=weekly."""
    try:
        data = get_supply_overview_enhanced(park_id=park_id, from_date=from_, to_date=to, grain=grain)
        return data
    except Exception as e:
        logger.error("GET /ops/supply/overview-enhanced: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/composition")
async def get_supply_composition_endpoint(
    park_id: str = Query(..., description="Park (obligatorio)"),
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    format: Optional[str] = Query(None),
):
    """Composición semanal por segmento con WoW. Fuente: ops.mv_supply_segments_weekly."""
    try:
        data = get_supply_composition(park_id=park_id, from_date=from_, to_date=to)
        if (format or "").lower() == "csv":
            cols = ["week_start", "segment_week", "drivers_count", "delta_drivers", "trips_sum", "share_of_active", "delta_share", "supply_contribution", "avg_trips_per_driver", "drivers_wow_pct", "trips_wow_pct", "share_wow_pp"]
            body = _to_csv(data, [c for c in cols if data and data[0].get(c) is not None] or cols)
            return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=supply_composition.csv"})
        return {"data": data, "total": len(data)}
    except Exception as e:
        logger.error("GET /ops/supply/composition: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/migration")
async def get_supply_migration_endpoint(
    park_id: str = Query(..., description="Park (obligatorio)"),
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    format: Optional[str] = Query(None),
):
    """Migración entre segmentos por semana: from_segment, to_segment, drivers_migrated, migration_type. Incluye summary (upgrades, downgrades, drops, revivals)."""
    try:
        result = get_supply_migration(park_id=park_id, from_date=from_, to_date=to)
        rows = result.get("data", [])
        summary = result.get("summary", {"upgrades": 0, "downgrades": 0, "drops": 0, "revivals": 0})
        if (format or "").lower() == "csv":
            cols = ["week_start", "park_id", "from_segment", "to_segment", "migration_type", "drivers_migrated"]
            body = _to_csv(rows, cols)
            return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=supply_migration.csv"})
        return {"data": rows, "total": len(rows), "summary": summary}
    except Exception as e:
        logger.error("GET /ops/supply/migration: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/migration/drilldown")
async def get_supply_migration_drilldown_endpoint(
    park_id: str = Query(..., description="Park ID"),
    week_start: str = Query(..., description="Semana YYYY-MM-DD"),
    from_segment: Optional[str] = Query(None),
    to_segment: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
):
    """Drivers que migraron en una semana (opcional: from_segment, to_segment)."""
    try:
        data = get_supply_migration_drilldown(park_id=park_id, week_start=week_start, from_segment=from_segment, to_segment=to_segment)
        if (format or "").lower() == "csv":
            cols = ["driver_key", "week_start", "park_id", "from_segment", "to_segment", "migration_type", "trips_completed_week", "baseline_trips_4w_avg"]
            body = _to_csv(data, cols)
            return Response(content=body, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=supply_migration_drilldown_{week_start}_{park_id}.csv"})
        return {"data": data, "total": len(data)}
    except Exception as e:
        logger.error("GET /ops/supply/migration/drilldown: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/definitions")
async def get_supply_definitions_endpoint():
    """Definiciones oficiales de métricas (active_supply, churned, reactivated, growth_rate, segments, migration)."""
    try:
        return get_definitions()
    except Exception as e:
        logger.error("GET /ops/supply/definitions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supply/freshness")
async def get_supply_freshness_endpoint():
    """Última semana disponible, última corrida de refresh y estado del pipeline (fresh/stale/unknown)."""
    try:
        return get_supply_freshness()
    except Exception as e:
        logger.error("GET /ops/supply/freshness: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# --- Data Freshness & Coverage (fuentes base + derivados) ---
@router.get("/data-freshness")
async def get_data_freshness_endpoint(
    latest_only: bool = Query(True, description="Solo última ejecución por dataset"),
):
    """Auditoría de freshness por dataset: source_max_date, derived_max_date, expected_latest_date, status (OK, PARTIAL_EXPECTED, LAGGING, MISSING_EXPECTED_DATA)."""
    try:
        return get_freshness_audit(latest_only=latest_only)
    except Exception as e:
        logger.error("GET /ops/data-freshness: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data-freshness/alerts")
async def get_data_freshness_alerts_endpoint():
    """Resumen de alertas accionables: datasets con status distinto de OK y mensaje explicativo."""
    try:
        return get_freshness_alerts()
    except Exception as e:
        logger.error("GET /ops/data-freshness/alerts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data-freshness/expectations")
async def get_data_freshness_expectations_endpoint():
    """Configuración de expectativas por dataset (grain, expected_delay_days, source/derived objects)."""
    try:
        return get_freshness_expectations()
    except Exception as e:
        logger.error("GET /ops/data-freshness/expectations: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data-freshness/run")
async def post_data_freshness_run():
    """Ejecuta el chequeo de freshness y escribe en ops.data_freshness_audit. Uso: cron o admin."""
    try:
        import subprocess
        # __file__ = backend/app/routers/ops.py -> backend = dirname(dirname(dirname(__file__)))
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        r = subprocess.run(
            [sys.executable, "-m", "scripts.run_data_freshness_audit"],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "ok": r.returncode == 0,
            "stdout": r.stdout or "",
            "stderr": r.stderr or "",
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        logger.error("POST /ops/data-freshness/run: timeout")
        raise HTTPException(status_code=504, detail="Audit run timeout")
    except Exception as e:
        logger.error("POST /ops/data-freshness/run: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/supply/refresh")
async def post_supply_refresh():
    """Refresca MVs de Supply Alerting. CONCURRENTLY."""
    try:
        refresh_supply_alerting_mvs()
        return {"ok": True, "message": "ops.refresh_supply_alerting_mvs() ejecutado"}
    except Exception as e:
        logger.error("POST /ops/supply/refresh: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/supply/refresh-alerting")
async def post_supply_refresh_alerting():
    """Refresca MVs de Supply Alerting (solo si SUPPLY_REFRESH_ALLOWED=true). Uso admin."""
    import os
    if os.environ.get("SUPPLY_REFRESH_ALLOWED", "").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=403, detail="Supply refresh not allowed (set SUPPLY_REFRESH_ALLOWED)")
    try:
        refresh_supply_alerting_mvs()
        return {"ok": True, "message": "ops.refresh_supply_alerting_mvs() ejecutado"}
    except Exception as e:
        logger.error("POST /ops/supply/refresh-alerting: %s", e)
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


# ─── Real LOB Drill PRO (rutas más específicas primero para evitar 404) ─────────────────
@router.get("/real-lob/drill/parks")
async def get_real_lob_drill_parks_endpoint(
    country: Optional[str] = Query(None, description="Filtrar parks por país (pe | co)"),
):
    """Lista de parks para el filtro Park del drill."""
    try:
        parks = await _run_sync(get_real_lob_drill_parks, country=country)
        return {"parks": parks}
    except Exception as e:
        logger.error("GET /ops/real-lob/drill/parks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/drill/children")
async def get_real_lob_drill_children_endpoint(
    country: str = Query(..., description="País (pe | co)"),
    period: Literal["month", "week"] = Query("month"),
    period_start: str = Query(..., description="YYYY-MM-DD o YYYY-MM-01"),
    desglose: Literal["LOB", "PARK", "SERVICE_TYPE"] = Query("PARK"),
    segmento: Optional[Literal["all", "b2c", "b2b"]] = Query("all"),
    drill_lob_id: Optional[str] = Query(None, description="Filtro LOB (solo válido si desglose=LOB)"),
    drill_park_id: Optional[str] = Query(None, description="Filtro Park (válido si desglose=PARK o desglose=SERVICE_TYPE para filtrar tipo_servicio por park)"),
    park_id: Optional[str] = Query(None, description="Filtro por park (igual que drill_park_id; aplica a desglose tipo_servicio)"),
):
    """
    Desglose por LOB (1 fila por lob_group), Park (city, park_name), o Tipo de servicio. Orden: viajes DESC.
    Si desglose=SERVICE_TYPE y park_id (o drill_park_id) está indicado, el desglose se limita a ese park.

    Contrato params por dimensión:
    - desglose=LOB  => permitido drill_lob_id; 400 si llega drill_park_id.
    - desglose=PARK => permitido drill_park_id; 400 si llega drill_lob_id.
    - desglose=SERVICE_TYPE => permitido park_id/drill_park_id para filtrar por park.
    """
    if desglose == "PARK" and drill_lob_id is not None and str(drill_lob_id).strip() != "":
        raise HTTPException(
            status_code=400,
            detail="Incompatible drill params for groupBy=PARK: drill_lob_id is not allowed when desglose is PARK.",
        )
    if desglose == "LOB" and (drill_park_id is not None and str(drill_park_id).strip() != "" or park_id is not None and str(park_id).strip() != ""):
        raise HTTPException(
            status_code=400,
            detail="Incompatible drill params for groupBy=LOB: drill_park_id/park_id is not allowed when desglose is LOB.",
        )
    effective_park_id = (park_id or drill_park_id)
    if effective_park_id is not None:
        effective_park_id = str(effective_park_id).strip() or None
    try:
        data = await _run_sync(
            get_real_lob_drill_pro_children,
            country=country,
            period=period,
            period_start=period_start,
            desglose=desglose,
            segmento=segmento,
            park_id=effective_park_id,
        )
        return {"data": data}
    except Exception as e:
        logger.error("Real LOB drill PRO children: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/drill")
async def get_real_lob_drill_pro_endpoint(
    period: Literal["month", "week"] = Query("month", description="month | week"),
    desglose: Literal["LOB", "PARK", "SERVICE_TYPE"] = Query("PARK", description="Desglose al expandir: LOB | PARK | SERVICE_TYPE"),
    segmento: Optional[Literal["all", "b2c", "b2b"]] = Query("all", description="all | b2c | b2b"),
    country: Optional[Literal["all", "pe", "co"]] = Query("all", description="all | pe | co"),
    park_id: Optional[str] = Query(None, description="Filtro opcional por park; aplica a timeline y a desglose tipo_servicio"),
):
    """Real LOB Drill PRO: countries[] con coverage, kpis, rows por periodo."""
    logger.info("Real LOB drill: request received period=%s desglose=%s segmento=%s park_id=%s", period, desglose, segmento, park_id)
    try:
        return await _run_sync(
            get_real_lob_drill_pro,
            period=period,
            desglose=desglose,
            segmento=segmento,
            country=country,
            park_id=park_id,
        )
    except Exception as e:
        logger.error("Real LOB drill PRO: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── Period Semantics & Comparatives ─────────────────
@router.get("/period-semantics")
async def get_period_semantics_endpoint(
    reference: Optional[str] = Query(None, description="Fecha referencia YYYY-MM-DD (default: hoy)"),
):
    """Semántica temporal: last_closed_day/week/month, current_open_week/month y labels para UI."""
    try:
        ref = None
        if reference and len(reference.strip()) >= 10:
            from datetime import date
            ref = date.fromisoformat(reference.strip()[:10])
        return await asyncio.to_thread(get_period_semantics, ref)
    except Exception as e:
        logger.error("GET /ops/period-semantics: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/comparatives/weekly")
async def get_real_lob_wow_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país (pe | co)"),
):
    """WoW: última semana cerrada vs semana cerrada anterior. Métricas: viajes, margen_total, margen_trip, km_prom, b2b_pct."""
    try:
        return await asyncio.to_thread(get_weekly_comparative, country=country)
    except Exception as e:
        logger.error("GET /ops/real-lob/comparatives/weekly: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/comparatives/monthly")
async def get_real_lob_mom_endpoint(
    country: Optional[str] = Query(None, description="Filtrar por país (pe | co)"),
):
    """MoM: último mes cerrado vs mes cerrado anterior. Métricas: viajes, margen_total, margen_trip, km_prom, b2b_pct."""
    try:
        return await asyncio.to_thread(get_monthly_comparative, country=country)
    except Exception as e:
        logger.error("GET /ops/real-lob/comparatives/monthly: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/daily/summary")
async def get_real_lob_daily_summary_endpoint(
    day: Optional[str] = Query(None, description="Fecha YYYY-MM-DD (default: último día cerrado = ayer)"),
    country: Optional[str] = Query(None, description="Filtrar por país (pe | co)"),
):
    """Vista diaria: KPIs agregados por día (viajes, margen, km_prom, B2B %)."""
    try:
        return await asyncio.to_thread(get_daily_summary, day=day, country=country)
    except Exception as e:
        logger.error("GET /ops/real-lob/daily/summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/daily/comparative")
async def get_real_lob_daily_comparative_endpoint(
    day: Optional[str] = Query(None, description="Fecha YYYY-MM-DD (default: último día cerrado)"),
    country: Optional[str] = Query(None, description="Filtrar por país (pe | co)"),
    baseline: Literal["D-1", "same_weekday_previous_week", "same_weekday_avg_4w"] = Query(
        "D-1",
        description="D-1 = vs día anterior; same_weekday_previous_week = vs mismo día semana pasada; same_weekday_avg_4w = vs promedio 4 mismos días",
    ),
):
    """Comparativo diario: día consultado vs baseline (D-1, mismo día semana pasada, o promedio 4 mismos días)."""
    try:
        return await asyncio.to_thread(get_daily_comparative, day=day, country=country, baseline=baseline)
    except Exception as e:
        logger.error("GET /ops/real-lob/daily/comparative: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/real-lob/daily/table")
async def get_real_lob_daily_table_endpoint(
    day: Optional[str] = Query(None, description="Fecha YYYY-MM-DD (default: último día cerrado)"),
    country: Optional[str] = Query(None, description="Filtrar por país (pe | co)"),
    group_by: Literal["lob", "park"] = Query("lob", description="Agrupar por LOB o por Park"),
    baseline: Optional[Literal["D-1", "same_weekday_previous_week", "same_weekday_avg_4w"]] = Query(
        None, description="Si se indica, cada fila incluye *_baseline y *_delta_pct (comparativo por fila)",
    ),
):
    """Tabla diaria: filas por LOB o por Park. Con baseline se añaden columnas comparativas por fila."""
    try:
        return await asyncio.to_thread(get_daily_table, day=day, country=country, group_by=group_by, baseline=baseline)
    except Exception as e:
        logger.error("GET /ops/real-lob/daily/table: %s", e)
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
