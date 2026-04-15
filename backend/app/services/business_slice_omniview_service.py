"""
Business Slice Omniview — modelo canónico backend (REAL only, sin Plan).

Fuentes (fact-first discipline):
- monthly: ops.real_business_slice_month_fact
- weekly: ops.real_business_slice_week_fact
- daily: ops.real_business_slice_day_fact

Resolved view (ops.v_real_trips_business_slice_resolved) is retained for
build/reconciliation only and NOT used for normal serving.

Comparativos:
- monthly: MoM (mes civil vs mes anterior)
- weekly: WoW (semana ISO, lunes = trip_week del pipeline)
- daily: fecha vs fecha - 7 días (mismo día de semana anterior)

Guardrails: weekly/daily exigen country; daily_window_days <= 120.

Ratios en subtotales/totals: se recomputan desde sumas (no promedio de ratios).
Ver docs/BUSINESS_SLICE_OMNIVIEW_BACKEND.md.
"""
from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db, get_db_drill
from app.services.business_slice_service import (
    FACT_DAILY,
    FACT_MONTHLY,
    FACT_WEEKLY,
    V_RESOLVED,
    _json_safe_scalar,
)
from app.services.serving_guardrails import (
    QueryMode as _QM,
    ServingPolicy,
    SourceType as _ST,
    context_from_policy,
    execute_db_gated_query,
    register_policy,
)

_SERVING_POLICY = ServingPolicy(
    feature_name="Omniview Matrix",
    query_mode=_QM.SERVING,
    preferred_source=FACT_MONTHLY,
    preferred_source_type=_ST.FACT,
    forbidden_sources=[
        "ops.v_real_trips_business_slice_resolved",
        "ops.v_real_trips_enriched_base",
    ],
    strict_mode=True,
    require_preferred_source_match=True,
)
register_policy(_SERVING_POLICY)

# --- Umbrales señalización (contractuales) ---
THRESHOLD_DELTA_PCT_POINTS: float = 5.0  # variación relativa % (ej. +5% viajes)
THRESHOLD_DELTA_PP: float = 0.5  # puntos porcentuales (take rate, cancel rate)

Granularity = Literal["monthly", "weekly", "daily"]
MetricDirection = Literal["higher_better", "lower_better", "neutral"]
MetricSignal = Literal["positive", "negative", "neutral", "no_data"]

DIM_KEY_FIELDS = (
    "country",
    "city",
    "business_slice_name",
    "fleet_display_name",
    "is_subfleet",
    "subfleet_name",
    "parent_fleet_name",
)

# Contrato de unidades (API / UI): commission alineado al fact mensual en ratio 0–1.
OMNIVIEW_UNITS_CONTRACT: dict[str, Any] = {
    "commission_pct": {
        "storage": "ratio",
        "range": "0_to_1",
        "ui_hint": "Multiplicar por 100 para % take rate",
    },
    "cancel_rate_pct": {
        "storage": "percent",
        "range": "0_to_100",
        "ui_hint": "Porcentaje de cancelaciones sobre completados+cancelados",
    },
    "revenue_yego_net": {
        "storage": "currency_amount",
        "note": "Moneda según país; sin FX en este endpoint",
    },
    "avg_ticket": {
        "storage": "currency_amount",
        "note": "Media de ticket en agregado; moneda según país",
    },
    "trips_completed": {"storage": "count"},
    "trips_cancelled": {"storage": "count"},
    "active_drivers": {"storage": "count"},
    "trips_per_driver": {"storage": "ratio", "note": "Viajes completados por conductor activo"},
}


def _month_add_first(d: date, delta_months: int) -> date:
    """Primer día del mes tras sumar delta_months al mes de d (d debe ser primer día de mes)."""
    y, m = d.year, d.month + delta_months
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return date(y, m, 1)


def _last_day_of_month(d: date) -> date:
    _, last = calendar.monthrange(d.year, d.month)
    return date(d.year, d.month, last)


def _iso_week_monday(d: date) -> date:
    """Lunes ISO de la semana que contiene d (alineado a date_trunc('week', ...) en PG)."""
    return d - timedelta(days=d.weekday())


