"""
FASE_KPI_CONSISTENCY — Validador automático de consistencia KPI por grano.

Corrección v2 (FASE_VALIDATION_FIX):
  La versión anterior sumaba semanas ISO completas (weekly_sum_full_iso),
  lo que producía falsos FAIL cuando una semana cruzaba dos meses
  (la suma incluía días del mes anterior o siguiente).

  Regla canónica correcta para KPIs aditivos:
    monthly_value ≈ SUM(daily_value dentro del mes calendario)  [OBLIGATORIO]
    monthly_value ≈ weekly_sum_intersection (ponderado por días en mes)  [OPCIONAL]

  El campo weekly_sum_full_iso se mantiene como referencia informativa
  pero NO se usa como criterio de FAIL para KPIs aditivos.

Para cada KPI visible en Omniview y para cada combinación
(country, city, business_slice, month) compara:

  - monthly_value      = ops.real_business_slice_month_fact
  - daily_sum_in_month = SUM(day_fact) dentro del mes calendario  ← BASE CANÓNICA
  - weekly_sum_full_iso= SUM(week_fact) semanas ISO completas que tocan el mes (informativo)
  - weekly_sum_intersect= SUM(week_fact ponderado por días dentro del mes)  (opcional)

Status por celda:
  ok | expected_non_comparable | warning | fail

Uso:
  python -m scripts.validate_kpi_grain_consistency \\
        --year 2026 --month 4

Salida:
  backend/scripts/outputs/kpi_grain_consistency_<timestamp>.csv
"""
from __future__ import annotations

import argparse
import calendar
import csv
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config.kpi_aggregation_rules import (  # noqa: E402
    AGG_ADDITIVE,
    AGG_DERIVED_RATIO,
    AGG_NON_ADDITIVE_RATIO,
    AGG_SEMI_ADDITIVE,
    OMNIVIEW_MATRIX_VISIBLE_KPIS,
    get_omniview_kpi_rule,
)
from app.db.connection import get_db  # noqa: E402


# ────────────────────────────────────────────────────────────────────────
# Tolerancias
# ────────────────────────────────────────────────────────────────────────
ADDITIVE_REL_EPS = 0.01     # 1% relativo
ADDITIVE_ABS_EPS = 1.0      # 1 unidad (trips) o eps moneda
RATIO_REL_EPS    = 0.02     # 2% al recomputar


# ────────────────────────────────────────────────────────────────────────
# Helpers numéricos
# ────────────────────────────────────────────────────────────────────────

def _f(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(x) or math.isinf(x):
        return 0.0
    return x


def _within(a: float, b: float, rel: float, absol: float) -> bool:
    diff = abs(a - b)
    if diff <= absol:
        return True
    base = max(abs(a), abs(b))
    if base == 0.0:
        return diff == 0.0
    return diff / base <= rel


# ────────────────────────────────────────────────────────────────────────
# Cálculo de intersección de semanas ISO con el mes calendario
# ────────────────────────────────────────────────────────────────────────

def _iso_weeks_for_month(year: int, month: int) -> List[Tuple[date, date, float]]:
    """
    Devuelve las semanas ISO (lunes..domingo) que se superponen con el mes
    (year, month), junto con la fracción de días de esa semana que caen
    dentro del mes calendario.

    Returns:
        List de (week_start, week_end, fraction_in_month)
        donde fraction_in_month ∈ (0, 1].
    """
    last_day = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)

    # El lunes de la semana que contiene el primer día del mes
    first_week_start = month_start - timedelta(days=month_start.weekday())

    weeks: List[Tuple[date, date, float]] = []
    ws = first_week_start
    while ws <= month_end:
        we = ws + timedelta(days=6)
        # días de esta semana que caen dentro del mes
        overlap_start = max(ws, month_start)
        overlap_end = min(we, month_end)
        days_in_month = (overlap_end - overlap_start).days + 1
        fraction = days_in_month / 7.0
        weeks.append((ws, we, fraction))
        ws += timedelta(weeks=1)

    return weeks


# ────────────────────────────────────────────────────────────────────────
# Carga de datos
# ────────────────────────────────────────────────────────────────────────

