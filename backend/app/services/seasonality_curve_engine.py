"""
Seasonality Curve Engine — distribución intra-periodo no lineal.

Calcula qué fracción del plan mensual se espera haber acumulado al día D,
basándose en la distribución histórica real de KPIs por día del mes.

Fallback jerárquico trazable:
  1. misma ciudad + misma tajada  (city_slice_Nm)
  2. misma ciudad, todas tajadas  (city_all_Nm)
  3. mismo país + misma tajada    (country_slice_Nm)
  4. mismo país, todas tajadas    (country_all_Nm)
  5. lineal                       (linear_fallback)

Fuente: ops.real_business_slice_day_fact (fact-first).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.business_slice_service import FACT_DAILY

logger = logging.getLogger(__name__)


def _smoothing_alpha_day() -> float:
    try:
        from app.settings import settings

        return float(getattr(settings, "PROJECTION_SMOOTHING_ALPHA_DAY", 0.7))
    except Exception:
        return 0.7


def _smoothing_alpha_week() -> float:
    try:
        from app.settings import settings

        return float(getattr(settings, "PROJECTION_SMOOTHING_ALPHA_WEEK", 0.7))
    except Exception:
        return 0.7


def _finalize_monthly_ratio_dict(result: Dict[str, Any], target_month: date, cutoff_day: int) -> Dict[str, Any]:
    """Alpha-blend: histórico vs progreso lineal cutoff/total_days (FASE Projection Integrity)."""
    total_days = _days_in_month(target_month.replace(day=1))
    linear_ratio = min(cutoff_day / total_days, 1.0) if total_days > 0 else 0.0
    alpha = _smoothing_alpha_day()
    raw = float(result.get("expected_ratio_to_date") or 0.0)
    smoothed = alpha * raw + (1.0 - alpha) * linear_ratio
    out = dict(result)
    out["expected_ratio_to_date"] = round(smoothed, 6)
    out["smoothing_applied_monthly"] = True
    return out


def _count_weeks_intersecting_month(month_start: date) -> int:
    """Cantidad de lunes (week_start ISO) cuya semana intersecta el mes calendar."""
    m0 = month_start.replace(day=1)
    nxt = date(m0.year + (m0.month // 12), (m0.month % 12) + 1, 1)
    month_end = nxt - timedelta(days=1)
    monday = m0 - timedelta(days=m0.weekday())
    n = 0
    while monday <= month_end:
        week_end = monday + timedelta(days=6)
        if week_end >= m0 and monday <= month_end:
            n += 1
        monday += timedelta(days=7)
    return max(n, 1)


DEFAULT_LOOKBACK_MONTHS = 3
MONTH_WEIGHTS = [0.5, 0.3, 0.2]

PROJECTABLE_KPIS = ("trips_completed", "revenue_yego_net", "active_drivers")

_CONFIDENCE_MAP = {
    1: "high",
    2: "medium",
    3: "medium",
    4: "low",
    5: "fallback",
}


def _previous_months(reference_month: date, n: int) -> List[date]:
    """Return first-of-month dates for the N months before reference_month (most recent first)."""
    result = []
    d = date(reference_month.year, reference_month.month, 1)
    for _ in range(n):
        d = (d - timedelta(days=1)).replace(day=1)
        result.append(d)
    return result


def _days_in_month(d: date) -> int:
    nxt = date(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return (nxt - d.replace(day=1)).days


def _fetch_daily_distribution(
    conn,
    months: List[date],
    kpi_column: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice_name: Optional[str] = None,
    _dist_cache: Optional[Dict] = None,
) -> Dict[str, List[Tuple[int, float]]]:
    """Fetch daily KPI values grouped by month.

    Returns {month_key: [(day_of_month, value), ...]} sorted by day.

    _dist_cache — diccionario compartido por request para evitar SQL repetidas para el
    mismo (months, kpi_col, country, city, bsn). Clave: tuple canónica de los parámetros.
    """
    if not months:
        return {}

    # ── Nivel 1 de caché: distribución histórica (evita SQL repetidas) ─────
    if _dist_cache is not None:
        dist_key = (
            tuple(m.strftime("%Y-%m-01") for m in months),
            kpi_column,
            (country or "").lower(),
            (city or "").lower(),
            (business_slice_name or "").lower(),
        )
        if dist_key in _dist_cache:
            return _dist_cache[dist_key]

    params: List[Any] = []
    clauses = ["1=1"]

    month_placeholders = []
    for m in months:
        month_placeholders.append("%s")
        params.append(m)
    clauses.append(f"date_trunc('month', trip_date)::date IN ({', '.join(month_placeholders)})")

    if country:
        clauses.append("lower(trim(country)) = lower(trim(%s))")
        params.append(country)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city)
    if business_slice_name:
        clauses.append("lower(trim(business_slice_name)) = lower(trim(%s))")
        params.append(business_slice_name)

    clauses.append("(NOT is_subfleet OR is_subfleet IS NULL)")

    sql = f"""
        SELECT
            date_trunc('month', trip_date)::date AS month_key,
            EXTRACT(DAY FROM trip_date)::int AS day_of_month,
            COALESCE(SUM({kpi_column}), 0) AS daily_value
        FROM {FACT_DAILY}
        WHERE {' AND '.join(clauses)}
        GROUP BY month_key, day_of_month
        ORDER BY month_key, day_of_month
    """

    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()

    result: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
    for r in rows:
        mk = r["month_key"].strftime("%Y-%m-01") if hasattr(r["month_key"], "strftime") else str(r["month_key"])[:10]
        result[mk].append((int(r["day_of_month"]), float(r["daily_value"])))

    final = dict(result)
    if _dist_cache is not None:
        _dist_cache[dist_key] = final   # almacenar para futuros lookups
    return final


def _compute_cumulative_ratio(daily_values: List[Tuple[int, float]], cutoff_day: int) -> Optional[float]:
    """Compute the cumulative ratio: sum(day 1..cutoff_day) / sum(all days)."""
    if not daily_values:
        return None
    total = sum(v for _, v in daily_values)
    if total <= 0:
        return None
    accumulated = sum(v for d, v in daily_values if d <= cutoff_day)
    return accumulated / total


def _weighted_average(values: List[Optional[float]], weights: List[float]) -> Optional[float]:
    """Weighted average, skipping None values."""
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None]
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    if total_w <= 0:
        return None
    return sum(v * w for v, w in pairs) / total_w


def compute_expected_ratio(
    country: str,
    city: str,
    business_slice_name: str,
    kpi: str,
    target_month: date,
    cutoff_day: int,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    conn=None,
    _cache: Optional[Dict] = None,
    _dist_cache: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Compute the expected ratio to date for a KPI using hierarchical fallback.

    Returns dict with expected_ratio_to_date, curve_method, fallback_level, etc.

    Parámetros de caché por request (opcionales):
      _cache      — dict compartido para resultados completos; evita recálculo para
                    misma (country, city, bsn, kpi, month, cutoff_day).
      _dist_cache — dict compartido para distribuciones históricas; evita SQL repetidas
                    para misma combinación geo+kpi.
    """
    result_key = (
        (country or "").lower(),
        (city or "").lower(),
        (business_slice_name or "").lower(),
        kpi,
        target_month.strftime("%Y-%m-01"),
        cutoff_day,
        lookback_months,
    )
    # Almacenamos ratio *pre-smoothing* en caché; el blend α se aplica al leer/devolver.
    if _cache is not None and result_key in _cache:
        return _finalize_monthly_ratio_dict(dict(_cache[result_key]), target_month, cutoff_day)

    months = _previous_months(target_month, lookback_months)
    weights = MONTH_WEIGHTS[:lookback_months]
    while len(weights) < lookback_months:
        weights.append(weights[-1] if weights else 1.0)

    kpi_col = _kpi_to_column(kpi)

    own_conn = None
    if conn is None:
        own_conn = get_db().__enter__()
        conn = own_conn

    try:
        result = _try_level(conn, months, kpi_col, weights, cutoff_day,
                            country=country, city=city,
                            business_slice_name=business_slice_name,
                            level=1, method=f"city_slice_{lookback_months}m",
                            _dist_cache=_dist_cache)
        if result:
            if _cache is not None:
                _cache[result_key] = result
            return _finalize_monthly_ratio_dict(result, target_month, cutoff_day)

        result = _try_level(conn, months, kpi_col, weights, cutoff_day,
                            country=country, city=city,
                            business_slice_name=None,
                            level=2, method=f"city_all_{lookback_months}m",
                            _dist_cache=_dist_cache)
        if result:
            if _cache is not None:
                _cache[result_key] = result
            return _finalize_monthly_ratio_dict(result, target_month, cutoff_day)

        result = _try_level(conn, months, kpi_col, weights, cutoff_day,
                            country=country, city=None,
                            business_slice_name=business_slice_name,
                            level=3, method=f"country_slice_{lookback_months}m",
                            _dist_cache=_dist_cache)
        if result:
            if _cache is not None:
                _cache[result_key] = result
            return _finalize_monthly_ratio_dict(result, target_month, cutoff_day)

        result = _try_level(conn, months, kpi_col, weights, cutoff_day,
                            country=country, city=None,
                            business_slice_name=None,
                            level=4, method=f"country_all_{lookback_months}m",
                            _dist_cache=_dist_cache)
        if result:
            if _cache is not None:
                _cache[result_key] = result
            return _finalize_monthly_ratio_dict(result, target_month, cutoff_day)

        total_days = _days_in_month(target_month.replace(day=1))
        linear_ratio = min(cutoff_day / total_days, 1.0) if total_days > 0 else 0.0
        fallback_result = {
            "expected_ratio_to_date": linear_ratio,
            "curve_method": "linear_fallback",
            "historical_window_months": 0,
            "seasonality_source": "none",
            "fallback_level": 5,
            "day_weights_used": [],
            "confidence": "fallback",
        }
        if _cache is not None:
            _cache[result_key] = fallback_result
        return _finalize_monthly_ratio_dict(fallback_result, target_month, cutoff_day)
    finally:
        if own_conn is not None:
            try:
                own_conn.close()
            except Exception:
                pass