def _parse_period_anchor(granularity: Granularity, period: Optional[str]) -> date:
    """Ancla de periodo desde string YYYY-MM-DD / YYYY-MM."""
    today = date.today()
    if not period or not str(period).strip():
        if granularity == "monthly":
            return date(today.year, today.month, 1)
        if granularity == "weekly":
            return _iso_week_monday(today)
        return today - timedelta(days=1)
    s = str(period).strip()[:10]
    parts = s.split("-")
    if len(parts) < 2:
        raise ValueError("period debe ser YYYY-MM o YYYY-MM-DD")
    y, m = int(parts[0]), int(parts[1])
    if granularity == "monthly":
        return date(y, m, 1)
    if len(parts) >= 3:
        return date(y, m, int(parts[2]))
    if granularity == "weekly":
        return _iso_week_monday(date(y, m, 1))
    raise ValueError("daily requiere period YYYY-MM-DD")


@dataclass
class PeriodWindows:
    current_start: date
    current_end_exclusive: date
    previous_start: date
    previous_end_exclusive: date
    comparison_rule: str
    is_current_partial: bool
    is_previous_partial: bool


def resolve_period_windows(granularity: Granularity, anchor: date) -> PeriodWindows:
    today = date.today()
    if granularity == "monthly":
        cur_start = date(anchor.year, anchor.month, 1)
        prev_start = _month_add_first(cur_start, -1)
        cur_end = _month_add_first(cur_start, 1)
        prev_end = cur_start
        rule = "MoM"
        is_cur_partial = cur_start <= today < cur_end
        is_prev_partial = prev_start <= today < prev_end  # normalmente False
    elif granularity == "weekly":
        cur_start = _iso_week_monday(anchor)
        prev_start = cur_start - timedelta(days=7)
        cur_end = cur_start + timedelta(days=7)
        prev_end = cur_start
        rule = "WoW"
        is_cur_partial = cur_start <= today < cur_end
        is_prev_partial = prev_start <= today < prev_end
    else:
        cur_start = anchor
        prev_start = anchor - timedelta(days=7)
        cur_end = cur_start + timedelta(days=1)
        prev_end = prev_start + timedelta(days=1)
        rule = "DoW_minus_7"
        is_cur_partial = cur_start == today
        is_prev_partial = prev_start == today
    return PeriodWindows(
        current_start=cur_start,
        current_end_exclusive=cur_end,
        previous_start=prev_start,
        previous_end_exclusive=prev_end,
        comparison_rule=rule,
        is_current_partial=is_cur_partial,
        is_previous_partial=is_prev_partial,
    )


def validate_omniview_params(
    granularity: str,
    country: Optional[str],
    daily_window_days: int,
) -> Granularity:
    if granularity not in ("monthly", "weekly", "daily"):
        raise ValueError("granularity debe ser monthly, weekly o daily")
    g: Granularity = granularity  # type: ignore[assignment]
    if g in ("weekly", "daily"):
        if not country or not str(country).strip():
            raise ValueError("country es obligatorio para weekly y daily")
    if daily_window_days < 1 or daily_window_days > 120:
        raise ValueError("daily_window_days debe estar entre 1 y 120")
    return g


def dim_key(row: dict[str, Any]) -> tuple:
    return tuple(row.get(k) for k in DIM_KEY_FIELDS)


def commission_pct_from_sums(revenue_sum: Any, total_fare_sum: Any) -> Optional[float]:
    """Misma semántica que loader: SUM(revenue) / SUM(total_fare) con total_fare > 0."""
    if revenue_sum is None or total_fare_sum is None:
        return None
    try:
        tr = float(total_fare_sum)
        rev = float(revenue_sum)
    except (TypeError, ValueError):
        return None
    if tr <= 0:
        return None
    return rev / tr


def cancel_rate_pct_from_counts(trips_completed: Any, trips_cancelled: Any) -> Optional[float]:
    tc = int(trips_completed or 0)
    cx = int(trips_cancelled or 0)
    den = tc + cx
    if den == 0:
        return None
    return 100.0 * float(cx) / float(den)


def trips_per_driver_from_counts(trips_completed: Any, active_drivers: Any) -> Optional[float]:
    tc = int(trips_completed or 0)
    ad = int(active_drivers or 0)
    if ad <= 0:
        return None
    return float(tc) / float(ad)


