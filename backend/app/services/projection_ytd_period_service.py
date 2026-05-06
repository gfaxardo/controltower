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


def _slice_key_from_line_key(lk: Tuple) -> str:
    co, ci, bsn, is_sf, sub = lk
    return f"{co}::{ci}::{bsn}::{1 if is_sf else 0}::{sub}"


def _slice_level_from_line_key(lk: Tuple) -> str:
    return "subfleet" if lk[3] else "lob"


def _empty_ytd_slice_payload(grain: str, lk: Tuple, *, trace_note: str) -> Dict[str, Any]:
    """Fila/slice sin acumulación suficiente; objeto siempre presente (FASE 3.8)."""
    return {
        "grain": grain,
        "slice_key": _slice_key_from_line_key(lk),
        "slice_level": _slice_level_from_line_key(lk),
        "ytd_real_trips": None,
        "ytd_plan_expected_trips": None,
        "ytd_gap_trips": None,
        "ytd_attainment_pct": None,
        "pacing_vs_expected": None,
        "ytd_trend": None,
        "ytd_real_revenue": None,
        "ytd_plan_expected_revenue": None,
        "ytd_gap_revenue": None,
        "ytd_avg_active_drivers_real": None,
        "ytd_avg_active_drivers_expected": None,
        "driver_productivity_ytd_real": None,
        "driver_productivity_ytd_expected": None,
        "metric_trace": {
            "insufficient_data": trace_note,
            "expected_plan_basis": "same_as_global_ytd_summary",
            "slice_key_rule": "country::city::business_slice_name::is_subfleet_flag::subfleet_name",
        },
    }