def _build_filter(country: Optional[str], city: Optional[str]) -> Tuple[str, List[Any]]:
    where = []
    params: List[Any] = []
    if country:
        where.append("country IS NOT DISTINCT FROM %s")
        params.append(country)
    if city:
        where.append("city IS NOT DISTINCT FROM %s")
        params.append(city)
    sql = (" AND " + " AND ".join(where)) if where else ""
    return sql, params


def _month_bounds(year: int, month: int) -> Tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _load_month_facts(
    year: int, month: int, country: Optional[str], city: Optional[str]
) -> Dict[Tuple, Dict[str, Any]]:
    extra_where, extra_params = _build_filter(country, city)
    sql = f"""
        SELECT country, city, business_slice_name,
               trips_completed, trips_cancelled, active_drivers,
               avg_ticket, commission_pct, trips_per_driver,
               revenue_yego_net,
               NULL::numeric AS cancel_rate_pct,
               ticket_sum_completed, ticket_count_completed,
               total_fare_completed_positive_sum
        FROM ops.real_business_slice_month_fact
        WHERE month = %s::date {extra_where}
    """
    params = [date(year, month, 1)] + extra_params
    out: Dict[Tuple, Dict[str, Any]] = {}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            key = (d.get("country"), d.get("city"), d.get("business_slice_name"))
            out[key] = d
        cur.close()
    return out


def _load_week_facts_full_iso(
    year: int, month: int, country: Optional[str], city: Optional[str]
) -> Dict[Tuple, Dict[str, Any]]:
    """
    Suma semanal FULL ISO (informativa, NO base de fail).
    Incluye días de meses adyacentes cuando la semana cruza el límite mensual.
    Se almacena en el CSV como 'weekly_sum_full_iso' para trazabilidad.
    """
    extra_where, extra_params = _build_filter(country, city)
    start, end = _month_bounds(year, month)
    sql = f"""
        SELECT country, city, business_slice_name,
               COUNT(*) AS n_weeks,
               SUM(trips_completed)           AS sum_trips_completed,
               MAX(trips_completed)           AS max_trips_completed,
               SUM(trips_cancelled)           AS sum_trips_cancelled,
               SUM(active_drivers)            AS sum_active_drivers,
               MAX(active_drivers)            AS max_active_drivers,
               MIN(active_drivers)            AS min_active_drivers,
               SUM(revenue_yego_net)          AS sum_revenue_yego_net,
               SUM(ticket_sum_completed)      AS sum_ticket_sum_completed,
               SUM(ticket_count_completed)    AS sum_ticket_count_completed,
               SUM(total_fare_completed_positive_sum) AS sum_total_fare_pos
        FROM ops.real_business_slice_week_fact
        WHERE week_start >= (date_trunc('week', %s::date))::date
          AND week_start <= %s::date
          {extra_where}
        GROUP BY country, city, business_slice_name
    """
    params = [start, end] + extra_params
    out: Dict[Tuple, Dict[str, Any]] = {}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            key = (d.get("country"), d.get("city"), d.get("business_slice_name"))
            out[key] = d
        cur.close()
    return out