def build_metrics_from_components(c: dict[str, Any]) -> dict[str, Any]:
    """Construye métricas V1 a partir de fila agregada (con o sin componentes)."""
    tc = int(c.get("trips_completed") or 0)
    cx = int(c.get("trips_cancelled") or 0)
    ad = c.get("active_drivers")
    ad_i = int(ad) if ad is not None else 0
    avg_ticket = _json_safe_scalar(c.get("avg_ticket"))
    revenue = _json_safe_scalar(c.get("revenue_yego_net"))
    cr_sum = c.get("completed_revenue_sum")
    tf_sum = c.get("completed_total_fare_sum")
    if cr_sum is not None and tf_sum is not None:
        comm = commission_pct_from_sums(cr_sum, tf_sum)
    else:
        comm = _json_safe_scalar(c.get("commission_pct"))
    tpd = trips_per_driver_from_counts(tc, ad_i) if ad is not None else None
    if tpd is None and c.get("trips_per_driver") is not None:
        tpd = _json_safe_scalar(c.get("trips_per_driver"))
    cr_pct = cancel_rate_pct_from_counts(tc, cx)
    return {
        "trips_completed": tc,
        "trips_cancelled": cx,
        "active_drivers": ad_i if ad is not None else None,
        "avg_ticket": avg_ticket,
        "revenue_yego_net": revenue,
        "commission_pct": comm,
        "trips_per_driver": tpd,
        "cancel_rate_pct": cr_pct,
    }


