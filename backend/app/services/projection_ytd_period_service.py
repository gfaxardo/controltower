"""
YTD y period-over-period (DoD / WoW / MoM) para Omniview Proyección.

FASE 3.5 / 3.5B — aditivo: no mezcla plan/real en tablas; solo extiende respuesta y filas.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.services.seasonality_curve_engine import PROJECTABLE_KPIS


def _peps() -> Any:
    """Evita import circular con projection_expected_progress_service."""
    from app.services import projection_expected_progress_service as m

    return m


def _safe_float(v: Any) -> Optional[float]:
    pe = _peps()
    return pe._safe_float(v)


def _semantic_ui_revenue(v: Any) -> Optional[float]:
    pe = _peps()
    return pe._semantic_ui_revenue(v)


def _ytd_calendar_cutoff(year: int, month: Optional[int], today: date) -> date:
    if month:
        last = date(year, month, monthrange(year, month)[1])
        return min(last, today)
    return min(date(year, 12, 31), today)


def _avg_ticket_ratio(trips: Any, revenue: Any) -> Optional[float]:
    t = _safe_float(trips)
    r = _semantic_ui_revenue(revenue)
    if t is None or r is None or t <= 0:
        return None
    return round(r / t, 4)


def _variation(cur: Optional[float], prev: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if cur is None or prev is None:
        return None, None
    diff = round(cur - prev, 4)
    if prev == 0:
        return diff, None
    return diff, round(((cur - prev) / prev) * 100.0, 2)


def _line_key(r: Dict[str, Any]) -> Tuple:
    return (
        str(r.get("country") or ""),
        str(r.get("city") or ""),
        str(r.get("business_slice_name") or ""),
        bool(r.get("is_subfleet")),
        str(r.get("subfleet_name") or ""),
    )


def _period_sort_tuple(r: Dict[str, Any], grain: str) -> Tuple:
    if grain == "monthly":
        return ("m", str(r.get("month") or ""))
    if grain == "weekly":
        return ("w", str(r.get("week_start") or ""))
    td = r.get("trip_date")
    td_s = td.isoformat()[:10] if hasattr(td, "isoformat") else str(td or "")[:10]
    return ("d", td_s)


def apply_period_over_period_inplace(rows: List[Dict[str, Any]], grain: str) -> None:
    """
    Anexa `period_over_period` a cada fila: variación vs período inmediato anterior
    en la misma línea (mismo país/ciudad/tajada/subfleet).
    """
    kind = {"monthly": "mom", "weekly": "wow", "daily": "dod"}.get(grain, "mom")
    label = {"monthly": "MoM", "weekly": "WoW", "daily": "DoD"}.get(grain, "PoP")

    buckets: Dict[Tuple, List[Tuple[Tuple, Dict[str, Any]]]] = defaultdict(list)
    for r in rows:
        buckets[_line_key(r)].append((_period_sort_tuple(r, grain), r))

    for _lk, lst in buckets.items():
        lst.sort(key=lambda x: x[0])
        for i, (_pk, cur) in enumerate(lst):
            prev_row = lst[i - 1][1] if i > 0 else None
            pop: Dict[str, Any] = {
                "kind": kind,
                "label": label,
                "prev_period": None,
                "comparable": prev_row is not None,
                "metrics": {},
            }
            if not prev_row:
                cur["period_over_period"] = pop
                continue

            if grain == "monthly":
                pop["prev_period"] = prev_row.get("month")
            elif grain == "weekly":
                pop["prev_period"] = prev_row.get("week_start")
            else:
                pd = prev_row.get("trip_date")
                pop["prev_period"] = pd.isoformat()[:10] if hasattr(pd, "isoformat") else str(pd or "")[:10]

            metrics: Dict[str, Any] = {}
            for kpi in PROJECTABLE_KPIS:
                cval = _safe_float(cur.get(kpi))
                pval = _safe_float(prev_row.get(kpi))
                ab, pc = _variation(cval, pval)
                metrics[kpi] = {
                    "abs": ab,
                    "pct": pc,
                    "basis": "real",
                    "cur_real": cval,
                    "prev_real": pval,
                }

            c_at = _avg_ticket_ratio(cur.get("trips_completed"), cur.get("revenue_yego_net"))
            p_at = _avg_ticket_ratio(prev_row.get("trips_completed"), prev_row.get("revenue_yego_net"))
            ab_at, pc_at = _variation(c_at, p_at)
            metrics["avg_ticket"] = {
                "abs": ab_at,
                "pct": pc_at,
                "basis": "derived_ratio",
                "formula": "revenue_yego_net / trips_completed",
                "cur": c_at,
                "prev": p_at,
            }

            pop["metrics"] = metrics
            cur["period_over_period"] = pop


def _acc_stack_ytd_row(
    row: Dict[str, Any],
    sums_real: Dict[str, float],
    sums_exp: Dict[str, float],
    drv_acc: Dict[str, float],
) -> None:
    """Acumula trips/revenue YTD y pesos para promedio ponderado de drivers (peso = trips período)."""
    for kpi in ("trips_completed", "revenue_yego_net"):
        a = _safe_float(row.get(kpi))
        e = _safe_float(row.get(f"{kpi}_projected_expected"))
        if a is not None:
            sums_real[kpi] += float(a)
        if e is not None:
            sums_exp[kpi] += float(e)

    t_r = _safe_float(row.get("trips_completed"))
    d_r = _safe_float(row.get("active_drivers"))
    if t_r is not None and t_r > 0 and d_r is not None:
        drv_acc["real_num"] += float(d_r) * float(t_r)
        drv_acc["real_den"] += float(t_r)

    t_e = _safe_float(row.get("trips_completed_projected_expected"))
    d_e = _safe_float(row.get("active_drivers_projected_expected"))
    if t_e is not None and t_e > 0 and d_e is not None:
        drv_acc["exp_num"] += float(d_e) * float(t_e)
        drv_acc["exp_den"] += float(t_e)


def _pacing_vs_expected(attainment_pct: Optional[float]) -> Optional[str]:
    if attainment_pct is None:
        return None
    if attainment_pct > 103.0:
        return "ahead"
    if attainment_pct < 97.0:
        return "behind"
    return "on_track"


def _classify_ytd_trend(period_snapshots: List[Dict[str, Any]]) -> str:
    """Últimas 3 unidades: pendiente simple sobre attainment_pct agregado cartera."""
    vals = [s.get("attainment_pct") for s in period_snapshots if s.get("attainment_pct") is not None]
    if len(vals) < 2:
        return "flat"
    tail = vals[-3:]
    if len(tail) == 2:
        slope = float(tail[1]) - float(tail[0])
    else:
        slope = (float(tail[2]) - float(tail[0])) / 2.0
    if slope > 1.0:
        return "improving"
    if slope < -1.0:
        return "deteriorating"
    return "flat"


def _gap_decomposition_simple(
    *,
    y_r: float,
    y_e: float,
    gap_t: float,
    avg_d_r: Optional[float],
    avg_d_e: Optional[float],
    avg_ticket_r: Optional[float],
    avg_ticket_e: Optional[float],
) -> Dict[str, Any]:
    """Aproximación ejecutiva: volumen (drivers), productividad (TPD), ticket (revenue)."""
    tpd_e = (y_e / avg_d_e) if avg_d_e and avg_d_e > 0 else None
    tpd_r = (y_r / avg_d_r) if avg_d_r and avg_d_r > 0 else None

    volume_effect = None
    if avg_d_r is not None and avg_d_e is not None and tpd_e is not None:
        volume_effect = round((avg_d_r - avg_d_e) * tpd_e, 2)

    productivity_effect = None
    if tpd_r is not None and tpd_e is not None and avg_d_r is not None:
        productivity_effect = round((tpd_r - tpd_e) * avg_d_r, 2)

    ticket_effect = None
    if avg_ticket_r is not None and avg_ticket_e is not None and y_r:
        ticket_effect = round(float(y_r) * (avg_ticket_r - avg_ticket_e), 2)

    residual = None
    if volume_effect is not None and productivity_effect is not None:
        residual = round(gap_t - volume_effect - productivity_effect, 2)

    return {
        "basis": "approximate_additive_decomposition",
        "volume_effect_drivers": volume_effect,
        "productivity_effect_trips_per_driver": productivity_effect,
        "ticket_effect_revenue": ticket_effect,
        "residual_trips_gap": residual,
        "formula_notes": {
            "volume_effect": "(avg_drivers_real - avg_drivers_expected) * TPD_expected",
            "productivity_effect": "(TPD_real - TPD_expected) * avg_drivers_real",
            "ticket_effect": "ytd_real_trips * (avg_ticket_real - avg_ticket_expected)",
        },
    }


def _finalize_ytd_payload(
    *,
    grain: str,
    year_eff: int,
    through_label: str,
    sums_real: Dict[str, float],
    sums_exp: Dict[str, float],
    drv_acc: Dict[str, float],
    period_snapshots: List[Dict[str, Any]],
) -> Dict[str, Any]:
    y_r = float(sums_real.get("trips_completed", 0.0))
    y_e = float(sums_exp.get("trips_completed", 0.0))
    rev_r = float(sums_real.get("revenue_yego_net", 0.0))
    rev_e = float(sums_exp.get("revenue_yego_net", 0.0))

    att = round((y_r / y_e) * 100.0, 2) if y_e > 0 else None
    gap_t = round(y_r - y_e, 2)
    gap_r = round(rev_r - rev_e, 2)

    avg_real = _avg_ticket_ratio(y_r if y_r else None, rev_r if rev_r else None)
    avg_exp = _avg_ticket_ratio(y_e if y_e else None, rev_e if rev_e else None)

    d_den_r = float(drv_acc.get("real_den", 0.0))
    d_den_e = float(drv_acc.get("exp_den", 0.0))
    ytd_avg_d_r = round(float(drv_acc["real_num"]) / d_den_r, 4) if d_den_r > 0 else None
    ytd_avg_d_e = round(float(drv_acc["exp_num"]) / d_den_e, 4) if d_den_e > 0 else None

    prod_r = round(y_r / ytd_avg_d_r, 4) if ytd_avg_d_r and ytd_avg_d_r > 0 else None
    prod_e = round(y_e / ytd_avg_d_e, 4) if ytd_avg_d_e and ytd_avg_d_e > 0 else None

    pacing = _pacing_vs_expected(att)
    trend = _classify_ytd_trend(period_snapshots)
    gap_dec = _gap_decomposition_simple(
        y_r=y_r,
        y_e=y_e,
        gap_t=gap_t,
        avg_d_r=ytd_avg_d_r,
        avg_d_e=ytd_avg_d_e,
        avg_ticket_r=avg_real,
        avg_ticket_e=avg_exp,
    )

    note_drv = (
        "Drivers YTD: promedio ponderado por trips del período (no suma de distinct). "
        "Útil como indicador operativo; no sustituye conteo distinct anual."
    )

    return {
        "grain": grain,
        "year": year_eff,
        "through_period": through_label,
        "metric_trace": {
            "trips_completed": {
                "real": "sum_period_actual_ytd",
                "expected_plan": "sum_projected_expected_ytd",
            },
            "revenue_yego_net": {
                "real": "sum_period_actual_ytd",
                "expected_plan": "sum_projected_expected_ytd",
            },
            "weekly_expected": {
                "expected_to_date": "closed_iso_weeks_full_plan; open_week uses daily_distribution or linear_day_fraction",
                "row_field": "trips_completed_projected_expected_to_date_week",
            },
            "ytd_avg_active_drivers_real": {
                "basis": "weighted_mean",
                "weight": "trips_completed per period (real)",
            },
            "ytd_avg_active_drivers_expected": {
                "basis": "weighted_mean",
                "weight": "trips_completed_projected_expected per period",
            },
            "driver_productivity_ytd": {"formula": "ytd_real_trips / ytd_avg_active_drivers_real"},
            "pacing_vs_expected": {"basis": "ytd_attainment_pct bands: >103 ahead, 97-103 on_track, <97 behind"},
            "ytd_trend": {"basis": "last_up_to_3 portfolio attainment slopes"},
            "gap_decomposition": gap_dec.get("basis"),
        },
        "ytd_real_trips": round(y_r, 2),
        "ytd_plan_expected_trips": round(y_e, 2),
        "ytd_gap_trips": gap_t,
        "ytd_attainment_pct": att,
        "ytd_real_revenue": round(rev_r, 2) if rev_r or rev_r == 0 else None,
        "ytd_plan_expected_revenue": round(rev_e, 2) if rev_e or rev_e == 0 else None,
        "ytd_gap_revenue": gap_r,
        "ytd_avg_active_drivers_real": ytd_avg_d_r,
        "ytd_avg_active_drivers_expected": ytd_avg_d_e,
        "driver_productivity_ytd_real": prod_r,
        "driver_productivity_ytd_expected": prod_e,
        "ytd_avg_ticket_real": avg_real,
        "ytd_avg_ticket_expected": avg_exp,
        "pacing_vs_expected": pacing,
        "ytd_trend": trend,
        "ytd_trend_periods": [dict(s) for s in period_snapshots[-3:]],
        "gap_decomposition": gap_dec,
        "active_drivers_note": note_drv,
        # Legado explícito (no suma): mantener null para contratos que esperaban estos keys
        "ytd_active_drivers_real": None,
        "ytd_plan_expected_active_drivers": None,
        "ytd_gap_active_drivers": None,
    }


def compute_ytd_summary(
    conn: Any,
    *,
    grain: str,
    rows: List[Dict[str, Any]],
    plan_version: str,
    idx: Any,
    map_rows: List[dict],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
    today: date,
) -> Dict[str, Any]:
    """Agrega YTD (real y plan esperado acumulado) según grano."""
    pe = _peps()
    year_eff = year if year is not None else today.year
    cutoff = _ytd_calendar_cutoff(year_eff, month, today)
    through_label = cutoff.isoformat()

    sums_real: Dict[str, float] = defaultdict(float)
    sums_exp: Dict[str, float] = defaultdict(float)
    drv_acc: Dict[str, float] = {"real_num": 0.0, "real_den": 0.0, "exp_num": 0.0, "exp_den": 0.0}
    period_snapshots: List[Dict[str, Any]] = []

    if grain == "weekly":
        ref_monday = today - timedelta(days=today.weekday())
        by_w: Dict[str, Dict[str, float]] = defaultdict(lambda: {"r": 0.0, "e": 0.0})
        for r in rows:
            ws = r.get("week_start")
            if not ws:
                continue
            wsd = date.fromisoformat(str(ws)[:10])
            if wsd > ref_monday:
                continue
            if int(r.get("iso_year") or 0) != int(year_eff):
                continue
            _acc_stack_ytd_row(r, sums_real, sums_exp, drv_acc)
            by_w[str(ws)[:10]]["r"] += float(_safe_float(r.get("trips_completed")) or 0.0)
            by_w[str(ws)[:10]]["e"] += float(_safe_float(r.get("trips_completed_projected_expected")) or 0.0)
        sorted_weeks = sorted(by_w.keys())
        for wk in sorted_weeks[-3:]:
            t = by_w[wk]
            att_p = round((t["r"] / t["e"]) * 100.0, 2) if t["e"] > 0 else None
            period_snapshots.append({"period": wk, "attainment_pct": att_p, "real_trips": t["r"], "exp_trips": t["e"]})

    elif grain == "daily":
        plan_year_rows = pe._load_plan(plan_version, country, city, year_eff, None)
        plan_by_year = pe._resolve_and_index_plan(plan_year_rows, idx, map_rows)
        end_m = month if month else (today.month if year_eff == today.year else 12)
        daily_agg: Dict[str, Dict[str, float]] = defaultdict(lambda: {"r": 0.0, "e": 0.0})
        for m in range(1, end_m + 1):
            mk = pe._month_key(date(year_eff, m, 1))
            sub_plan = {k: v for k, v in plan_by_year.items() if k[0] == mk}
            dr, dp, _, _ = pe._build_daily(
                conn, sub_plan, today, country, city, business_slice, year_eff, m
            )
            for row in dr + dp:
                td = row.get("trip_date")
                td_s = td.isoformat()[:10] if hasattr(td, "isoformat") else str(td or "")[:10]
                if td_s > cutoff.isoformat():
                    continue
                _acc_stack_ytd_row(row, sums_real, sums_exp, drv_acc)
                daily_agg[td_s]["r"] += float(_safe_float(row.get("trips_completed")) or 0.0)
                daily_agg[td_s]["e"] += float(_safe_float(row.get("trips_completed_projected_expected")) or 0.0)
        sorted_days = sorted(d for d in daily_agg.keys() if d <= cutoff.isoformat())
        for dk in sorted_days[-3:]:
            t = daily_agg[dk]
            att_p = round((t["r"] / t["e"]) * 100.0, 2) if t["e"] > 0 else None
            period_snapshots.append({"period": dk, "attainment_pct": att_p, "real_trips": t["r"], "exp_trips": t["e"]})

    else:  # monthly
        plan_year_rows = pe._load_plan(plan_version, country, city, year_eff, None)
        plan_by_year = pe._resolve_and_index_plan(plan_year_rows, idx, map_rows)
        end_m = month if month else (today.month if year_eff == today.year else 12)
        for m in range(1, end_m + 1):
            mk = pe._month_key(date(year_eff, m, 1))
            sub_plan = {k: v for k, v in plan_by_year.items() if k[0] == mk}
            main, pwr, _ = pe._build_monthly(
                conn, sub_plan, today, country, city, business_slice, year_eff, m
            )
            comb = main + pwr
            tr = sum(float(_safe_float(x.get("trips_completed")) or 0.0) for x in comb)
            te = sum(float(_safe_float(x.get("trips_completed_projected_expected")) or 0.0) for x in comb)
            att_p = round((tr / te) * 100.0, 2) if te > 0 else None
            period_snapshots.append(
                {
                    "period": f"{year_eff}-{m:02d}",
                    "attainment_pct": att_p,
                    "real_trips": tr,
                    "exp_trips": te,
                }
            )
            for row in comb:
                _acc_stack_ytd_row(row, sums_real, sums_exp, drv_acc)
        period_snapshots = period_snapshots[-3:]

    return _finalize_ytd_payload(
        grain=grain,
        year_eff=year_eff,
        through_label=through_label,
        sums_real=dict(sums_real),
        sums_exp=dict(sums_exp),
        drv_acc=drv_acc,
        period_snapshots=period_snapshots,
    )


def attach_projection_ytd_and_pop(
    conn: Any,
    *,
    grain: str,
    rows: List[Dict[str, Any]],
    plan_version: str,
    idx: Any,
    map_rows: List[dict],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
    today: date,
) -> Dict[str, Any]:
    apply_period_over_period_inplace(rows, grain)
    return compute_ytd_summary(
        conn,
        grain=grain,
        rows=rows,
        plan_version=plan_version,
        idx=idx,
        map_rows=map_rows,
        country=country,
        city=city,
        business_slice=business_slice,
        year=year,
        month=month,
        today=today,
    )


def meta_period_over_period_kind(grain: str) -> str:
    return {"monthly": "mom", "weekly": "wow", "daily": "dod"}.get(grain, "mom")