def _load_week_facts_intersection(
    year: int, month: int, country: Optional[str], city: Optional[str]
) -> Dict[Tuple, Dict[str, Any]]:
    """
    Suma semanal ponderada por fracción de días que caen dentro del mes calendario.

    Para cada semana ISO que toca el mes, pondera los valores por la fracción
    de sus días que pertenecen al mes (fraction = dias_en_mes / 7).

    Esta es la métrica correcta para comparar semanas contra el mensual.
    Si la semana está completamente dentro del mes, fraction = 1.0.
    Si cruza el límite, fraction < 1.0.
    """
    extra_where, extra_params = _build_filter(country, city)
    weeks = _iso_weeks_for_month(year, month)

    if not weeks:
        return {}

    # Cargar cada semana individualmente y ponderar
    aggregated: Dict[Tuple, Dict[str, Any]] = {}
    with get_db() as conn:
        cur = conn.cursor()
        for ws, _we, fraction in weeks:
            sql = f"""
                SELECT country, city, business_slice_name,
                       trips_completed    * %s::float AS trips_completed_w,
                       trips_cancelled    * %s::float AS trips_cancelled_w,
                       active_drivers                 AS active_drivers_raw,
                       revenue_yego_net   * %s::float AS revenue_yego_net_w,
                       ticket_sum_completed   * %s::float AS ticket_sum_w,
                       ticket_count_completed * %s::float AS ticket_count_w,
                       total_fare_completed_positive_sum * %s::float AS total_fare_w
                FROM ops.real_business_slice_week_fact
                WHERE week_start = %s::date {extra_where}
            """
            params = [fraction, fraction, fraction, fraction, fraction, fraction, ws] + extra_params
            cur.execute(sql, params)
            cols2 = [c[0] for c in cur.description]
            for row in cur.fetchall():
                d = dict(zip(cols2, row))
                key = (d.get("country"), d.get("city"), d.get("business_slice_name"))
                if key not in aggregated:
                    aggregated[key] = {
                        "intersect_trips_completed": 0.0,
                        "intersect_trips_cancelled": 0.0,
                        "intersect_active_drivers_max": 0.0,
                        "intersect_revenue_yego_net": 0.0,
                        "intersect_ticket_sum": 0.0,
                        "intersect_ticket_count": 0.0,
                        "intersect_total_fare": 0.0,
                        "n_weeks_intersect": 0,
                    }
                a = aggregated[key]
                a["intersect_trips_completed"] += _f(d.get("trips_completed_w"))
                a["intersect_trips_cancelled"] += _f(d.get("trips_cancelled_w"))
                a["intersect_active_drivers_max"] = max(
                    a["intersect_active_drivers_max"], _f(d.get("active_drivers_raw"))
                )
                a["intersect_revenue_yego_net"] += _f(d.get("revenue_yego_net_w"))
                a["intersect_ticket_sum"] += _f(d.get("ticket_sum_w"))
                a["intersect_ticket_count"] += _f(d.get("ticket_count_w"))
                a["intersect_total_fare"] += _f(d.get("total_fare_w"))
                a["n_weeks_intersect"] += 1
        cur.close()
    return aggregated


def _load_day_facts(
    year: int, month: int, country: Optional[str], city: Optional[str]
) -> Dict[Tuple, Dict[str, Any]]:
    """Suma de day_fact dentro del mes calendario exacto. BASE CANÓNICA."""
    extra_where, extra_params = _build_filter(country, city)
    start, end = _month_bounds(year, month)
    sql = f"""
        SELECT country, city, business_slice_name,
               COUNT(*) AS n_days,
               SUM(trips_completed)           AS sum_trips_completed,
               MAX(trips_completed)           AS max_trips_completed,
               SUM(trips_cancelled)           AS sum_trips_cancelled,
               SUM(active_drivers)            AS sum_active_drivers,
               MAX(active_drivers)            AS max_active_drivers,
               MIN(active_drivers)            AS min_active_drivers,
               SUM(revenue_yego_net)          AS sum_revenue_yego_net,
               SUM(ticket_sum_completed)      AS sum_ticket_sum_completed,
               SUM(ticket_count_completed)    AS sum_ticket_count_completed,
               SUM(total_fare_completed_positive_sum) AS sum_total_fare_pos
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= %s::date
          AND trip_date <= %s::date
          {extra_where}
        GROUP BY country, city, business_slice_name
    """
    params = [start, end] + extra_params
    out: Dict[Tuple, Dict[str, Any]] = {}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            key = (d.get("country"), d.get("city"), d.get("business_slice_name"))
            out[key] = d
        cur.close()
    return out


# ────────────────────────────────────────────────────────────────────────
# Reglas por aggregation_type
# ────────────────────────────────────────────────────────────────────────