def merge_component_rows_for_rollup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Suma componentes para rollup; active_drivers no es sumable (se deja None)."""
    out: dict[str, Any] = {
        "trips_completed": 0,
        "trips_cancelled": 0,
        "completed_revenue_sum": Decimal("0"),
        "completed_total_fare_sum": Decimal("0"),
        "completed_ticket_weighted_num": Decimal("0"),
    }
    for r in rows:
        out["trips_completed"] += int(r.get("trips_completed") or 0)
        out["trips_cancelled"] += int(r.get("trips_cancelled") or 0)
        cr = r.get("completed_revenue_sum")
        tf = r.get("completed_total_fare_sum")
        if cr is not None:
            out["completed_revenue_sum"] += Decimal(str(cr))
        if tf is not None:
            out["completed_total_fare_sum"] += Decimal(str(tf))
        tc = int(r.get("trips_completed") or 0)
        at = r.get("avg_ticket")
        if tc > 0 and at is not None:
            out["completed_ticket_weighted_num"] += Decimal(str(at)) * tc
    tc = out["trips_completed"]
    out["revenue_yego_net"] = float(out["completed_revenue_sum"]) if tc else None
    out["avg_ticket"] = (
        float(out["completed_ticket_weighted_num"] / tc) if tc > 0 else None
    )
    out["commission_pct"] = commission_pct_from_sums(
        out["completed_revenue_sum"], out["completed_total_fare_sum"]
    )
    out["active_drivers"] = None
    out["trips_per_driver"] = None
    out["cancel_rate_pct"] = cancel_rate_pct_from_counts(
        out["trips_completed"], out["trips_cancelled"]
    )
    return out


METRIC_DIRECTIONS: dict[str, MetricDirection] = {
    "trips_completed": "higher_better",
    "trips_cancelled": "lower_better",
    "active_drivers": "higher_better",
    "avg_ticket": "neutral",
    "revenue_yego_net": "higher_better",
    "commission_pct": "neutral",
    "trips_per_driver": "higher_better",
    "cancel_rate_pct": "lower_better",
}


def _metric_kind_for_threshold(metric_key: str) -> Literal["pp", "rel"]:
    if metric_key in ("commission_pct", "cancel_rate_pct"):
        return "pp"
    return "rel"


def compute_signal_for_metric(
    metric_key: str,
    current: Any,
    previous: Any,
    delta_pct: Optional[float],
    delta_abs_pp: Optional[float],
) -> MetricSignal:
    direction = METRIC_DIRECTIONS[metric_key]
    if direction == "neutral":
        if current is None or previous is None:
            return "no_data"
        return "neutral"
    if current is None or previous is None:
        return "no_data"
    kind = _metric_kind_for_threshold(metric_key)
    if kind == "pp":
        if delta_abs_pp is None:
            return "neutral"
        if abs(delta_abs_pp) < THRESHOLD_DELTA_PP:
            return "neutral"
        up = delta_abs_pp > 0
    else:
        if delta_pct is None:
            return "neutral"
        if abs(delta_pct) < THRESHOLD_DELTA_PCT_POINTS:
            return "neutral"
        up = delta_pct > 0
    if direction == "higher_better":
        return "positive" if up else "negative"
    return "positive" if not up else "negative"


def compute_deltas(
    cur: dict[str, Any], prev: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, MetricSignal], bool, Optional[str]]:
    """Devuelve (delta_dict, signals_dict, not_comparable, reason)."""
    signals: dict[str, MetricSignal] = {}
    deltas: dict[str, Any] = {}
    not_comp = False
    reason: Optional[str] = None
    keys = [
        "trips_completed",
        "trips_cancelled",
        "active_drivers",
        "avg_ticket",
        "revenue_yego_net",
        "commission_pct",
        "trips_per_driver",
        "cancel_rate_pct",
    ]
    for k in keys:
        c = cur.get(k)
        p = prev.get(k)
        entry: dict[str, Any] = {"delta_abs": None, "delta_pct": None, "delta_abs_pp": None}
        if c is None and p is None:
            signals[k] = "no_data"
            deltas[k] = entry
            continue
        if p is None:
            entry["delta_abs"] = None
            entry["delta_pct"] = None
            signals[k] = "no_data"
            not_comp = True
            reason = reason or "previous_missing"
            deltas[k] = entry
            continue
        if c is None and k in ("trips_completed", "trips_cancelled"):
            c = 0
        if c is None:
            signals[k] = "no_data"
            not_comp = True
            reason = reason or "current_missing"
            deltas[k] = entry
            continue
        try:
            fc, fp = float(c), float(p)
        except (TypeError, ValueError):
            signals[k] = "no_data"
            deltas[k] = entry
            continue
        if math.isnan(fc) or math.isinf(fc) or math.isnan(fp) or math.isinf(fp):
            signals[k] = "no_data"
            deltas[k] = entry
            continue
        entry["delta_abs"] = fc - fp
        if k == "commission_pct":
            entry["delta_abs_pp"] = (fc - fp) * 100.0
            if fp != 0:
                entry["delta_pct"] = (fc / fp - 1.0) * 100.0
            else:
                entry["delta_pct"] = None
                if fc != 0:
                    not_comp = True
                    reason = reason or "pct_base_zero"
        elif k == "cancel_rate_pct":
            entry["delta_abs_pp"] = fc - fp
            if fp != 0:
                entry["delta_pct"] = (fc / fp - 1.0) * 100.0
            else:
                entry["delta_pct"] = None
                if fc != 0:
                    not_comp = True
                    reason = reason or "pct_base_zero"
        else:
            if fp != 0:
                entry["delta_pct"] = (fc / fp - 1.0) * 100.0
            else:
                entry["delta_pct"] = None
                if fc != 0:
                    not_comp = True
                    reason = reason or "pct_base_zero"
        signals[k] = compute_signal_for_metric(
            k, c, p, entry.get("delta_pct"), entry.get("delta_abs_pp")
        )
        deltas[k] = entry
    return deltas, signals, not_comp, reason


# --- SQL builders ---

_AGG_SELECT_RESOLVED = """
    COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
    COUNT(*) FILTER (WHERE cancelled_flag) AS trips_cancelled,
    COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers,
    AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL) AS avg_ticket,
    SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS completed_revenue_sum,
    SUM(total_fare) FILTER (
        WHERE completed_flag AND total_fare IS NOT NULL AND total_fare > 0
    ) AS completed_total_fare_sum,
    CASE
        WHEN SUM(total_fare) FILTER (
            WHERE completed_flag AND total_fare IS NOT NULL AND total_fare > 0
        ) > 0
        THEN SUM(revenue_yego_net) FILTER (
            WHERE completed_flag AND total_fare IS NOT NULL AND total_fare > 0
        ) / SUM(total_fare) FILTER (
            WHERE completed_flag AND total_fare IS NOT NULL AND total_fare > 0
        )
        ELSE NULL
    END AS commission_pct,
    CASE
        WHEN COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) > 0
        THEN COUNT(*) FILTER (WHERE completed_flag)::numeric
            / COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)
        ELSE NULL
    END AS trips_per_driver,
    SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net