def _finalize_ytd_slice_only(
    *,
    grain: str,
    lk: Tuple,
    year_eff: int,
    through_label: str,
    sums_real: Dict[str, float],
    sums_exp: Dict[str, float],
    drv_acc: Dict[str, float],
    period_snapshots: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Misma lógica numérica que meta.ytd_summary pero anexada por slice (sin gap_decomposition)."""
    full = _finalize_ytd_payload(
        grain=grain,
        year_eff=year_eff,
        through_label=through_label,
        sums_real=dict(sums_real),
        sums_exp=dict(sums_exp),
        drv_acc=drv_acc,
        period_snapshots=period_snapshots,
    )
    mt: Dict[str, Any] = dict(full.get("metric_trace") or {})
    mt["slice_key_rule"] = "country::city::business_slice_name::is_subfleet_flag::subfleet_name"
    mt["slice_coordinate"] = {
        "country": lk[0],
        "city": lk[1],
        "business_slice_name": lk[2],
        "is_subfleet": lk[3],
        "subfleet_name": lk[4],
    }
    mt.pop("gap_decomposition", None)
    return {
        "grain": grain,
        "slice_key": _slice_key_from_line_key(lk),
        "slice_level": _slice_level_from_line_key(lk),
        "ytd_real_trips": full.get("ytd_real_trips"),
        "ytd_plan_expected_trips": full.get("ytd_plan_expected_trips"),
        "ytd_gap_trips": full.get("ytd_gap_trips"),
        "ytd_attainment_pct": full.get("ytd_attainment_pct"),
        "pacing_vs_expected": full.get("pacing_vs_expected"),
        "ytd_trend": full.get("ytd_trend"),
        "ytd_real_revenue": full.get("ytd_real_revenue"),
        "ytd_plan_expected_revenue": full.get("ytd_plan_expected_revenue"),
        "ytd_gap_revenue": full.get("ytd_gap_revenue"),
        "ytd_avg_active_drivers_real": full.get("ytd_avg_active_drivers_real"),
        "ytd_avg_active_drivers_expected": full.get("ytd_avg_active_drivers_expected"),
        "driver_productivity_ytd_real": full.get("driver_productivity_ytd_real"),
        "driver_productivity_ytd_expected": full.get("driver_productivity_ytd_expected"),
        "metric_trace": mt,
    }


def compute_ytd_slice_by_line_key(
    conn: Any,
    *,
    grain: str,
    display_rows: List[Dict[str, Any]],
    plan_version: str,
    idx: Any,
    map_rows: List[dict],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
    today: date,
) -> Dict[Tuple, Dict[str, Any]]:
    """
    YTD por slice operativo (misma lógica de expected que compute_ytd_summary / granularidad).
    Clave alineada con period_over_period y matriz (country, city, bsn, subfleet).
    """
    pe = _peps()
    year_eff = year if year is not None else today.year
    cutoff = _ytd_calendar_cutoff(year_eff, month, today)
    through_label = cutoff.isoformat()
    keys_from_display = {_line_key(r) for r in display_rows}

    def _acc_box() -> Dict[str, Any]:
        return {
            "sums_real": defaultdict(float),
            "sums_exp": defaultdict(float),
            "drv_acc": {"real_num": 0.0, "real_den": 0.0, "exp_num": 0.0, "exp_den": 0.0},
        }

    result: Dict[Tuple, Dict[str, Any]] = {}

    if grain == "weekly":
        ref_monday = today - timedelta(days=today.weekday())
        acc: Dict[Tuple, Dict[str, Any]] = defaultdict(_acc_box)
        by_w: Dict[Tuple, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: {"r": 0.0, "e": 0.0})
        )

        for r in display_rows:
            ws = r.get("week_start")
            if not ws:
                continue
            wsd = date.fromisoformat(str(ws)[:10])
            if wsd > ref_monday:
                continue
            if int(r.get("iso_year") or 0) != int(year_eff):
                continue
            lk = _line_key(r)
            box = acc[lk]
            _acc_stack_ytd_row(r, box["sums_real"], box["sums_exp"], box["drv_acc"])
            wks = str(ws)[:10]
            by_w[lk][wks]["r"] += float(_safe_float(r.get("trips_completed")) or 0.0)
            by_w[lk][wks]["e"] += float(_safe_float(r.get("trips_completed_projected_expected")) or 0.0)

        for lk, box in acc.items():
            period_snapshots: List[Dict[str, Any]] = []
            sorted_weeks = sorted(by_w[lk].keys())
            for wk in sorted_weeks[-3:]:
                t = by_w[lk][wk]
                att_p = round((t["r"] / t["e"]) * 100.0, 2) if t["e"] > 0 else None
                period_snapshots.append(
                    {"period": wk, "attainment_pct": att_p, "real_trips": t["r"], "exp_trips": t["e"]}
                )
            result[lk] = _finalize_ytd_slice_only(
                grain=grain,
                lk=lk,
                year_eff=year_eff,
                through_label=through_label,
                sums_real=box["sums_real"],
                sums_exp=box["sums_exp"],
                drv_acc=box["drv_acc"],
                period_snapshots=period_snapshots,
            )

    elif grain == "daily":
        plan_year_rows = pe._load_plan(plan_version, country, city, year_eff, None)
        plan_by_year = pe._resolve_and_index_plan(plan_year_rows, idx, map_rows)
        end_m = month if month else (today.month if year_eff == today.year else 12)

        acc = defaultdict(_acc_box)
        daily_agg: Dict[Tuple, Dict[str, Dict[str, float]]] = defaultdict(
            lambda: defaultdict(lambda: {"r": 0.0, "e": 0.0})
        )

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
                lk = _line_key(row)
                box = acc[lk]
                _acc_stack_ytd_row(row, box["sums_real"], box["sums_exp"], box["drv_acc"])
                daily_agg[lk][td_s]["r"] += float(_safe_float(row.get("trips_completed")) or 0.0)
                daily_agg[lk][td_s]["e"] += float(
                    _safe_float(row.get("trips_completed_projected_expected")) or 0.0
                )

        for lk, box in acc.items():
            sorted_days = sorted(d for d in daily_agg[lk].keys() if d <= cutoff.isoformat())
            period_snapshots = []
            for dk in sorted_days[-3:]:
                t = daily_agg[lk][dk]
                att_p = round((t["r"] / t["e"]) * 100.0, 2) if t["e"] > 0 else None
                period_snapshots.append(
                    {"period": dk, "attainment_pct": att_p, "real_trips": t["r"], "exp_trips": t["e"]}
                )
            result[lk] = _finalize_ytd_slice_only(
                grain=grain,
                lk=lk,
                year_eff=year_eff,
                through_label=through_label,
                sums_real=box["sums_real"],
                sums_exp=box["sums_exp"],
                drv_acc=box["drv_acc"],
                period_snapshots=period_snapshots,
            )

    else:  # monthly
        plan_year_rows = pe._load_plan(plan_version, country, city, year_eff, None)
        plan_by_year = pe._resolve_and_index_plan(plan_year_rows, idx, map_rows)
        end_m = month if month else (today.month if year_eff == today.year else 12)

        acc = defaultdict(_acc_box)
        month_snap: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)

        for m in range(1, end_m + 1):
            mk = pe._month_key(date(year_eff, m, 1))
            sub_plan = {k: v for k, v in plan_by_year.items() if k[0] == mk}
            main, pwr, _ = pe._build_monthly(
                conn, sub_plan, today, country, city, business_slice, year_eff, m
            )
            comb = main + pwr
            by_m: Dict[Tuple, Dict[str, float]] = defaultdict(lambda: {"tr": 0.0, "te": 0.0})

            for row in comb:
                lk = _line_key(row)
                by_m[lk]["tr"] += float(_safe_float(row.get("trips_completed")) or 0.0)
                by_m[lk]["te"] += float(
                    _safe_float(row.get("trips_completed_projected_expected")) or 0.0
                )
                box = acc[lk]
                _acc_stack_ytd_row(row, box["sums_real"], box["sums_exp"], box["drv_acc"])

            for lk, t in by_m.items():
                att_p = round((t["tr"] / t["te"]) * 100.0, 2) if t["te"] > 0 else None
                month_snap[lk].append(
                    {
                        "period": f"{year_eff}-{m:02d}",
                        "attainment_pct": att_p,
                        "real_trips": t["tr"],
                        "exp_trips": t["te"],
                    }
                )

        for lk, box in acc.items():
            snaps = month_snap[lk][-3:]
            result[lk] = _finalize_ytd_slice_only(
                grain=grain,
                lk=lk,
                year_eff=year_eff,
                through_label=through_label,
                sums_real=box["sums_real"],
                sums_exp=box["sums_exp"],
                drv_acc=box["drv_acc"],
                period_snapshots=snaps,
            )

    for lk in keys_from_display:
        if lk not in result:
            result[lk] = _empty_ytd_slice_payload(
                grain,
                lk,
                trace_note="sin períodos acumulados para esta clave en el alcance devuelto",
            )

    return result


def ytd_summary_api_to_authoritative_total_slice(
    ytd_summary_api: Optional[Dict[str, Any]],
    *,
    grain: str,
) -> Dict[str, Any]:
    """
    TOTAL YTD slice: copia campo a campo de meta.ytd_summary ya serializada para API.
    Garantiza misma semántica numérica que el JSON de ytd_summary.
    """
    if not ytd_summary_api or not isinstance(ytd_summary_api, dict) or ytd_summary_api.get("error"):
        trace = (
            f"ytd_summary en error o ausente: {ytd_summary_api.get('error')}"
            if isinstance(ytd_summary_api, dict) and ytd_summary_api.get("error")
            else "ytd_summary no disponible"
        )
        return {
            "grain": grain,
            "slice_key": "__PORTFOLIO__",
            "slice_level": "total",
            "ytd_real_trips": None,
            "ytd_plan_expected_trips": None,
            "ytd_gap_trips": None,
            "ytd_attainment_pct": None,
            "pacing_vs_expected": None,
            "ytd_trend": None,
            "ytd_real_revenue": None,
            "ytd_plan_expected_revenue": None,
            "ytd_gap_revenue": None,
            "ytd_avg_active_drivers_real": None,
            "ytd_avg_active_drivers_expected": None,
            "driver_productivity_ytd_real": None,
            "driver_productivity_ytd_expected": None,
            "metric_trace": {"insufficient_data": trace, "basis": "meta.ytd_summary"},
        }

    return {
        "grain": ytd_summary_api.get("grain", grain),
        "slice_key": "__PORTFOLIO__",
        "slice_level": "total",
        "ytd_real_trips": ytd_summary_api.get("ytd_real_trips"),
        "ytd_plan_expected_trips": ytd_summary_api.get("ytd_plan_expected_trips"),
        "ytd_gap_trips": ytd_summary_api.get("ytd_gap_trips"),
        "ytd_attainment_pct": ytd_summary_api.get("ytd_attainment_pct"),
        "pacing_vs_expected": ytd_summary_api.get("pacing_vs_expected"),
        "ytd_trend": ytd_summary_api.get("ytd_trend"),
        "ytd_real_revenue": ytd_summary_api.get("ytd_real_revenue"),
        "ytd_plan_expected_revenue": ytd_summary_api.get("ytd_plan_expected_revenue"),
        "ytd_gap_revenue": ytd_summary_api.get("ytd_gap_revenue"),
        "ytd_avg_active_drivers_real": ytd_summary_api.get("ytd_avg_active_drivers_real"),
        "ytd_avg_active_drivers_expected": ytd_summary_api.get("ytd_avg_active_drivers_expected"),
        "driver_productivity_ytd_real": ytd_summary_api.get("driver_productivity_ytd_real"),
        "driver_productivity_ytd_expected": ytd_summary_api.get("driver_productivity_ytd_expected"),
        "metric_trace": {
            "basis": "identical_fields_to_meta_ytd_summary_api",
            "source": "meta.ytd_summary",
        },
    }


def _aggregate_ytd_slice_payloads_for_scope(
    slices: List[Dict[str, Any]],
    *,
    grain: str,
    slice_key: str,
    slice_level: str,
) -> Dict[str, Any]:
    """Rollup aditivo autoritativo (FASE 3.8B): suma viajes/revenue; drivers ponderados."""
    clean = [s for s in slices if isinstance(s, dict)]
    if not clean:
        return {
            "grain": grain,
            "slice_key": slice_key,
            "slice_level": slice_level,
            "ytd_real_trips": None,
            "ytd_plan_expected_trips": None,
            "ytd_gap_trips": None,
            "ytd_attainment_pct": None,
            "pacing_vs_expected": None,
            "ytd_trend": None,
            "ytd_real_revenue": None,
            "ytd_plan_expected_revenue": None,
            "ytd_gap_revenue": None,
            "ytd_avg_active_drivers_real": None,
            "ytd_avg_active_drivers_expected": None,
            "driver_productivity_ytd_real": None,
            "driver_productivity_ytd_expected": None,
            "metric_trace": {
                "insufficient_data": "sin slices hijas para agregar",
                "basis": "authoritative_backend_additive_rollup",
                "slice_level": slice_level,
            },
        }

    sum_tr = sum_te = sum_rr = sum_re = 0.0
    has_tr = has_te = has_rr = has_re = False
    drv_num_r = drv_den_r = drv_num_e = drv_den_e = 0.0
    child_keys: List[str] = []

    for y in clean:
        sk = y.get("slice_key")
        if sk is not None:
            child_keys.append(str(sk))
        t = _safe_float(y.get("ytd_real_trips"))
        if t is not None:
            sum_tr += float(t)
            has_tr = True
        e = _safe_float(y.get("ytd_plan_expected_trips"))
        if e is not None:
            sum_te += float(e)
            has_te = True
        rr = _safe_float(y.get("ytd_real_revenue"))
        if rr is not None:
            sum_rr += float(rr)
            has_rr = True
        re = _safe_float(y.get("ytd_plan_expected_revenue"))
        if re is not None:
            sum_re += float(re)
            has_re = True

        trw = _safe_float(y.get("ytd_real_trips"))
        dr = _safe_float(y.get("ytd_avg_active_drivers_real"))
        if trw is not None and dr is not None and trw > 0:
            drv_num_r += float(dr) * float(trw)
            drv_den_r += float(trw)
        tew = _safe_float(y.get("ytd_plan_expected_trips"))
        de = _safe_float(y.get("ytd_avg_active_drivers_expected"))
        if tew is not None and de is not None and tew > 0:
            drv_num_e += float(de) * float(tew)
            drv_den_e += float(tew)

    ytd_att = round((sum_tr / sum_te) * 100.0, 2) if sum_te > 0 else None
    pacing = _pacing_vs_expected(ytd_att)
    gap_t = round(sum_tr - sum_te, 2) if (has_te or has_tr) else None
    gap_r = round(sum_rr - sum_re, 2) if (has_rr or has_re) else None
    avg_dr = round(drv_num_r / drv_den_r, 4) if drv_den_r > 0 else None
    avg_de = round(drv_num_e / drv_den_e, 4) if drv_den_e > 0 else None
    prod_r = round(sum_tr / avg_dr, 4) if avg_dr and avg_dr > 0 and has_tr else None
    prod_e = round(sum_te / avg_de, 4) if avg_de and avg_de > 0 and has_te else None

    return {
        "grain": grain,
        "slice_key": slice_key,
        "slice_level": slice_level,
        "ytd_real_trips": round(sum_tr, 2) if has_tr else None,
        "ytd_plan_expected_trips": round(sum_te, 2) if has_te else None,
        "ytd_gap_trips": gap_t,
        "ytd_attainment_pct": ytd_att,
        "pacing_vs_expected": pacing,
        "ytd_trend": None,
        "ytd_real_revenue": round(sum_rr, 2) if has_rr else None,
        "ytd_plan_expected_revenue": round(sum_re, 2) if has_re else None,
        "ytd_gap_revenue": gap_r,
        "ytd_avg_active_drivers_real": avg_dr,
        "ytd_avg_active_drivers_expected": avg_de,
        "driver_productivity_ytd_real": prod_r,
        "driver_productivity_ytd_expected": prod_e,
        "metric_trace": {
            "basis": "authoritative_backend_additive_rollup",
            "slice_level": slice_level,
            "child_slice_keys_sample": child_keys[:25],
            "child_count": len(child_keys),
        },
    }


def build_authoritative_ytd_block(
    *,
    grain: str,
    by_line: Dict[Tuple, Dict[str, Any]],
    ytd_summary_api: Optional[Dict[str, Any]],
    display_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Bloque meta.authoritative_ytd: total = ytd_summary; país/ciudad = rollup desde by_line.
    """
    total_row = {
        "row_type": "total",
        "row_scope_key": "__PORTFOLIO__",
        "ytd_slice": ytd_summary_api_to_authoritative_total_slice(ytd_summary_api, grain=grain),
    }

    countries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    cities: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for lk, ytd in by_line.items():
        co, ci, _, _, _ = lk
        countries[str(co)].append(ytd)
        cities[f"{co}::{ci}"].append(ytd)

    by_country: Dict[str, Dict[str, Any]] = {}
    for ckey, sl in countries.items():
        by_country[ckey] = {
            "row_type": "country",
            "row_scope_key": ckey,
            "ytd_slice": _aggregate_ytd_slice_payloads_for_scope(
                sl, grain=grain, slice_key=ckey, slice_level="country",
            ),
        }

    by_city: Dict[str, Dict[str, Any]] = {}
    for ck, sl in cities.items():
        by_city[ck] = {
            "row_type": "city",
            "row_scope_key": ck,
            "ytd_slice": _aggregate_ytd_slice_payloads_for_scope(
                sl, grain=grain, slice_key=ck, slice_level="city",
            ),
        }

    rows_out: List[Dict[str, Any]] = [total_row]
    rows_out.extend(by_country.values())
    rows_out.extend(by_city.values())

    _ = display_rows  # reservado: validaciones futuras / trazas
    return {
        "total": total_row,
        "by_country": by_country,
        "by_city": by_city,
        "rows": rows_out,
    }


def apply_authoritative_projection_ytd(
    conn: Any,
    display_rows: List[Dict[str, Any]],
    *,
    grain: str,
    ytd_summary_api: Optional[Dict[str, Any]],
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
    """
    FASE 3.8B — Única vía: ytd_slice + row_type + row_scope_key por fila;
    meta.authoritative_ytd con total/país/ciudad desde backend.
    """
    if not display_rows:
        return build_authoritative_ytd_block(
            grain=grain,
            by_line={},
            ytd_summary_api=ytd_summary_api,
            display_rows=display_rows,
        )

    by_key = compute_ytd_slice_by_line_key(
        conn,
        grain=grain,
        display_rows=display_rows,
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
    for r in display_rows:
        lk = _line_key(r)
        r["ytd_slice"] = by_key[lk]
        r["row_type"] = "subfleet" if r.get("is_subfleet") else "lob"
        r["row_scope_key"] = _slice_key_from_line_key(lk)

    return build_authoritative_ytd_block(
        grain=grain,
        by_line=by_key,
        ytd_summary_api=ytd_summary_api,
        display_rows=display_rows,
    )


def attach_ytd_slices_on_error(display_rows: List[Dict[str, Any]], grain: str, err: str) -> None:
    """Si compute_ytd_summary falla, mantiene contrato FASE 3.8 (objeto presente con traza)."""
    for r in display_rows:
        lk = _line_key(r)
        r["ytd_slice"] = _empty_ytd_slice_payload(grain, lk, trace_note=f"YTD slice no calculado: {err}")
        r["row_type"] = "subfleet" if r.get("is_subfleet") else "lob"
        r["row_scope_key"] = _slice_key_from_line_key(lk)