def _eval_additive(
    monthly: float,
    daily_sum_in_month: float,
    weekly_sum_full_iso: float,
    weekly_sum_intersect: float,
) -> Tuple[str, str]:
    """
    REGLA CANÓNICA (v2): base de comparación = daily_sum_in_month.
    weekly_sum_full_iso es solo informativa (no genera FAIL).
    weekly_sum_intersect es secundaria (genera warning, no fail).
    """
    # Base canónica: daily_sum_in_month
    daily_ok = _within(monthly, daily_sum_in_month, ADDITIVE_REL_EPS, ADDITIVE_ABS_EPS)

    if not daily_ok:
        return (
            "fail",
            f"SUM(daily_in_month)={daily_sum_in_month:g} vs monthly={monthly:g} "
            f"[weekly_full_iso={weekly_sum_full_iso:g} es solo informativo]",
        )

    # Verificación complementaria: weekly_intersect (si disponible)
    if weekly_sum_intersect > 0:
        intersect_ok = _within(monthly, weekly_sum_intersect, ADDITIVE_REL_EPS * 2, ADDITIVE_ABS_EPS * 2)
        if not intersect_ok:
            return (
                "warning",
                f"SUM(daily_in_month)={daily_sum_in_month:g} OK; "
                f"weekly_intersect={weekly_sum_intersect:g} vs monthly={monthly:g} "
                f"(tolerancia 2x, puede deberse a parciales de semana)",
            )

    return "ok", ""


def _eval_semi_additive(
    monthly: float,
    weekly_sum_full: float,
    weekly_max: float,
    daily_sum: float,
    daily_max: float,
) -> Tuple[str, str]:
    """
    active_drivers: distinct count. No se suma; se validan rangos razonables.
    No usa weekly_sum como criterio de fail (por la misma razón ISO: sumará drivers de
    días de meses adyacentes). Comparación solo por max(weekly|daily).
    """
    if monthly == 0.0 and weekly_sum_full == 0.0 and daily_sum == 0.0:
        return "expected_non_comparable", "Sin actividad en el periodo."

    issues: List[str] = []
    # monthly < max(daily) es sospechoso: el mensual (scope mes) debe >= máx diario
    if daily_max and monthly < daily_max - ADDITIVE_ABS_EPS:
        issues.append(f"monthly({monthly:g}) < max(daily)={daily_max:g}")
    # No comparamos contra max(weekly_full) porque puede incluir días fuera del mes
    # Si queremos la consistencia de semi_additive, usamos solo daily_max

    if not issues:
        return (
            "expected_non_comparable",
            "Distinct count: monthly NO equivale a SUM(weekly|daily); rango vs daily_max verificado.",
        )
    return "fail", "; ".join(issues)


def _eval_non_additive_ratio(
    kpi: str,
    monthly_row: Dict[str, Any],
    week_row: Dict[str, Any],
    day_row: Dict[str, Any],
) -> Tuple[str, str]:
    """Recomputar la fórmula desde componentes y comparar contra monthly."""
    monthly_val = _f(monthly_row.get(kpi))
    issues: List[str] = []

    if kpi == "avg_ticket":
        m_ts = _f(monthly_row.get("ticket_sum_completed"))
        m_tc = _f(monthly_row.get("ticket_count_completed"))
        recomputed = (m_ts / m_tc) if m_tc > 0 else None
        if recomputed is not None and not _within(monthly_val, recomputed, RATIO_REL_EPS, 0.01):
            issues.append(f"monthly stored={monthly_val:g} vs recomputed={recomputed:g}")
    elif kpi == "commission_pct":
        m_rev = _f(monthly_row.get("revenue_yego_net"))
        m_fare = _f(monthly_row.get("total_fare_completed_positive_sum"))
        recomputed = (m_rev / m_fare) if m_fare > 0 else None
        if recomputed is not None and not _within(monthly_val, recomputed, RATIO_REL_EPS, 0.001):
            issues.append(f"monthly stored={monthly_val:g} vs recomputed={recomputed:g}")
    elif kpi == "cancel_rate_pct":
        m_canc = _f(monthly_row.get("trips_cancelled"))
        m_comp = _f(monthly_row.get("trips_completed"))
        denom = m_canc + m_comp
        recomputed = (m_canc / denom) if denom > 0 else None
        if recomputed is not None and monthly_val > 0 and not _within(monthly_val, recomputed, RATIO_REL_EPS, 0.001):
            issues.append(f"monthly stored={monthly_val:g} vs recomputed={recomputed:g}")

    if issues:
        return "fail", "; ".join(issues)
    return "expected_non_comparable", "Ratio: misma fórmula a distinto scope; consistencia interna OK."