"""


def _filters_resolved(
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    fleet: Optional[str],
    subfleet: Optional[str],
    include_subfleets: bool,
) -> tuple[list[str], list[Any]]:
    w: list[str] = []
    p: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        p.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        p.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append(
            "business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(business_slice).strip())
    if fleet and str(fleet).strip():
        w.append(
            "fleet_display_name IS NOT NULL AND LOWER(TRIM(fleet_display_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(fleet).strip())
    if subfleet and str(subfleet).strip():
        w.append(
            "subfleet_name IS NOT NULL AND LOWER(TRIM(subfleet_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(subfleet).strip())
    if not include_subfleets:
        w.append("is_subfleet IS NOT TRUE")
    return w, p


def _fetch_resolved_slice_rows(
    cur,
    time_predicate_sql: str,
    time_params: list[Any],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    fleet: Optional[str],
    subfleet: Optional[str],
    include_subfleets: bool,
    limit: int,
) -> list[dict[str, Any]]:
    fw, fp = _filters_resolved(country, city, business_slice, fleet, subfleet, include_subfleets)
    where = ["resolution_status = 'resolved'", time_predicate_sql] + fw
    sql = f"""
        SELECT
            country, city, business_slice_name, fleet_display_name,
            is_subfleet, subfleet_name, parent_fleet_name,
            {_AGG_SELECT_RESOLVED}
        FROM {V_RESOLVED}
        WHERE {" AND ".join(where)}
        GROUP BY country, city, business_slice_name, fleet_display_name,
                 is_subfleet, subfleet_name, parent_fleet_name
        ORDER BY trips_completed DESC
        LIMIT %s
    """
    params = time_params + fp + [min(max(limit, 1), 10000)]
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def _fetch_resolved_rollup_by_country(
    cur,
    time_predicate_sql: str,
    time_params: list[Any],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    fleet: Optional[str],
    subfleet: Optional[str],
    include_subfleets: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fw, fp = _filters_resolved(country, city, business_slice, fleet, subfleet, include_subfleets)
    base_where = ["resolution_status = 'resolved'", time_predicate_sql] + fw
    wh = " AND ".join(base_where)
    cur.execute(
        f"""
        SELECT country,
               {_AGG_SELECT_RESOLVED}
        FROM {V_RESOLVED}
        WHERE {wh}
        GROUP BY country
        ORDER BY country
        """,
        time_params + fp,
    )
    by_country = [dict(r) for r in cur.fetchall()]
    cur.execute(
        f"""
        SELECT {_AGG_SELECT_RESOLVED}
        FROM {V_RESOLVED}
        WHERE {wh}
        """,
        time_params + fp,
    )
    total_row = cur.fetchone()
    total = dict(total_row) if total_row else {}
    return by_country, total


def _filters_fact(
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    fleet: Optional[str],
    subfleet: Optional[str],
    include_subfleets: bool,
) -> tuple[list[str], list[Any]]:
    """Shared filter builder for fact tables (same column names as resolved)."""
    w: list[str] = []
    p: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        p.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        p.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append("business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))")
        p.append(str(business_slice).strip())
    if fleet and str(fleet).strip():
        w.append("fleet_display_name IS NOT NULL AND LOWER(TRIM(fleet_display_name::text)) = LOWER(TRIM(%s))")
        p.append(str(fleet).strip())
    if subfleet and str(subfleet).strip():
        w.append("subfleet_name IS NOT NULL AND LOWER(TRIM(subfleet_name::text)) = LOWER(TRIM(%s))")
        p.append(str(subfleet).strip())
    if not include_subfleets:
        w.append("is_subfleet IS NOT TRUE")
    return w, p


def _fetch_fact_slice_rows(
    cur,
    fact_table: str,
    time_column: str,
    time_value: Any,
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    fleet: Optional[str],
    subfleet: Optional[str],
    include_subfleets: bool,
    limit: int,
) -> list[dict[str, Any]]:
    """Fact-first replacement for _fetch_resolved_slice_rows: reads pre-aggregated facts."""
    fw, fp = _filters_fact(country, city, business_slice, fleet, subfleet, include_subfleets)
    where = [f"{time_column} = %s"] + fw
    sql = f"""
        SELECT country, city, business_slice_name, fleet_display_name,
               is_subfleet, subfleet_name, parent_fleet_name,
               trips_completed, trips_cancelled, active_drivers,
               avg_ticket, commission_pct, trips_per_driver,
               revenue_yego_net,
               COALESCE(revenue_yego_final, revenue_yego_net) AS completed_revenue_sum,
               total_fare_completed_positive_sum AS completed_total_fare_sum
        FROM {fact_table}
        WHERE {" AND ".join(where)}
        ORDER BY trips_completed DESC
        LIMIT %s
    """
    params = [time_value] + fp + [min(max(limit, 1), 10000)]
    _ctx = context_from_policy(_SERVING_POLICY, source_name=fact_table)
    return execute_db_gated_query(
        _ctx, _SERVING_POLICY, cur, sql, params,
        source_name=fact_table, source_type="fact",
    )


def _fetch_fact_rollup_by_country(
    cur,
    fact_table: str,
    time_column: str,
    time_value: Any,
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    fleet: Optional[str],
    subfleet: Optional[str],
    include_subfleets: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fact-first replacement for _fetch_resolved_rollup_by_country: rollups from pre-aggregated facts."""
    fw, fp = _filters_fact(country, city, business_slice, fleet, subfleet, include_subfleets)
    where = [f"{time_column} = %s"] + fw
    wh = " AND ".join(where)
    agg = """
        SUM(trips_completed) AS trips_completed,
        SUM(trips_cancelled) AS trips_cancelled,
        SUM(active_drivers) AS active_drivers,
        CASE WHEN SUM(trips_completed) > 0
             THEN SUM(COALESCE(avg_ticket, 0) * trips_completed) / SUM(trips_completed)
             ELSE NULL END AS avg_ticket,
        SUM(COALESCE(revenue_yego_final, revenue_yego_net, 0)) AS completed_revenue_sum,
        SUM(total_fare_completed_positive_sum) AS completed_total_fare_sum,
        CASE WHEN SUM(total_fare_completed_positive_sum) > 0
             THEN SUM(COALESCE(revenue_yego_final, revenue_yego_net, 0))
                  / NULLIF(SUM(total_fare_completed_positive_sum), 0)
             ELSE NULL END AS commission_pct,
        CASE WHEN SUM(active_drivers) > 0
             THEN SUM(trips_completed)::numeric / SUM(active_drivers)
             ELSE NULL END AS trips_per_driver,
        SUM(COALESCE(revenue_yego_final, revenue_yego_net, 0)) AS revenue_yego_net
    """
    params = [time_value] + fp
    _ctx = context_from_policy(_SERVING_POLICY, source_name=fact_table)
    by_country = execute_db_gated_query(
        _ctx, _SERVING_POLICY, cur,
        f"SELECT country, {agg} FROM {fact_table} WHERE {wh} GROUP BY country ORDER BY country",
        params, source_name=fact_table, source_type="fact",
    )
    total_rows = execute_db_gated_query(
        _ctx, _SERVING_POLICY, cur,
        f"SELECT {agg} FROM {fact_table} WHERE {wh}",
        params, source_name=fact_table, source_type="fact",
    )
    total = total_rows[0] if total_rows else {}
    return by_country, total


