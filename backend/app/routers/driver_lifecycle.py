"""
Driver Lifecycle: endpoints con drilldown por park.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from fastapi.responses import PlainTextResponse
from app.services.driver_lifecycle_service import (
    get_weekly,
    get_monthly,
    get_drilldown,
    get_parks_summary,
    get_series,
    get_summary,
    get_cohorts,
    get_cohort_drilldown,
    get_base_metrics,
    get_base_metrics_drilldown,
    get_parks_for_selector,
    get_pro_churn_segments,
    get_pro_park_shock_list,
    get_pro_behavior_shifts,
    get_pro_drivers_at_risk,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops/driver-lifecycle", tags=["driver-lifecycle"])


@router.get("/weekly")
@router.get("/weekly-kpis")
async def driver_lifecycle_weekly(
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    park_id: Optional[str] = Query(None, description="Filtro opcional por park"),
):
    """
    KPIs semanales. Sin park_id devuelve además breakdown_by_park.
    """
    try:
        return get_weekly(from_date=from_, to_date=to, park_id=park_id)
    except Exception as e:
        logger.exception("driver-lifecycle weekly: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monthly")
@router.get("/monthly-kpis")
async def driver_lifecycle_monthly(
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    park_id: Optional[str] = Query(None, description="Filtro opcional por park"),
):
    """
    KPIs mensuales. Sin park_id devuelve además breakdown_by_park.
    """
    try:
        return get_monthly(from_date=from_, to_date=to, park_id=park_id)
    except Exception as e:
        logger.exception("driver-lifecycle monthly: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drilldown")
@router.get("/kpi-drilldown")
async def driver_lifecycle_drilldown(
    period_start: str = Query(..., description="YYYY-MM-DD (lunes para week, YYYY-MM-01 para month)"),
    park_id: str = Query(..., description="Park (obligatorio)"),
    period_type: Optional[str] = Query(None, description="week | month"),
    grain: Optional[str] = Query(None, description="Alias: weekly|monthly"),
    metric: Optional[str] = Query(None, description="activations | churned | reactivated | active | fulltime | parttime"),
    metric_name: Optional[str] = Query(None, description="Alias de metric"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """
    Lista paginada de driver_key para el periodo, métrica y park. Incluye activation_ts/last_completed_ts cuando aplica.
    Aliases: grain (weekly|monthly) -> period_type, metric_name -> metric.
    """
    pt = (grain or period_type or "").replace("weekly", "week").replace("monthly", "month")
    m = metric_name or metric
    if not pt or pt not in ("week", "month"):
        raise HTTPException(status_code=400, detail="period_type or grain (weekly|monthly) required")
    if not m:
        raise HTTPException(status_code=400, detail="metric or metric_name required")
    try:
        out = get_drilldown(
            period_type=pt,
            period_start=period_start,
            metric=m,
            park_id=park_id,
            page=page,
            page_size=page_size,
        )
        if out.get("error"):
            raise HTTPException(status_code=400, detail=out["error"])
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("driver-lifecycle drilldown: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/base-metrics")
async def driver_lifecycle_base_metrics(
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    park_id: Optional[str] = Query(None, description="Filtro opcional por park"),
):
    """
    Métricas base: time_to_first_trip (avg, median), lifetime_days (avg, median).
    """
    try:
        return get_base_metrics(from_date=from_, to_date=to, park_id=park_id)
    except Exception as e:
        logger.exception("driver-lifecycle base-metrics: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/base-metrics-drilldown")
async def driver_lifecycle_base_metrics_drilldown(
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    park_id: str = Query(..., description="Park (obligatorio)"),
    metric: str = Query(..., description="time_to_first_trip | lifetime_days"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """Drilldown de base metrics: lista drivers con ttf o lifetime."""
    if metric not in ("time_to_first_trip", "lifetime_days"):
        raise HTTPException(status_code=400, detail="metric must be time_to_first_trip or lifetime_days")
    try:
        out = get_base_metrics_drilldown(
            from_date=from_, to_date=to, park_id=park_id, metric=metric, page=page, page_size=page_size
        )
        if out.get("error"):
            raise HTTPException(status_code=400, detail=out["error"])
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("driver-lifecycle base-metrics-drilldown: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/park/series")
async def driver_lifecycle_park_series(
    park_id: str = Query(..., description="Park (obligatorio)"),
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    grain: str = Query("weekly", description="weekly | monthly"),
):
    """
    Serie por periodo para un park (PRO). Orden: más reciente primero.
    Alias de GET /series con park_id obligatorio.
    """
    if grain not in ("weekly", "monthly"):
        raise HTTPException(status_code=400, detail="grain must be weekly or monthly")
    try:
        return get_series(from_date=from_, to_date=to, grain=grain, park_id=park_id)
    except Exception as e:
        logger.exception("driver-lifecycle park/series: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series")
async def driver_lifecycle_series(
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    grain: str = Query("weekly", description="weekly | monthly"),
    park_id: Optional[str] = Query(None, description="Filtro opcional por park"),
):
    """
    Serie por periodo (week_start o month_start). Orden: más reciente → más antiguo.
    Métricas: period_start, activations, active_drivers, churned, reactivated,
    churn_rate, reactivation_rate, net_growth, mix_ft_pt.
    """
    if grain not in ("weekly", "monthly"):
        raise HTTPException(status_code=400, detail="grain must be weekly or monthly")
    try:
        return get_series(from_date=from_, to_date=to, grain=grain, park_id=park_id)
    except Exception as e:
        logger.exception("driver-lifecycle series: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def driver_lifecycle_summary(
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    grain: str = Query("weekly", description="weekly | monthly"),
    park_id: Optional[str] = Query(None, description="Filtro opcional por park"),
):
    """
    Resumen (cards) del rango: activations_range, churned_range, reactivated_range,
    time_to_first_trip_avg_days, lifetime_avg_active_days, active_drivers_last_period.
    Consistente con /series (active_drivers_last_period = primer periodo de la serie).
    """
    if grain not in ("weekly", "monthly"):
        raise HTTPException(status_code=400, detail="grain must be weekly or monthly")
    try:
        return get_summary(from_date=from_, to_date=to, grain=grain, park_id=park_id)
    except Exception as e:
        logger.exception("driver-lifecycle summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parks-summary")
async def driver_lifecycle_parks_summary(
    from_: str = Query(..., alias="from", description="YYYY-MM-DD"),
    to: str = Query(..., description="YYYY-MM-DD"),
    period_type: str = Query("week", description="week | month"),
):
    """
    Ranking de parks por activations, churn_rate, net_growth, mix FT/PT en el rango.
    """
    try:
        return get_parks_summary(from_date=from_, to_date=to, period_type=period_type)
    except Exception as e:
        logger.exception("driver-lifecycle parks-summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parks")
async def driver_lifecycle_parks_list():
    """
    Lista de parks para selector (Driver Lifecycle PRO).
    Fuente: dim.dim_park [{ park_id, park_name }]. Misma dimensión que Real LOB.
    Fallback: distinct park_id desde MVs + nombres desde dim.dim_park.
    """
    try:
        parks = get_parks_for_selector()
        return {"parks": [{"park_id": p["park_id"], "park_name": p.get("park_name") or str(p.get("park_id") or "")} for p in parks]}
    except Exception as e:
        logger.exception("driver-lifecycle parks list: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cohorts")
async def driver_lifecycle_cohorts(
    from_cohort_week: str = Query(..., description="YYYY-MM-DD (lunes)"),
    to_cohort_week: str = Query(..., description="YYYY-MM-DD (lunes)"),
    park_id: Optional[str] = Query(None, description="Filtro opcional por park"),
):
    """
    KPIs de cohortes por cohort_week y park_id.
    """
    try:
        return get_cohorts(
            from_cohort_week=from_cohort_week,
            to_cohort_week=to_cohort_week,
            park_id=park_id,
        )
    except Exception as e:
        logger.exception("driver-lifecycle cohorts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ─── PRO: churn segments, park shock, behavior shifts, drivers at risk + CSV export ─────────────────
def _to_csv(rows: list, columns: list) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([r.get(c) for c in columns])
    return buf.getvalue()


@router.get("/pro/churn-segments")
async def driver_lifecycle_pro_churn_segments(
    week_start: Optional[str] = Query(None, description="YYYY-MM-DD (lunes)"),
    segment: Optional[str] = Query(None, description="power | mid | light | newbie"),
    park_id: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=50000),
    format: Optional[str] = Query(None, description="csv para export"),
):
    """Lista ops.mv_driver_churn_segments_weekly. format=csv devuelve CSV."""
    try:
        rows = get_pro_churn_segments(week_start=week_start, segment=segment, park_id=park_id, limit=limit)
        if format == "csv":
            cols = ["driver_key", "week_start", "park_id", "trips_completed_week", "work_mode_week", "trips_prev_4w", "churn_segment"]
            return PlainTextResponse(_to_csv(rows, cols), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=driver_churn_segments.csv"})
        return {"data": rows, "total": len(rows)}
    except Exception as e:
        logger.exception("driver-lifecycle pro churn-segments: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pro/park-shock")
async def driver_lifecycle_pro_park_shock(
    week_start: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=50000),
    format: Optional[str] = Query(None, description="csv para export"),
):
    """Drivers con park_shock (cambio park dominante 8w vs baseline 12-5). format=csv devuelve CSV."""
    try:
        rows = get_pro_park_shock_list(week_start=week_start, limit=limit)
        if format == "csv":
            cols = ["driver_key", "week_start", "baseline_park_id", "recent_park_id", "park_shock"]
            return PlainTextResponse(_to_csv(rows, cols), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=driver_park_shock.csv"})
        return {"data": rows, "total": len(rows)}
    except Exception as e:
        logger.exception("driver-lifecycle pro park-shock: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pro/behavior-shifts")
async def driver_lifecycle_pro_behavior_shifts(
    week_start: Optional[str] = Query(None),
    shift: Optional[str] = Query(None, description="drop | spike | stable"),
    park_id: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=50000),
    format: Optional[str] = Query(None, description="csv para export"),
):
    """Lista ops.mv_driver_behavior_shifts_weekly. format=csv devuelve CSV."""
    try:
        rows = get_pro_behavior_shifts(week_start=week_start, shift=shift, park_id=park_id, limit=limit)
        if format == "csv":
            cols = ["driver_key", "week_start", "park_id", "trips_current_week", "avg_trips_prev_4w", "behavior_shift"]
            return PlainTextResponse(_to_csv(rows, cols), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=driver_behavior_shifts.csv"})
        return {"data": rows, "total": len(rows)}
    except Exception as e:
        logger.exception("driver-lifecycle pro behavior-shifts: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pro/drivers-at-risk")
async def driver_lifecycle_pro_drivers_at_risk(
    week_start: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=50000),
    format: Optional[str] = Query(None, description="csv para export"),
):
    """Drivers en riesgo: light/newbie, drop o park_shock. format=csv devuelve CSV."""
    try:
        rows = get_pro_drivers_at_risk(week_start=week_start, park_id=park_id, limit=limit)
        if format == "csv":
            cols = ["driver_key", "week_start", "park_id", "churn_segment", "behavior_shift", "park_shock"]
            return PlainTextResponse(_to_csv(rows, cols), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=drivers_at_risk.csv"})
        return {"data": rows, "total": len(rows)}
    except Exception as e:
        logger.exception("driver-lifecycle pro drivers-at-risk: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cohort-drilldown")
async def driver_lifecycle_cohort_drilldown(
    cohort_week: str = Query(..., description="YYYY-MM-DD (lunes)"),
    horizon: str = Query(..., description="base | w1 | w4 | w8 | w12"),
    park_id: str = Query(..., description="Park (obligatorio)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    """
    Lista paginada de driver_key para cohorte/horizon/park.
    """
    if horizon not in ("base", "w1", "w4", "w8", "w12"):
        raise HTTPException(status_code=400, detail="horizon must be base, w1, w4, w8 or w12")
    try:
        out = get_cohort_drilldown(
            cohort_week=cohort_week,
            horizon=horizon,
            park_id=park_id,
            page=page,
            page_size=page_size,
        )
        if out.get("error"):
            raise HTTPException(status_code=400, detail=out["error"])
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("driver-lifecycle cohort-drilldown: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