def _eval_derived_ratio(
    monthly_row: Dict[str, Any],
    week_row: Dict[str, Any],
    day_row: Dict[str, Any],
) -> Tuple[str, str]:
    """trips_per_driver: validar fórmula por scope, no por suma."""
    monthly_val = _f(monthly_row.get("trips_per_driver"))
    m_t = _f(monthly_row.get("trips_completed"))
    m_d = _f(monthly_row.get("active_drivers"))
    recomputed = (m_t / m_d) if m_d > 0 else None
    if recomputed is None:
        return "expected_non_comparable", "Sin drivers activos en el mes."
    if not _within(monthly_val, recomputed, RATIO_REL_EPS, 0.01):
        return "fail", f"monthly stored={monthly_val:g} vs recomputed(trips/drivers)={recomputed:g}"
    return (
        "expected_non_comparable",
        "Derivado de drivers únicos: validado por fórmula scope-by-scope, no por suma.",
    )


# ────────────────────────────────────────────────────────────────────────
# Construcción de filas CSV
# ────────────────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "country", "city", "business_slice", "kpi", "month",
    "monthly_value",
    "daily_sum_in_month",      # base canónica (obligatoria)
    "weekly_sum_full_iso",     # solo informativo — NO criterio de fail
    "weekly_sum_intersect",    # ponderado por días en el mes (opcional, complementario)
    "weekly_max", "daily_max",
    "expected_rule", "comparable_across_grains",
    "validation_basis",        # "daily_in_month" o "formula_internal"
    "status", "issue_note",
]


def _evaluate_cell(
    kpi: str,
    monthly_row: Dict[str, Any],
    week_row_full: Dict[str, Any],
    week_row_intersect: Dict[str, Any],
    day_row: Dict[str, Any],
) -> Dict[str, Any]:
    rule = get_omniview_kpi_rule(kpi)
    agg = rule.get("aggregation_type")
    comparable = bool(rule.get("comparable_across_grains"))
    comparison_rule = rule.get("comparison_rule")

    monthly_val = _f(monthly_row.get(kpi))

    # Suma daily dentro del mes (BASE CANÓNICA)
    daily_sum_col = f"sum_{kpi}" if f"sum_{kpi}" in day_row else None
    daily_sum_in_month = _f(day_row.get(daily_sum_col)) if daily_sum_col else 0.0

    # Suma semanal full ISO (solo informativa)
    week_sum_full_col = f"sum_{kpi}" if f"sum_{kpi}" in week_row_full else None
    weekly_sum_full_iso = _f(week_row_full.get(week_sum_full_col)) if week_sum_full_col else 0.0

    # Suma semanal ponderada por intersección (complementaria)
    _intersect_map = {
        "trips_completed": "intersect_trips_completed",
        "trips_cancelled": "intersect_trips_cancelled",
        "revenue_yego_net": "intersect_revenue_yego_net",
        "active_drivers": "intersect_active_drivers_max",  # no se suma para semi-additive
    }
    intersect_col = _intersect_map.get(kpi)
    weekly_sum_intersect = _f(week_row_intersect.get(intersect_col)) if intersect_col else 0.0

    weekly_max_col = f"max_{kpi}" if f"max_{kpi}" in week_row_full else None
    daily_max_col = f"max_{kpi}" if f"max_{kpi}" in day_row else None
    weekly_max = _f(week_row_full.get(weekly_max_col)) if weekly_max_col else 0.0
    daily_max = _f(day_row.get(daily_max_col)) if daily_max_col else 0.0

    if agg == AGG_ADDITIVE:
        status, note = _eval_additive(
            monthly_val, daily_sum_in_month, weekly_sum_full_iso, weekly_sum_intersect
        )
        validation_basis = "daily_in_month"
    elif agg == AGG_SEMI_ADDITIVE:
        status, note = _eval_semi_additive(
            monthly_val, weekly_sum_full_iso, weekly_max, daily_sum_in_month, daily_max
        )
        validation_basis = "daily_in_month+max_scope"
    elif agg == AGG_NON_ADDITIVE_RATIO:
        status, note = _eval_non_additive_ratio(kpi, monthly_row, week_row_full, day_row)
        validation_basis = "formula_internal"
    elif agg == AGG_DERIVED_RATIO:
        status, note = _eval_derived_ratio(monthly_row, week_row_full, day_row)
        validation_basis = "formula_internal"
    else:
        status, note = "warning", f"aggregation_type desconocido: {agg}"
        validation_basis = "unknown"

    return {
        "monthly_value": monthly_val,
        "daily_sum_in_month": daily_sum_in_month,
        "weekly_sum_full_iso": weekly_sum_full_iso,
        "weekly_sum_intersect": weekly_sum_intersect,
        "weekly_max": weekly_max,
        "daily_max": daily_max,
        "expected_rule": comparison_rule,
        "comparable_across_grains": comparable,
        "validation_basis": validation_basis,
        "status": status,
        "issue_note": note,
    }