def _try_level(
    conn,
    months: List[date],
    kpi_col: str,
    weights: List[float],
    cutoff_day: int,
    country: Optional[str],
    city: Optional[str],
    business_slice_name: Optional[str],
    level: int,
    method: str,
    _dist_cache: Optional[Dict] = None,
) -> Optional[Dict[str, Any]]:
    dist = _fetch_daily_distribution(conn, months, kpi_col,
                                     country=country, city=city,
                                     business_slice_name=business_slice_name,
                                     _dist_cache=_dist_cache)
    if not dist:
        return None

    ratios = []
    month_keys_used = []
    for m in months:
        mk = m.strftime("%Y-%m-01")
        daily = dist.get(mk)
        if daily:
            ratio = _compute_cumulative_ratio(daily, cutoff_day)
            ratios.append(ratio)
            if ratio is not None:
                month_keys_used.append(mk)
        else:
            ratios.append(None)

    avg = _weighted_average(ratios, weights)
    if avg is None:
        return None

    return {
        "expected_ratio_to_date": round(avg, 6),
        "curve_method": method,
        "historical_window_months": len(month_keys_used),
        "seasonality_source": FACT_DAILY,
        "fallback_level": level,
        "day_weights_used": weights[:len(month_keys_used)],
        "confidence": _CONFIDENCE_MAP.get(level, "low"),
        "historical_months_used": month_keys_used,
    }


