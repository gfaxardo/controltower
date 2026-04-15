"""
Projection Expected Progress Service — orquestador para modo Omniview Proyección.

Combina:
- Plan mensualizado desde ops.v_plan_projection_control_loop
- Real acumulado desde facts (month/week/day)
- Curva estacional desde seasonality_curve_engine

Aditivo: no modifica servicios ni tablas existentes.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.business_slice_service import FACT_DAILY, FACT_MONTHLY, FACT_WEEKLY
from app.services.control_loop_business_slice_resolve import (
    load_map_fallback_rows,
    load_rules_index_for_geos,
    resolve_to_business_slice_name,
)
from app.services.seasonality_curve_engine import (
    PROJECTABLE_KPIS,
    compute_daily_expected_ratio,
    compute_expected_ratio,
    compute_weekly_expected_ratio,
)

logger = logging.getLogger(__name__)

_COUNTRY_NORM = {
    "peru": "pe", "perú": "pe", "pe": "pe",
    "colombia": "co", "col": "co", "co": "co",
}

_COUNTRY_FULL = {"pe": "peru", "co": "colombia"}


def _norm_country(raw: str) -> str:
    return _COUNTRY_NORM.get((raw or "").strip().lower(), (raw or "").strip().lower())


def _to_full_country(code: str) -> str:
    return _COUNTRY_FULL.get(code, code)


def _month_key(d) -> str:
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-01")
    return str(d)[:7] + "-01"


def _signal_from_attainment(attainment_pct: Optional[float]) -> str:
    if attainment_pct is None:
        return "no_data"
    if attainment_pct >= 100.0:
        return "green"
    if attainment_pct >= 90.0:
        return "warning"
    return "danger"


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_omniview_projection(
    plan_version: str,
    grain: str = "monthly",
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Dict[str, Any]:
    """Main entry point for the Omniview Projection mode."""
    today = date.today()

    plan_rows = _load_plan(plan_version, country, city, year, month)
    if not plan_rows:
        return {
            "granularity": grain,
            "plan_version": plan_version,
            "data": [],
            "meta": {
                "plan_version": plan_version,
                "plan_loaded_at": None,
                "curve_summary": {"total_combinations": 0, "by_method": {}, "avg_confidence": None},
                "kpis_with_projection": list(PROJECTABLE_KPIS),
                "message": "No hay proyección cargada para esta versión / filtros.",
            },
        }

    geos: Set[Tuple[str, str]] = set()
    for p in plan_rows:
        geos.add((str(p["country"]), str(p["city"])))

    idx = load_rules_index_for_geos(geos)
    map_rows = load_map_fallback_rows()

    plan_by_key = _resolve_and_index_plan(plan_rows, idx, map_rows)

    with get_db() as conn:
        if grain == "monthly":
            result_rows = _build_monthly(conn, plan_by_key, today, country, city, business_slice, year, month)
        elif grain == "weekly":
            result_rows = _build_weekly(conn, plan_by_key, today, country, city, business_slice, year, month)
        else:
            result_rows = _build_daily(conn, plan_by_key, today, country, city, business_slice, year, month)

    curve_summary = _compute_curve_summary(result_rows)

    last_loaded = None
    for p in plan_rows:
        la = p.get("last_loaded_at")
        if la:
            last_loaded = str(la)
            break

    return {
        "granularity": grain,
        "plan_version": plan_version,
        "data": result_rows,
        "meta": {
            "plan_version": plan_version,
            "plan_loaded_at": last_loaded,
            "curve_summary": curve_summary,
            "kpis_with_projection": list(PROJECTABLE_KPIS),
        },
    }


def _load_plan(
    plan_version: str,
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> List[Dict[str, Any]]:
    params: List[Any] = [plan_version]
    clauses = ["plan_version = %s"]

    if country:
        cn = _norm_country(country)
        full = _to_full_country(cn)
        clauses.append("lower(trim(country)) = lower(trim(%s))")
        params.append(full)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    if year:
        clauses.append("EXTRACT(YEAR FROM period_date) = %s")
        params.append(year)
    if month:
        clauses.append("EXTRACT(MONTH FROM period_date) = %s")
        params.append(month)

    sql = f"""
        SELECT plan_version, period_date, country, city,
               linea_negocio_canonica, linea_negocio_excel,
               projected_trips, projected_revenue, projected_active_drivers,
               last_loaded_at
        FROM ops.v_plan_projection_control_loop
        WHERE {' AND '.join(clauses)}
    """

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

    return rows


def _resolve_and_index_plan(
    plan_rows: List[Dict[str, Any]],
    idx,
    map_rows: List[dict],
) -> Dict[Tuple[str, str, str, str], Dict[str, Any]]:
    """Resolve plan lines to business_slice_name and index by (month, country, city, bsn)."""
    result: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}

    for p in plan_rows:
        co = str(p["country"])
        ci = str(p["city"])
        lob_excel = str(p.get("linea_negocio_excel") or "")
        lob_canon = str(p.get("linea_negocio_canonica") or "")

        bsn, source = resolve_to_business_slice_name(idx, map_rows, co, ci, lob_excel, lob_canon)
        if not bsn:
            bsn = lob_excel or lob_canon or "__unresolved__"

        mk = _month_key(p["period_date"])
        key = (mk, co.strip().lower(), ci.strip().lower(), bsn.strip().lower())

        if key in result:
            existing = result[key]
            for metric_key, plan_key in [
                ("projected_trips", "projected_trips"),
                ("projected_revenue", "projected_revenue"),
                ("projected_active_drivers", "projected_active_drivers"),
            ]:
                ev = _safe_float(existing.get(plan_key))
                nv = _safe_float(p.get(plan_key))
                if ev is not None and nv is not None:
                    existing[plan_key] = ev + nv
                elif nv is not None:
                    existing[plan_key] = nv
        else:
            result[key] = {
                "period_date": p["period_date"],
                "country": co,
                "city": ci,
                "business_slice_name": bsn,
                "resolution_source": source,
                "projected_trips": _safe_float(p.get("projected_trips")),
                "projected_revenue": _safe_float(p.get("projected_revenue")),
                "projected_active_drivers": _safe_float(p.get("projected_active_drivers")),
            }

    return result


def _build_monthly(
    conn,
    plan_by_key: Dict[Tuple, Dict],
    today: date,
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> List[Dict[str, Any]]:
    real_map = _load_real_monthly(conn, country, city, business_slice, year, month)
    all_plan_months = set()
    for (mk, *_) in plan_by_key:
        all_plan_months.add(mk)

    result = []
    seen_keys: Set[Tuple] = set()

    for key, plan in plan_by_key.items():
        mk, co_norm, ci_norm, bsn_lower = key
        month_date = date.fromisoformat(mk)
        cutoff = _monthly_cutoff(month_date, today)

        row = _build_projection_row_monthly(
            conn, plan, month_date, cutoff, co_norm, ci_norm, bsn_lower,
            real_map, "monthly"
        )
        result.append(row)
        seen_keys.add(key)

    for rk, real_data in real_map.items():
        if rk in seen_keys:
            continue
        if business_slice and business_slice.strip().lower() != rk[3]:
            continue
        mk = rk[0]
        month_date = date.fromisoformat(mk)
        cutoff = _monthly_cutoff(month_date, today)
        row = _build_no_plan_row(real_data, mk, "monthly")
        result.append(row)

    result.sort(key=lambda r: (r.get("month", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    return result


def _monthly_cutoff(month_date: date, today: date) -> int:
    month_start = month_date.replace(day=1)
    next_month = date(month_start.year + (month_start.month // 12), (month_start.month % 12) + 1, 1)
    month_end = next_month - timedelta(days=1)

    if today >= month_end:
        return month_end.day
    if today >= month_start:
        return today.day
    return month_end.day


def _build_projection_row_monthly(
    conn,
    plan: Dict,
    month_date: date,
    cutoff_day: int,
    co_norm: str,
    ci_norm: str,
    bsn_lower: str,
    real_map: Dict,
    grain: str,
) -> Dict[str, Any]:
    bsn = plan["business_slice_name"]
    co_full = plan["country"]
    ci = plan["city"]

    real_key = (_month_key(month_date), co_norm, ci_norm, bsn_lower)
    real = real_map.get(real_key, {})

    row: Dict[str, Any] = {
        "country": co_full,
        "city": ci,
        "business_slice_name": bsn,
        "fleet_display_name": bsn,
        "is_subfleet": False,
        "subfleet_name": "",
        "month": _month_key(month_date),
    }

    for kpi in PROJECTABLE_KPIS:
        plan_key = f"projected_{kpi}" if kpi != "revenue_yego_net" else "projected_revenue"
        if kpi == "trips_completed":
            plan_key = "projected_trips"
        elif kpi == "active_drivers":
            plan_key = "projected_active_drivers"

        plan_total = _safe_float(plan.get(plan_key))

        real_kpi_key = kpi
        if kpi == "revenue_yego_net":
            real_kpi_key = "real_revenue"
        elif kpi == "trips_completed":
            real_kpi_key = "real_trips"
        elif kpi == "active_drivers":
            real_kpi_key = "real_active_drivers"

        actual = _safe_float(real.get(real_kpi_key))

        curve = compute_expected_ratio(
            _to_full_country(co_norm), ci, bsn, kpi, month_date, cutoff_day, conn=conn,
        )
        expected_ratio = curve["expected_ratio_to_date"]
        expected_to_date = plan_total * expected_ratio if plan_total is not None else None

        attainment = None
        if actual is not None and expected_to_date is not None and expected_to_date > 0:
            attainment = round((actual / expected_to_date) * 100.0, 2)

        gap_to_expected = None
        if actual is not None and expected_to_date is not None:
            gap_to_expected = round(actual - expected_to_date, 2)

        gap_to_full = None
        if actual is not None and plan_total is not None:
            gap_to_full = round(actual - plan_total, 2)

        completion = None
        if actual is not None and plan_total is not None and plan_total > 0:
            completion = round((actual / plan_total) * 100.0, 2)

        row[kpi] = actual
        row[f"{kpi}_projected_total"] = plan_total
        row[f"{kpi}_projected_expected"] = round(expected_to_date, 2) if expected_to_date is not None else None
        row[f"{kpi}_attainment_pct"] = attainment
        row[f"{kpi}_gap_to_expected"] = gap_to_expected
        row[f"{kpi}_gap_to_full"] = gap_to_full
        row[f"{kpi}_completion_pct"] = completion
        row[f"{kpi}_signal"] = _signal_from_attainment(attainment)
        row[f"{kpi}_curve_method"] = curve.get("curve_method", "linear_fallback")
        row[f"{kpi}_curve_confidence"] = curve.get("confidence", "fallback")
        row[f"{kpi}_fallback_level"] = curve.get("fallback_level", 5)
        row[f"{kpi}_expected_ratio"] = expected_ratio

    return row


def _build_weekly(
    conn,
    plan_by_key: Dict[Tuple, Dict],
    today: date,
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> List[Dict[str, Any]]:
    real_map = _load_real_weekly(conn, country, city, business_slice, year, month)
    result = []

    target_weeks = _get_weeks_for_scope(year, month, today)

    for week_start in target_weeks:
        week_month = date(week_start.year, week_start.month, 1)

        for key, plan in plan_by_key.items():
            mk, co_norm, ci_norm, bsn_lower = key
            plan_month = date.fromisoformat(mk)

            if plan_month.year != week_month.year or plan_month.month != week_month.month:
                continue

            bsn = plan["business_slice_name"]
            co_full = plan["country"]
            ci = plan["city"]

            week_end = week_start + timedelta(days=6)
            cutoff_date = min(today, week_end)

            real_key = (week_start.isoformat(), co_norm, ci_norm, bsn_lower)
            real = real_map.get(real_key, {})

            row: Dict[str, Any] = {
                "country": co_full,
                "city": ci,
                "business_slice_name": bsn,
                "fleet_display_name": bsn,
                "is_subfleet": False,
                "subfleet_name": "",
                "week_start": week_start.isoformat(),
                "month": mk,
            }

            for kpi in PROJECTABLE_KPIS:
                plan_key = _plan_column(kpi)
                plan_total = _safe_float(plan.get(plan_key))

                curve = compute_weekly_expected_ratio(
                    _to_full_country(co_norm), ci, bsn, kpi,
                    week_start, cutoff_date, plan_month, conn=conn,
                )

                week_expected = plan_total * curve["expected_ratio_to_date"] if plan_total is not None else None
                week_plan_total = plan_total * curve.get("week_share_of_month", 0) if plan_total is not None else None

                real_kpi = _real_column(kpi)
                actual = _safe_float(real.get(real_kpi))

                attainment = None
                if actual is not None and week_expected is not None and week_expected > 0:
                    attainment = round((actual / week_expected) * 100.0, 2)

                gap = None
                if actual is not None and week_expected is not None:
                    gap = round(actual - week_expected, 2)

                row[kpi] = actual
                row[f"{kpi}_projected_total"] = round(week_plan_total, 2) if week_plan_total is not None else None
                row[f"{kpi}_projected_expected"] = round(week_expected, 2) if week_expected is not None else None
                row[f"{kpi}_attainment_pct"] = attainment
                row[f"{kpi}_gap_to_expected"] = gap
                row[f"{kpi}_gap_to_full"] = round(actual - week_plan_total, 2) if actual is not None and week_plan_total is not None else None
                row[f"{kpi}_completion_pct"] = round((actual / week_plan_total) * 100.0, 2) if actual is not None and week_plan_total and week_plan_total > 0 else None
                row[f"{kpi}_signal"] = _signal_from_attainment(attainment)
                row[f"{kpi}_curve_method"] = curve.get("curve_method", "linear_fallback")
                row[f"{kpi}_curve_confidence"] = curve.get("confidence", "fallback")
                row[f"{kpi}_fallback_level"] = curve.get("fallback_level", 5)
                row[f"{kpi}_expected_ratio"] = curve.get("expected_ratio_to_date", 0)

            result.append(row)

    result.sort(key=lambda r: (r.get("week_start", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    return result


def _build_daily(
    conn,
    plan_by_key: Dict[Tuple, Dict],
    today: date,
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> List[Dict[str, Any]]:
    real_map = _load_real_daily(conn, country, city, business_slice, year, month)
    result = []

    target_days = _get_days_for_scope(year, month, today)

    for trip_date in target_days:
        day_month = date(trip_date.year, trip_date.month, 1)

        for key, plan in plan_by_key.items():
            mk, co_norm, ci_norm, bsn_lower = key
            plan_month = date.fromisoformat(mk)

            if plan_month.year != day_month.year or plan_month.month != day_month.month:
                continue

            bsn = plan["business_slice_name"]
            co_full = plan["country"]
            ci = plan["city"]

            real_key = (trip_date.isoformat(), co_norm, ci_norm, bsn_lower)
            real = real_map.get(real_key, {})

            row: Dict[str, Any] = {
                "country": co_full,
                "city": ci,
                "business_slice_name": bsn,
                "fleet_display_name": bsn,
                "is_subfleet": False,
                "subfleet_name": "",
                "trip_date": trip_date.isoformat(),
                "month": _month_key(day_month),
            }

            for kpi in PROJECTABLE_KPIS:
                plan_key = _plan_column(kpi)
                plan_total = _safe_float(plan.get(plan_key))

                curve = compute_daily_expected_ratio(
                    _to_full_country(co_norm), ci, bsn, kpi,
                    trip_date, day_month, conn=conn,
                )

                daily_expected = plan_total * curve["expected_ratio_to_date"] if plan_total is not None else None

                real_kpi = _real_column(kpi)
                actual = _safe_float(real.get(real_kpi))

                attainment = None
                if actual is not None and daily_expected is not None and daily_expected > 0:
                    attainment = round((actual / daily_expected) * 100.0, 2)

                gap = None
                if actual is not None and daily_expected is not None:
                    gap = round(actual - daily_expected, 2)

                row[kpi] = actual
                row[f"{kpi}_projected_total"] = round(daily_expected, 2) if daily_expected is not None else None
                row[f"{kpi}_projected_expected"] = round(daily_expected, 2) if daily_expected is not None else None
                row[f"{kpi}_attainment_pct"] = attainment
                row[f"{kpi}_gap_to_expected"] = gap
                row[f"{kpi}_gap_to_full"] = gap
                row[f"{kpi}_completion_pct"] = attainment
                row[f"{kpi}_signal"] = _signal_from_attainment(attainment)
                row[f"{kpi}_curve_method"] = curve.get("curve_method", "linear_fallback")
                row[f"{kpi}_curve_confidence"] = curve.get("confidence", "fallback")
                row[f"{kpi}_fallback_level"] = curve.get("fallback_level", 5)
                row[f"{kpi}_expected_ratio"] = curve.get("expected_ratio_to_date", 0)

            result.append(row)

    result.sort(key=lambda r: (r.get("trip_date", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    return result


# ── Real data loaders ──────────────────────────────────────────────────────

def _load_real_monthly(conn, country, city, business_slice, year, month):
    clauses = ["(NOT is_subfleet OR is_subfleet IS NULL)"]
    params: List[Any] = []

    if country:
        cn = _norm_country(country)
        full = _to_full_country(cn)
        clauses.append("lower(trim(country)) = lower(trim(%s))")
        params.append(full)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    if business_slice:
        clauses.append("lower(trim(business_slice_name)) = lower(trim(%s))")
        params.append(business_slice.strip().lower())
    if year:
        clauses.append("EXTRACT(YEAR FROM month) = %s")
        params.append(year)
    if month:
        clauses.append("EXTRACT(MONTH FROM month) = %s")
        params.append(month)

    sql = f"""
        SELECT month, country, city, business_slice_name,
               trips_completed AS real_trips,
               COALESCE(revenue_yego_final, revenue_yego_net) AS real_revenue,
               active_drivers AS real_active_drivers
        FROM {FACT_MONTHLY}
        WHERE {' AND '.join(clauses)}
    """

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()

    result = {}
    for r in rows:
        mk = _month_key(r["month"])
        key = (mk,
               (r["country"] or "").strip().lower(),
               (r["city"] or "").strip().lower(),
               (r["business_slice_name"] or "").strip().lower())
        result[key] = dict(r)
    return result


def _load_real_weekly(conn, country, city, business_slice, year, month):
    clauses = ["(NOT is_subfleet OR is_subfleet IS NULL)"]
    params: List[Any] = []

    if country:
        cn = _norm_country(country)
        full = _to_full_country(cn)
        clauses.append("lower(trim(country)) = lower(trim(%s))")
        params.append(full)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    if business_slice:
        clauses.append("lower(trim(business_slice_name)) = lower(trim(%s))")
        params.append(business_slice.strip().lower())
    if year:
        clauses.append("EXTRACT(YEAR FROM week_start) = %s")
        params.append(year)
    if month:
        clauses.append("EXTRACT(MONTH FROM week_start) = %s")
        params.append(month)

    sql = f"""
        SELECT week_start, country, city, business_slice_name,
               trips_completed AS real_trips,
               COALESCE(revenue_yego_final, revenue_yego_net) AS real_revenue,
               active_drivers AS real_active_drivers
        FROM {FACT_WEEKLY}
        WHERE {' AND '.join(clauses)}
    """

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()

    result = {}
    for r in rows:
        ws = r["week_start"].isoformat() if hasattr(r["week_start"], "isoformat") else str(r["week_start"])[:10]
        key = (ws,
               (r["country"] or "").strip().lower(),
               (r["city"] or "").strip().lower(),
               (r["business_slice_name"] or "").strip().lower())
        result[key] = dict(r)
    return result


def _load_real_daily(conn, country, city, business_slice, year, month):
    clauses = ["(NOT is_subfleet OR is_subfleet IS NULL)"]
    params: List[Any] = []

    if country:
        cn = _norm_country(country)
        full = _to_full_country(cn)
        clauses.append("lower(trim(country)) = lower(trim(%s))")
        params.append(full)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    if business_slice:
        clauses.append("lower(trim(business_slice_name)) = lower(trim(%s))")
        params.append(business_slice.strip().lower())
    if year:
        clauses.append("EXTRACT(YEAR FROM trip_date) = %s")
        params.append(year)
    if month:
        clauses.append("EXTRACT(MONTH FROM trip_date) = %s")
        params.append(month)

    sql = f"""
        SELECT trip_date, country, city, business_slice_name,
               trips_completed AS real_trips,
               COALESCE(revenue_yego_final, revenue_yego_net) AS real_revenue,
               active_drivers AS real_active_drivers
        FROM {FACT_DAILY}
        WHERE {' AND '.join(clauses)}
    """

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()

    result = {}
    for r in rows:
        td = r["trip_date"].isoformat() if hasattr(r["trip_date"], "isoformat") else str(r["trip_date"])[:10]
        key = (td,
               (r["country"] or "").strip().lower(),
               (r["city"] or "").strip().lower(),
               (r["business_slice_name"] or "").strip().lower())
        result[key] = dict(r)
    return result


# ── Helpers ────────────────────────────────────────────────────────────────

def _plan_column(kpi: str) -> str:
    return {
        "trips_completed": "projected_trips",
        "revenue_yego_net": "projected_revenue",
        "active_drivers": "projected_active_drivers",
    }[kpi]


def _real_column(kpi: str) -> str:
    return {
        "trips_completed": "real_trips",
        "revenue_yego_net": "real_revenue",
        "active_drivers": "real_active_drivers",
    }[kpi]


def _build_no_plan_row(real_data: Dict, period_key: str, grain: str) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "country": real_data.get("country", ""),
        "city": real_data.get("city", ""),
        "business_slice_name": real_data.get("business_slice_name", ""),
        "fleet_display_name": real_data.get("business_slice_name", ""),
        "is_subfleet": False,
        "subfleet_name": "",
    }

    if grain == "monthly":
        row["month"] = period_key
    elif grain == "weekly":
        row["week_start"] = period_key
    else:
        row["trip_date"] = period_key

    for kpi in PROJECTABLE_KPIS:
        real_kpi = _real_column(kpi)
        actual = _safe_float(real_data.get(real_kpi))
        row[kpi] = actual
        row[f"{kpi}_projected_total"] = None
        row[f"{kpi}_projected_expected"] = None
        row[f"{kpi}_attainment_pct"] = None
        row[f"{kpi}_gap_to_expected"] = None
        row[f"{kpi}_gap_to_full"] = None
        row[f"{kpi}_completion_pct"] = None
        row[f"{kpi}_signal"] = "no_data"
        row[f"{kpi}_curve_method"] = None
        row[f"{kpi}_curve_confidence"] = None
        row[f"{kpi}_fallback_level"] = None
        row[f"{kpi}_expected_ratio"] = None

    return row


def _get_weeks_for_scope(year, month, today):
    if year and month:
        first = date(year, month, 1)
    elif year:
        first = date(year, 1, 1)
    else:
        first = date(today.year, today.month, 1)

    if month:
        last_day = date(year or today.year, month, 1)
        nxt = date(last_day.year + (last_day.month // 12), (last_day.month % 12) + 1, 1)
        last = nxt - timedelta(days=1)
    else:
        last = date(first.year, 12, 31)

    last = min(last, today)

    monday = first - timedelta(days=first.weekday())
    weeks = []
    while monday <= last:
        weeks.append(monday)
        monday += timedelta(days=7)
    return weeks


def _get_days_for_scope(year, month, today):
    if year and month:
        first = date(year, month, 1)
        nxt = date(first.year + (first.month // 12), (first.month % 12) + 1, 1)
        last = min(nxt - timedelta(days=1), today)
    elif year:
        first = date(year, 1, 1)
        last = min(date(year, 12, 31), today)
    else:
        first = date(today.year, today.month, 1)
        last = today

    days = []
    d = first
    while d <= last:
        days.append(d)
        d += timedelta(days=1)
    return days[-30:] if len(days) > 30 else days


def _compute_curve_summary(rows: List[Dict]) -> Dict[str, Any]:
    methods: Dict[str, int] = defaultdict(int)
    confidence_scores = {"high": 4, "medium": 3, "low": 2, "fallback": 1}
    conf_values = []

    for r in rows:
        for kpi in PROJECTABLE_KPIS:
            cm = r.get(f"{kpi}_curve_method")
            cc = r.get(f"{kpi}_curve_confidence")
            if cm:
                methods[cm] += 1
            if cc and cc in confidence_scores:
                conf_values.append(confidence_scores[cc])

    avg_conf_score = sum(conf_values) / len(conf_values) if conf_values else 0
    avg_label = "high" if avg_conf_score >= 3.5 else "medium" if avg_conf_score >= 2.5 else "low" if avg_conf_score >= 1.5 else "fallback"

    return {
        "total_combinations": len(rows) * len(PROJECTABLE_KPIS),
        "by_method": dict(methods),
        "avg_confidence": avg_label if conf_values else None,
    }