# ────────────────────────────────────────────────────────────────────────
# Orquestación
# ────────────────────────────────────────────────────────────────────────

def run_consistency_audit(
    year: int,
    month: int,
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    print(
        f"[kpi-consistency-v2] year={year} month={month} "
        f"country={country or '*'} city={city or '*'}",
        flush=True,
    )
    print(
        "[kpi-consistency-v2] base canónica: daily_sum_in_month "
        "(weekly_sum_full_iso solo informativo)",
        flush=True,
    )

    monthly = _load_month_facts(year, month, country, city)
    weekly_full = _load_week_facts_full_iso(year, month, country, city)
    weekly_intersect = _load_week_facts_intersection(year, month, country, city)
    daily = _load_day_facts(year, month, country, city)

    keys = set(monthly.keys()) | set(weekly_full.keys()) | set(daily.keys())
    print(
        f"[kpi-consistency-v2] cells: monthly={len(monthly)} "
        f"weekly_full={len(weekly_full)} weekly_intersect={len(weekly_intersect)} "
        f"daily={len(daily)} merged={len(keys)}",
        flush=True,
    )

    rows: List[Dict[str, Any]] = []
    month_iso = date(year, month, 1).isoformat()
    for k in sorted(keys, key=lambda x: tuple("" if v is None else str(v) for v in x)):
        co, ci, bs = k
        m_row = monthly.get(k, {})
        wf_row = weekly_full.get(k, {})
        wi_row = weekly_intersect.get(k, {})
        d_row = daily.get(k, {})
        for kpi in OMNIVIEW_MATRIX_VISIBLE_KPIS:
            ev = _evaluate_cell(kpi, m_row, wf_row, wi_row, d_row)
            rows.append({
                "country": co or "",
                "city": ci or "",
                "business_slice": bs or "",
                "kpi": kpi,
                "month": month_iso,
                **ev,
            })
    return rows


def write_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_COLUMNS})


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {"ok": 0, "expected_non_comparable": 0, "warning": 0, "fail": 0}
    for r in rows:
        s = r.get("status") or ""
        counts[s] = counts.get(s, 0) + 1
    return counts


def main() -> int:
    p = argparse.ArgumentParser(description="FASE_KPI_CONSISTENCY validator v2 (fix ISO weeks)")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--country", type=str, default=None)
    p.add_argument("--city", type=str, default=None)
    p.add_argument("--out", type=str, default=None)
    args = p.parse_args()

    rows = run_consistency_audit(args.year, args.month, args.country, args.city)
    counts = summarize(rows)

    print("[kpi-consistency-v2] resumen status:")
    for k in ("ok", "expected_non_comparable", "warning", "fail"):
        print(f"  {k}: {counts.get(k, 0)}")

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_path = Path(args.out) if args.out else (
        _HERE / "outputs" / f"kpi_grain_consistency_v2_{ts}.csv"
    )
    write_csv(rows, out_path)
    print(f"[kpi-consistency-v2] CSV: {out_path}")

    if counts.get("fail", 0) > 0:
        return 2
    if counts.get("warning", 0) > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