def _kpi_to_column(kpi: str) -> str:
    mapping = {
        "trips_completed": "trips_completed",
        "revenue_yego_net": "COALESCE(revenue_yego_final, revenue_yego_net)",
        "active_drivers": "active_drivers",
    }
    return mapping.get(kpi, kpi)


def compute_weekly_expected_ratio(
    country: str,
    city: str,
    business_slice_name: str,
    kpi: str,
    week_start: date,
    cutoff_date: date,
    target_month: date,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    conn=None,
    _cache: Optional[Dict] = None,
    _dist_cache: Optional[Dict] = None,
) -> Dict[str, Any]:
    """For weekly grain: expected ratio of the month that falls within this week,
    up to cutoff_date.

    _cache / _dist_cache — dicts compartidos por request para eliminar SQL y
    recálculos redundantes. Pásalos desde _build_weekly.
    """
    month_start = target_month.replace(day=1)

    week_end = week_start + timedelta(days=6)
    effective_start = max(week_start, month_start)
    month_end = date(month_start.year + (month_start.month // 12),
                     (month_start.month % 12) + 1, 1) - timedelta(days=1)
    effective_end = min(week_end, month_end)

    week_end_day = effective_end.day
    week_start_day = max(effective_start.day - 1, 0)

    def _ratio(cutoff_day: int):
        return compute_expected_ratio(
            country, city, business_slice_name, kpi,
            target_month, cutoff_day, lookback_months, conn,
            _cache=_cache, _dist_cache=_dist_cache,
        )

    month_ratio_full   = _ratio(week_end_day)
    month_ratio_before = _ratio(week_start_day) if week_start_day > 0 else {"expected_ratio_to_date": 0.0}

    week_share = month_ratio_full["expected_ratio_to_date"] - month_ratio_before.get("expected_ratio_to_date", 0.0)
    n_weeks = _count_weeks_intersecting_month(month_start)
    uniform_share = 1.0 / n_weeks if n_weeks > 0 else week_share
    alpha_w = _smoothing_alpha_week()
    week_share = alpha_w * week_share + (1.0 - alpha_w) * uniform_share

    effective_cutoff = min(cutoff_date, effective_end)
    if effective_cutoff < effective_start:
        progress_within_week = 0.0
    else:
        cutoff_day_ratio = _ratio(effective_cutoff.day)
        progress_within_week = (
            cutoff_day_ratio["expected_ratio_to_date"] - month_ratio_before.get("expected_ratio_to_date", 0.0)
        )

    return {
        "expected_ratio_to_date": round(progress_within_week, 6),
        "week_share_of_month":    round(week_share, 6),
        "curve_method":           month_ratio_full.get("curve_method", "linear_fallback"),
        "historical_window_months": month_ratio_full.get("historical_window_months", 0),
        "seasonality_source":     month_ratio_full.get("seasonality_source", "none"),
        "fallback_level":         month_ratio_full.get("fallback_level", 5),
        "day_weights_used":       month_ratio_full.get("day_weights_used", []),
        "confidence":             month_ratio_full.get("confidence", "fallback"),
    }


def compute_daily_expected_ratio(
    country: str,
    city: str,
    business_slice_name: str,
    kpi: str,
    trip_date: date,
    target_month: date,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    conn=None,
    _cache: Optional[Dict] = None,
    _dist_cache: Optional[Dict] = None,
) -> Dict[str, Any]:
    """For daily grain: expected ratio of the month that falls on this specific day.

    _cache / _dist_cache — dicts compartidos por request. Pásalos desde _build_daily.
    """
    day_of_month = trip_date.day
    prev_day = day_of_month - 1

    def _ratio(cutoff_day: int):
        return compute_expected_ratio(
            country, city, business_slice_name, kpi,
            target_month, cutoff_day, lookback_months, conn,
            _cache=_cache, _dist_cache=_dist_cache,
        )

    ratio_to_day  = _ratio(day_of_month)
    ratio_to_prev = _ratio(prev_day) if prev_day > 0 else {"expected_ratio_to_date": 0.0}

    daily_share = ratio_to_day["expected_ratio_to_date"] - ratio_to_prev.get("expected_ratio_to_date", 0.0)
    total_days = _days_in_month(target_month.replace(day=1))
    uniform_day = (1.0 / total_days) if total_days > 0 else daily_share
    alpha_d = _smoothing_alpha_day()
    daily_share = alpha_d * daily_share + (1.0 - alpha_d) * uniform_day

    return {
        "expected_ratio_to_date":   round(daily_share, 6),
        "curve_method":             ratio_to_day.get("curve_method", "linear_fallback"),
        "historical_window_months": ratio_to_day.get("historical_window_months", 0),
        "seasonality_source":       ratio_to_day.get("seasonality_source", "none"),
        "fallback_level":           ratio_to_day.get("fallback_level", 5),
        "day_weights_used":         ratio_to_day.get("day_weights_used", []),
        "confidence":               ratio_to_day.get("confidence", "fallback"),
    }
