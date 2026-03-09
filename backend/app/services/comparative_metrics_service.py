"""
Comparativos oficiales WoW (semana cerrada vs anterior) y MoM (mes cerrado vs anterior).
Usa períodos cerrados por defecto. Fuente: ops.real_rollup_day_fact.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from app.db.connection import get_db
from app.services.period_semantics_service import (
    get_last_closed_week,
    get_last_closed_month,
)
from psycopg2.extras import RealDictCursor

TABLE_DAY = "ops.real_rollup_day_fact"


def _float_or_none(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _trend(current: float, previous: float) -> str:
    if previous == 0:
        return "flat" if current == 0 else "up"
    pct = (current - previous) / previous
    if abs(pct) < 0.0001:
        return "flat"
    return "up" if pct > 0 else "down"


def _metric_row(
    value_current: float | None,
    value_previous: float | None,
    name: str,
) -> dict[str, Any]:
    cur = value_current if value_current is not None else 0.0
    prev = value_previous if value_previous is not None else 0.0
    delta_abs = cur - prev if (value_current is not None or value_previous is not None) else None
    delta_pct = (delta_abs / prev * 100) if prev != 0 and delta_abs is not None else None
    return {
        "metric": name,
        "value_current": value_current,
        "value_previous": value_previous,
        "delta_abs": round(delta_abs, 4) if delta_abs is not None else None,
        "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
        "trend_direction": _trend(cur, prev),
    }


def _agg_week(cursor, country: str | None, week_start: str) -> dict[str, Any]:
    where = "week_start = %s::date"
    params: list[Any] = [week_start]
    if country and country.strip():
        where += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params.append(country.strip())
    cursor.execute(
        f"""
        SELECT
            SUM(trips) AS trips,
            SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) AS margin_total,
            SUM(b2b_trips) AS b2b_trips,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) / SUM(trips) ELSE NULL END AS margin_trip,
            CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(distance_total_km, 0))::numeric / SUM(trips) ELSE NULL END AS km_prom
        FROM (
            SELECT trip_day, country, trips, margin_total_pos, margin_total_raw, b2b_trips, distance_total_km,
                   date_trunc('week', trip_day)::date AS week_start
            FROM {TABLE_DAY}
        ) t
        WHERE {where}
        """,
        params,
    )
    return dict(cursor.fetchone() or {})


def _agg_month(cursor, country: str | None, month_start: str) -> dict[str, Any]:
    where = "month_start = %s::date"
    params: list[Any] = [month_start]
    if country and country.strip():
        where += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params.append(country.strip())
    cursor.execute(
        f"""
        SELECT
            SUM(trips) AS trips,
            SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) AS margin_total,
            SUM(b2b_trips) AS b2b_trips,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) / SUM(trips) ELSE NULL END AS margin_trip,
            CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(distance_total_km, 0))::numeric / SUM(trips) ELSE NULL END AS km_prom
        FROM (
            SELECT trip_day, country, trips, margin_total_pos, margin_total_raw, b2b_trips, distance_total_km,
                   date_trunc('month', trip_day)::date AS month_start
            FROM {TABLE_DAY}
        ) t
        WHERE {where}
        """,
        params,
    )
    return dict(cursor.fetchone() or {})


def get_weekly_comparative(country: str | None = None) -> dict[str, Any]:
    """
    WoW: última semana cerrada vs semana cerrada anterior.
    Métricas: viajes, margen_total, margen_trip, km_prom, b2b_pct.
    """
    last = get_last_closed_week()
    previous = last - timedelta(days=7)
    last_s = last.isoformat()
    prev_s = previous.isoformat()

    out: dict[str, Any] = {
        "period_type": "week",
        "current_week_start": last_s,
        "previous_week_start": prev_s,
        "comparative_type": "WoW",
        "metrics": [],
        "by_country": [],
    }

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = '15000'")

            countries_to_fetch = ["pe", "co"] if not country or not country.strip() else [country.strip().lower()]
            for c in countries_to_fetch:
                if c not in ("pe", "co"):
                    continue
                curr_agg = _agg_week(cur, c, last_s)
                prev_agg = _agg_week(cur, c, prev_s)

                trips_cur = _float_or_none(curr_agg.get("trips"))
                trips_prev = _float_or_none(prev_agg.get("trips"))
                margin_cur = _float_or_none(curr_agg.get("margin_total"))
                margin_prev = _float_or_none(prev_agg.get("margin_total"))
                margin_trip_cur = _float_or_none(curr_agg.get("margin_trip"))
                margin_trip_prev = _float_or_none(prev_agg.get("margin_trip"))
                km_cur = _float_or_none(curr_agg.get("km_prom"))
                km_prev = _float_or_none(prev_agg.get("km_prom"))
                b2b_cur = _float_or_none(curr_agg.get("b2b_trips"))
                b2b_prev = _float_or_none(prev_agg.get("b2b_trips"))
                trips_tot = (trips_cur or 0) + 1e-9
                b2b_pct_cur = (b2b_cur / trips_tot * 100) if b2b_cur is not None and trips_tot else None
                trips_tot_prev = (trips_prev or 0) + 1e-9
                b2b_pct_prev = (b2b_prev / trips_tot_prev * 100) if b2b_prev is not None and trips_tot_prev else None

                metrics = [
                    _metric_row(trips_cur, trips_prev, "viajes"),
                    _metric_row(margin_cur, margin_prev, "margen_total"),
                    _metric_row(margin_trip_cur, margin_trip_prev, "margen_trip"),
                    _metric_row(km_cur, km_prev, "km_prom"),
                    _metric_row(b2b_pct_cur, b2b_pct_prev, "b2b_pct"),
                ]
                out["by_country"].append({
                    "country": c,
                    "metrics": metrics,
                })
                if not out["metrics"]:
                    out["metrics"] = metrics
            cur.close()
    except Exception as e:
        out["error"] = str(e)
    return out


def get_monthly_comparative(country: str | None = None) -> dict[str, Any]:
    """
    MoM: último mes cerrado vs mes cerrado anterior.
    """
    last = get_last_closed_month()
    # Mes anterior al último cerrado
    if last.month == 1:
        previous = last.replace(year=last.year - 1, month=12)
    else:
        previous = last.replace(month=last.month - 1)
    last_s = last.isoformat()
    prev_s = previous.isoformat()

    out: dict[str, Any] = {
        "period_type": "month",
        "current_month_start": last_s,
        "previous_month_start": prev_s,
        "comparative_type": "MoM",
        "metrics": [],
        "by_country": [],
    }

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = '15000'")

            countries_to_fetch = ["pe", "co"] if not country or not country.strip() else [country.strip().lower()]
            for c in countries_to_fetch:
                if c not in ("pe", "co"):
                    continue
                curr_agg = _agg_month(cur, c, last_s)
                prev_agg = _agg_month(cur, c, prev_s)

                trips_cur = _float_or_none(curr_agg.get("trips"))
                trips_prev = _float_or_none(prev_agg.get("trips"))
                margin_cur = _float_or_none(curr_agg.get("margin_total"))
                margin_prev = _float_or_none(prev_agg.get("margin_total"))
                margin_trip_cur = _float_or_none(curr_agg.get("margin_trip"))
                margin_trip_prev = _float_or_none(prev_agg.get("margin_trip"))
                km_cur = _float_or_none(curr_agg.get("km_prom"))
                km_prev = _float_or_none(prev_agg.get("km_prom"))
                b2b_cur = _float_or_none(curr_agg.get("b2b_trips"))
                b2b_prev = _float_or_none(prev_agg.get("b2b_trips"))
                trips_tot = (trips_cur or 0) + 1e-9
                b2b_pct_cur = (b2b_cur / trips_tot * 100) if b2b_cur is not None and trips_tot else None
                trips_tot_prev = (trips_prev or 0) + 1e-9
                b2b_pct_prev = (b2b_prev / trips_tot_prev * 100) if b2b_prev is not None and trips_tot_prev else None

                metrics = [
                    _metric_row(trips_cur, trips_prev, "viajes"),
                    _metric_row(margin_cur, margin_prev, "margen_total"),
                    _metric_row(margin_trip_cur, margin_trip_prev, "margen_trip"),
                    _metric_row(km_cur, km_prev, "km_prom"),
                    _metric_row(b2b_pct_cur, b2b_pct_prev, "b2b_pct"),
                ]
                out["by_country"].append({
                    "country": c,
                    "metrics": metrics,
                })
                if not out["metrics"]:
                    out["metrics"] = metrics
            cur.close()
    except Exception as e:
        out["error"] = str(e)
    return out
