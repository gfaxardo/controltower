"""
Alertas YTD accionables por dimensión (país / ciudad / LOB).

FASE 3.6 — aditivo, sin alterar tablas ni contratos existentes salvo meta.ytd_alerts.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from app.services.projection_ytd_period_service import (
    _avg_ticket_ratio,
    _classify_ytd_trend,
    _gap_decomposition_simple,
    _pacing_vs_expected,
    _safe_float,
    _ytd_calendar_cutoff,
)


def _peps() -> Any:
    from app.services import projection_expected_progress_service as m

    return m


DimKey = Union[str, Tuple[str, str], Tuple[str, str, str]]


@dataclass
class _DimAccumulator:
    trips_r: float = 0.0
    trips_e: float = 0.0
    rev_r: float = 0.0
    rev_e: float = 0.0
    drv_r_num: float = 0.0
    drv_r_den: float = 0.0
    drv_e_num: float = 0.0
    drv_e_den: float = 0.0
    period_snaps: List[Dict[str, Any]] = field(default_factory=list)


def _merge_row_ytd(acc: _DimAccumulator, row: Dict[str, Any]) -> None:
    tr = _safe_float(row.get("trips_completed"))
    te = _safe_float(row.get("trips_completed_projected_expected"))
    if tr is not None:
        acc.trips_r += float(tr)
    if te is not None:
        acc.trips_e += float(te)
    rr = _safe_float(row.get("revenue_yego_net"))
    re = _safe_float(row.get("revenue_yego_net_projected_expected"))
    if rr is not None:
        acc.rev_r += float(rr)
    if re is not None:
        acc.rev_e += float(re)
    if tr is not None and tr > 0:
        d_r = _safe_float(row.get("active_drivers"))
        if d_r is not None:
            acc.drv_r_num += float(d_r) * float(tr)
            acc.drv_r_den += float(tr)
    if te is not None and te > 0:
        d_e = _safe_float(row.get("active_drivers_projected_expected"))
        if d_e is not None:
            acc.drv_e_num += float(d_e) * float(te)
            acc.drv_e_den += float(te)


def _iter_dim_keys(row: Dict[str, Any]) -> Iterator[Tuple[str, DimKey]]:
    co = str(row.get("country") or "").strip()
    ci = str(row.get("city") or "").strip()
    bsn = str(row.get("business_slice_name") or "").strip()
    if not co:
        return
    yield "country", co
    if ci:
        yield "city", (co, ci)
    if ci and bsn:
        yield "lob", (co, ci, bsn)


def _empty_period_buckets() -> Dict[str, Dict[DimKey, Dict[str, float]]]:
    return {
        "country": defaultdict(lambda: {"r": 0.0, "e": 0.0}),
        "city": defaultdict(lambda: {"r": 0.0, "e": 0.0}),
        "lob": defaultdict(lambda: {"r": 0.0, "e": 0.0}),
    }


def _add_row_period(p: Dict[str, Dict[DimKey, Dict[str, float]]], row: Dict[str, Any]) -> None:
    tr = float(_safe_float(row.get("trips_completed")) or 0.0)
    te = float(_safe_float(row.get("trips_completed_projected_expected")) or 0.0)
    for dim, key in _iter_dim_keys(row):
        p[dim][key]["r"] += tr
        p[dim][key]["e"] += te


def _flush_period(
    registries: Dict[str, Dict[DimKey, _DimAccumulator]],
    p: Dict[str, Dict[DimKey, Dict[str, float]]],
    period_label: str,
) -> None:
    for dim in ("country", "city", "lob"):
        for key, v in p[dim].items():
            acc = registries[dim][key]
            att = round((v["r"] / v["e"]) * 100.0, 2) if v["e"] > 0 else None
            acc.period_snaps.append(
                {
                    "period": period_label,
                    "attainment_pct": att,
                    "real_trips": v["r"],
                    "exp_trips": v["e"],
                }
            )
            acc.period_snaps = acc.period_snaps[-3:]


def _default_registries() -> Dict[str, Dict[DimKey, _DimAccumulator]]:
    return {
        "country": defaultdict(_DimAccumulator),
        "city": defaultdict(_DimAccumulator),
        "lob": defaultdict(_DimAccumulator),
    }


def _entity_label(dim: str, key: DimKey) -> str:
    if dim == "country":
        return str(key)
    if dim == "city":
        k = key  # type: ignore[assignment]
        return f"{k[1]} · {k[0]}"
    k = key  # type: ignore[assignment]
    return f"{k[1]} - {k[2]}"


def _alert_level(pacing: Optional[str], trend: str) -> Optional[str]:
    if pacing == "behind" and trend == "deteriorating":
        return "critical"
    if pacing == "behind" and trend != "deteriorating":
        return "warning"
    if pacing == "ahead" and trend == "improving":
        return "opportunity"
    return None


def _main_driver(gd: Dict[str, Any]) -> str:
    parts = [
        ("volume", gd.get("volume_effect_drivers")),
        ("productivity", gd.get("productivity_effect_trips_per_driver")),
        ("ticket", gd.get("ticket_effect_revenue")),
    ]
    best = "volume"
    best_abs = 0.0
    for name, val in parts:
        if val is None:
            continue
        try:
            av = abs(float(val))
        except (TypeError, ValueError):
            continue
        if av > best_abs:
            best_abs = av
            best = name
    return best


def _acc_to_alert_dict(
    *,
    dim: str,
    key: DimKey,
    acc: _DimAccumulator,
) -> Optional[Dict[str, Any]]:
    y_r = acc.trips_r
    y_e = acc.trips_e
    if y_e <= 0:
        return None
    att = round((y_r / y_e) * 100.0, 2)
    gap_t = round(y_r - y_e, 2)
    gap_pct = round(((y_r - y_e) / y_e) * 100.0, 2) if y_e > 0 else None

    pacing = _pacing_vs_expected(att)
    trend = _classify_ytd_trend(acc.period_snaps)
    level = _alert_level(pacing, trend)
    if level is None:
        return None

    d_r = round(float(acc.drv_r_num) / acc.drv_r_den, 4) if acc.drv_r_den > 0 else None
    d_e = round(float(acc.drv_e_num) / acc.drv_e_den, 4) if acc.drv_e_den > 0 else None
    avg_tr = _avg_ticket_ratio(y_r if y_r else None, acc.rev_r if acc.rev_r else None)
    avg_te = _avg_ticket_ratio(y_e if y_e else None, acc.rev_e if acc.rev_e else None)

    gd = _gap_decomposition_simple(
        y_r=y_r,
        y_e=y_e,
        gap_t=float(gap_t),
        avg_d_r=d_r,
        avg_d_e=d_e,
        avg_ticket_r=avg_tr,
        avg_ticket_e=avg_te,
    )
    driver = _main_driver(gd)

    out: Dict[str, Any] = {
        "level": level,
        "dimension": dim,
        "entity": _entity_label(dim, key),
        "gap_trips": gap_t,
        "gap_pct": gap_pct,
        "principal_driver": driver,
        "pacing_vs_expected": pacing,
        "ytd_trend": trend,
        "ytd_attainment_pct": att,
    }
    if dim == "country":
        out["country"] = str(key)
    elif dim == "city":
        k = key  # type: ignore[assignment]
        out["country"], out["city"] = k[0], k[1]
    else:
        k = key  # type: ignore[assignment]
        out["country"], out["city"], out["business_slice"] = k[0], k[1], k[2]
    return out


def _sort_alerts(alerts: List[Dict[str, Any]]) -> None:
    """Impacto absoluto luego relativo (valor absoluto de brecha)."""

    def _k(a: Dict[str, Any]) -> Tuple[float, float]:
        gt = float(a.get("gap_trips") or 0.0)
        gp = float(a.get("gap_pct") or 0.0)
        return (-abs(gt), -abs(gp))

    alerts.sort(key=_k)


def compute_ytd_alerts(
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
) -> List[Dict[str, Any]]:
    pe = _peps()
    year_eff = year if year is not None else today.year
    cutoff = _ytd_calendar_cutoff(year_eff, month, today)

    registries = _default_registries()

    if grain == "weekly":
        ref_monday = today - timedelta(days=today.weekday())
        by_week: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in display_rows:
            ws = r.get("week_start")
            if not ws:
                continue
            wsd = date.fromisoformat(str(ws)[:10])
            if wsd > ref_monday:
                continue
            if int(r.get("iso_year") or 0) != int(year_eff):
                continue
            by_week[str(ws)[:10]].append(r)
        for wk in sorted(by_week.keys()):
            p = _empty_period_buckets()
            for row in by_week[wk]:
                _add_row_period(p, row)
                for dim, key in _iter_dim_keys(row):
                    _merge_row_ytd(registries[dim][key], row)
            _flush_period(registries, p, wk)

    elif grain == "daily":
        plan_year_rows = pe._load_plan(plan_version, country, city, year_eff, None)
        plan_by_year = pe._resolve_and_index_plan(plan_year_rows, idx, map_rows)
        end_m = month if month else (today.month if year_eff == today.year else 12)
        all_rows: List[Tuple[str, Dict[str, Any]]] = []
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
                all_rows.append((td_s, row))
        all_rows.sort(key=lambda x: x[0])
        cur_day: Optional[str] = None
        p = _empty_period_buckets()
        for td_s, row in all_rows:
            if cur_day != td_s:
                if cur_day is not None:
                    _flush_period(registries, p, cur_day)
                p = _empty_period_buckets()
                cur_day = td_s
            _add_row_period(p, row)
            for dim, key in _iter_dim_keys(row):
                _merge_row_ytd(registries[dim][key], row)
        if cur_day is not None:
            _flush_period(registries, p, cur_day)

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
            p = _empty_period_buckets()
            period_label = f"{year_eff}-{m:02d}"
            for row in comb:
                _add_row_period(p, row)
                for dim, key in _iter_dim_keys(row):
                    _merge_row_ytd(registries[dim][key], row)
            _flush_period(registries, p, period_label)

    alerts: List[Dict[str, Any]] = []
    for dim in ("country", "city", "lob"):
        for key, acc in registries[dim].items():
            ad = _acc_to_alert_dict(dim=dim, key=key, acc=acc)
            if ad:
                alerts.append(ad)
    problems = [a for a in alerts if a["level"] in ("critical", "warning")]
    opps = [a for a in alerts if a["level"] == "opportunity"]
    _sort_alerts(problems)
    _sort_alerts(opps)
    return problems + opps