def _fetch_monthly_fact_rows(
    cur, month: date, country: Optional[str], city: Optional[str], business_slice: Optional[str],
    fleet: Optional[str], subfleet: Optional[str], include_subfleets: bool, limit: int,
) -> list[dict[str, Any]]:
    w: list[str] = ["month = %s"]
    p: list[Any] = [month]
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        p.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        p.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append(
            "business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(business_slice).strip())
    if fleet and str(fleet).strip():
        w.append(
            "fleet_display_name IS NOT NULL AND LOWER(TRIM(fleet_display_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(fleet).strip())
    if subfleet and str(subfleet).strip():
        w.append(
            "subfleet_name IS NOT NULL AND LOWER(TRIM(subfleet_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(subfleet).strip())
    if not include_subfleets:
        w.append("is_subfleet IS NOT TRUE")
    sql = f"""
        SELECT *
        FROM {FACT_MONTHLY}
        WHERE {" AND ".join(w)}
        ORDER BY trips_completed DESC
        LIMIT %s
    """
    p.append(min(max(limit, 1), 10000))
    _ctx = context_from_policy(_SERVING_POLICY, source_name=FACT_MONTHLY)
    return execute_db_gated_query(
        _ctx, _SERVING_POLICY, cur, sql, p,
        source_name=FACT_MONTHLY, source_type="fact",
    )


def _month_fact_row_to_metric_row(r: dict[str, Any]) -> dict[str, Any]:
    """Enriquece con componentes para rollup (recupera total_fare implícito desde ratio canónico)."""
    rev = r.get("revenue_yego_net")
    cp = r.get("commission_pct")
    tf = None
    if rev is not None and cp is not None:
        try:
            cpf = float(cp)
            if cpf > 0:
                tf = float(rev) / cpf
        except (TypeError, ValueError, ZeroDivisionError):
            tf = None
    out = dict(r)
    out["completed_revenue_sum"] = rev
    out["completed_total_fare_sum"] = tf
    return out


def _rollup_metrics_from_month_fact_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = [_month_fact_row_to_metric_row(r) for r in rows]
    return merge_component_rows_for_rollup(enriched)


def get_business_slice_omniview(
    granularity: str,
    period: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    include_subfleets: bool = False,
    daily_window_days: int = 90,
    limit_rows: int = 2000,
    include_previous_only_rows: bool = False,
    use_drill_connection_for_resolved: bool = True,
) -> dict[str, Any]:
    """
    Orquesta lectura current/previous, join por dims, deltas, señales, subtotales y totales.

    include_previous_only_rows: si True, incluye claves solo presentes en previous (current vacío).
    """
    g = validate_omniview_params(granularity, country, daily_window_days)
    anchor = _parse_period_anchor(g, period)
    win = resolve_period_windows(g, anchor)

    mixed_currency = (not country or not str(country).strip()) and g == "monthly"

    conn_ctx = get_db_drill if use_drill_connection_for_resolved else get_db
    with conn_ctx() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if g == "monthly":
                cur_cur = _fetch_monthly_fact_rows(
                    cur, win.current_start, country, city, business_slice,
                    fleet, subfleet, include_subfleets, limit_rows,
                )
                cur_prev = _fetch_monthly_fact_rows(
                    cur, win.previous_start, country, city, business_slice,
                    fleet, subfleet, include_subfleets, limit_rows,
                )
                rc_rollup, rc_total = _fetch_fact_rollup_by_country(
                    cur, FACT_MONTHLY, "month", win.current_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets,
                )
                rp_rollup, rp_total = _fetch_fact_rollup_by_country(
                    cur, FACT_MONTHLY, "month", win.previous_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets,
                )
            elif g == "weekly":
                cur_cur = _fetch_fact_slice_rows(
                    cur, FACT_WEEKLY, "week_start", win.current_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets, limit_rows,
                )
                cur_prev = _fetch_fact_slice_rows(
                    cur, FACT_WEEKLY, "week_start", win.previous_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets, limit_rows,
                )
                rc_rollup, rc_total = _fetch_fact_rollup_by_country(
                    cur, FACT_WEEKLY, "week_start", win.current_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets,
                )
                rp_rollup, rp_total = _fetch_fact_rollup_by_country(
                    cur, FACT_WEEKLY, "week_start", win.previous_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets,
                )
            else:
                cur_cur = _fetch_fact_slice_rows(
                    cur, FACT_DAILY, "trip_date", win.current_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets, limit_rows,
                )
                cur_prev = _fetch_fact_slice_rows(
                    cur, FACT_DAILY, "trip_date", win.previous_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets, limit_rows,
                )
                rc_rollup, rc_total = _fetch_fact_rollup_by_country(
                    cur, FACT_DAILY, "trip_date", win.current_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets,
                )
                rp_rollup, rp_total = _fetch_fact_rollup_by_country(
                    cur, FACT_DAILY, "trip_date", win.previous_start,
                    country, city, business_slice, fleet, subfleet, include_subfleets,
                )
        finally:
            cur.close()

    def norm_month_row(r: dict[str, Any]) -> dict[str, Any]:
        if g != "monthly":
            return r
        m = dict(r)
        m["period_key"] = m.get("month")
        return m

    cur_map = {dim_key(norm_month_row(r)): norm_month_row(r) for r in cur_cur}
    prev_map = {dim_key(norm_month_row(r)): norm_month_row(r) for r in cur_prev}

    keys = set(cur_map.keys())
    if include_previous_only_rows:
        keys |= set(prev_map.keys())
    rows_out: list[dict[str, Any]] = []
    for key in keys:
        raw_c = cur_map.get(key)
        raw_p = prev_map.get(key)
        if raw_c is None and raw_p is None:
            continue
        if raw_c is None and not include_previous_only_rows:
            continue
        dims = {f: (raw_c or raw_p).get(f) for f in DIM_KEY_FIELDS}
        if g == "monthly":
            comp_c = _month_fact_row_to_metric_row(raw_c) if raw_c else {}
            comp_p = _month_fact_row_to_metric_row(raw_p) if raw_p else {}
        else:
            comp_c = raw_c or {}
            comp_p = raw_p or {}
        m_cur = build_metrics_from_components(comp_c)
        m_prev = build_metrics_from_components(comp_p)
        deltas, signals, row_nocomp, row_reason = compute_deltas(m_cur, m_prev)
        rows_out.append(
            {
                "dims": _serialize_dims(dims),
                "current": _json_safe_metrics(m_cur),
                "previous": _json_safe_metrics(m_prev),
                "delta": deltas,
                "signals": {k: {"direction": METRIC_DIRECTIONS[k], "signal": signals[k]} for k in signals},
                "flags": {
                    "not_comparable": row_nocomp,
                    "not_comparable_reason": row_reason,
                    "coverage_unknown": True,
                },
            }
        )

    by_c = {r.get("country"): r for r in rc_rollup}
    by_p = {r.get("country"): r for r in rp_rollup}
    countries = sorted(set(by_c.keys()) | set(by_p.keys()), key=lambda x: (x is None, str(x or "")))
    subtotals: list[dict[str, Any]] = []
    for ctry in countries:
        rc = by_c.get(ctry) or {}
        rp = by_p.get(ctry) or {}
        m_c = build_metrics_from_components(rc)
        m_p = build_metrics_from_components(rp)
        dlt, sig, ncmp, rs = compute_deltas(m_c, m_p)
        subtotals.append(
            {
                "country": ctry,
                "current": _json_safe_metrics(m_c),
                "previous": _json_safe_metrics(m_p),
                "delta": dlt,
                "signals": {k: {"direction": METRIC_DIRECTIONS[k], "signal": sig[k]} for k in sig},
                "flags": {
                    "not_comparable": ncmp,
                    "not_comparable_reason": rs,
                    "coverage_unknown": True,
                },
                "raw_components": {
                    "current": _serialize_components(rc),
                    "previous": _serialize_components(rp),
                },
            }
        )

    tot_c = build_metrics_from_components(rc_total)
    tot_p = build_metrics_from_components(rp_total)
    tot_delta, tot_sig, tot_nocomp, tot_reason = compute_deltas(tot_c, tot_p)

    if g == "monthly":
        detail_source = FACT_MONTHLY
        totals_source = FACT_MONTHLY
    elif g == "weekly":
        detail_source = FACT_WEEKLY
        totals_source = FACT_WEEKLY
    else:
        detail_source = FACT_DAILY
        totals_source = FACT_DAILY

    warnings: list[str] = []
    if mixed_currency:
        warnings.append(
            "mixed_currency: monthly sin country; revenue/ticket pueden mezclar monedas entre países."
        )

    inner_meta: dict[str, Any] = {
        "detail_source": detail_source,
        "totals_source": totals_source,
        "subtotals_source": totals_source,
        "units": OMNIVIEW_UNITS_CONTRACT,
        "coverage_level": "none_at_business_slice_grain",
        "coverage_reference": (
            "Cobertura operativa por ciudad×mes en GET /ops/business-slice/coverage; "
            "no hay métrica de cobertura por tajada unida a cada fila en V1."
        ),
        "daily_window_days": daily_window_days,
        "daily_window_note": (
            "Validado para extensiones futuras; el comparativo diario V1 usa solo el par (día, día-7)."
        ),
    }

    return {
        "granularity": g,
        "comparison_rule": win.comparison_rule,
        "current_period_start": win.current_start.isoformat(),
        "current_period_end_exclusive": win.current_end_exclusive.isoformat(),
        "previous_period_start": win.previous_start.isoformat(),
        "previous_period_end_exclusive": win.previous_end_exclusive.isoformat(),
        "is_current_partial": win.is_current_partial,
        "is_previous_partial": win.is_previous_partial,
        "mixed_currency_warning": mixed_currency,
        "warnings": warnings,
        "meta": inner_meta,
        "rows": rows_out,
        "subtotals": subtotals,
        "totals": {
            "current": _json_safe_metrics(tot_c),
            "previous": _json_safe_metrics(tot_p),
            "delta": tot_delta,
            "signals": {k: {"direction": METRIC_DIRECTIONS[k], "signal": tot_sig[k]} for k in tot_sig},
            "flags": {
                "not_comparable": tot_nocomp,
                "not_comparable_reason": tot_reason,
                "coverage_unknown": True,
            },
        },
    }


def _json_safe_metrics(m: dict[str, Any]) -> dict[str, Any]:
    return {k: _json_safe_scalar(v) for k, v in m.items()}


def _serialize_dims(dims: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in dims.items():
        if hasattr(v, "isoformat") and getattr(v, "day", None):
            out[k] = v.isoformat()[:10]
        else:
            out[k] = _json_safe_scalar(v)
    return out


def _serialize_components(r: dict[str, Any]) -> dict[str, Any]:
    keys = ("completed_revenue_sum", "completed_total_fare_sum")
    return {k: _json_safe_scalar(r.get(k)) for k in keys if k in r}
