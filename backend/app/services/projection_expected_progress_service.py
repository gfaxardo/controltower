"""
Projection Expected Progress Service — orquestador para modo Omniview Proyección.

Combina:
- Plan mensualizado desde ops.v_plan_projection_control_loop
- Real acumulado desde facts (month/week/day)
- Derivación semanal/diaria simple y trazable desde el plan mensual

Aditivo: no modifica servicios ni tablas existentes.
"""
from __future__ import annotations

import logging
import time
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

from psycopg2.extras import RealDictCursor

from app.config.control_loop_lob_mapping import resolve_excel_line_to_canonical
from app.contracts.data_contract import remove_accents
from app.db.connection import get_db
from app.services.business_slice_canonical_service import (
    business_slice_filter_variants,
    canonicalize_business_slice_name,
    normalize_business_slice_key,
)
from app.services.business_slice_service import (
    FACT_DAILY,
    FACT_MONTHLY,
    FACT_WEEKLY,
    compute_matrix_data_freshness,
    explicit_day_temporal_fields,
)
from app.services.control_loop_business_slice_resolve import (
    load_map_fallback_rows,
    load_rules_index_for_geos,
    resolve_to_business_slice_name,
)
from app.services.omniview_semantics_service import (
    compute_canonical_metrics,
    resolve_comparison_basis,
    resolve_signal,
)
from app.services.seasonality_curve_engine import (
    PROJECTABLE_KPIS,
    compute_expected_ratio,
)

logger = logging.getLogger(__name__)


# FASE_KPI_CONSISTENCY: subset de PROJECTABLE_KPIS que SÍ es aditivo entre granos.
# Solo estos KPIs deben someterse a conservation reconciliation y validaciones de
# SUM(weekly|daily) == monthly. active_drivers (semi_additive_distinct) se proyecta
# para visualización pero NO se reconcilia: forzar SUM(weekly_drivers)==monthly_drivers
# es semánticamente incorrecto.
try:
    from app.config.kpi_aggregation_rules import is_kpi_additive as _is_kpi_additive_contract

    ADDITIVE_PROJECTABLE_KPIS: Tuple[str, ...] = tuple(
        k for k in PROJECTABLE_KPIS if _is_kpi_additive_contract(k)
    )
except Exception:  # pragma: no cover - degradado a literal seguro
    ADDITIVE_PROJECTABLE_KPIS = ("trips_completed", "revenue_yego_net")


def _conservation_tolerance_ok(drift_abs: float, monthly_plan: Optional[float]) -> bool:
    """OK si drift pequeño en abs o en %% respecto al plan mensual."""
    if monthly_plan is None:
        return drift_abs <= 1.0
    if monthly_plan <= 0:
        return drift_abs <= 1.0
    try:
        from app.settings import settings

        tol_pct = float(getattr(settings, "PROJECTION_CONSERVATION_TOLERANCE_PCT", 0.1))
    except Exception:
        tol_pct = 0.1
    drift_pct = (drift_abs / monthly_plan) * 100.0
    return drift_abs <= 1.0 or drift_pct <= tol_pct


def _month_bounds(month_start: date) -> Tuple[date, date, int]:
    first = month_start.replace(day=1)
    days_in_month = monthrange(first.year, first.month)[1]
    last = date(first.year, first.month, days_in_month)
    return first, last, days_in_month


_MONTH_SHORT_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
_MONTH_SHORT_ES_UPPER = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def _iter_month_dates(month_start: date) -> List[date]:
    first, last, _ = _month_bounds(month_start)
    dates: List[date] = []
    current = first
    while current <= last:
        dates.append(current)
        current += timedelta(days=1)
    return dates


def _iso_week_context(trip_date: date) -> Dict[str, Any]:
    iso_year, iso_week, _ = trip_date.isocalendar()
    week_start = trip_date - timedelta(days=trip_date.weekday())
    week_end = week_start + timedelta(days=6)
    ms = _MONTH_SHORT_ES_UPPER
    if week_start.year != week_end.year:
        week_range_label = (
            f"{week_start.day} {ms[week_start.month - 1]} {week_start.year} – "
            f"{week_end.day} {ms[week_end.month - 1]} {week_end.year}"
        )
    else:
        week_range_label = (
            f"{week_start.day} {ms[week_start.month - 1]} – "
            f"{week_end.day} {ms[week_end.month - 1]}"
        )
    week_short = f"S{iso_week}-{iso_year}"
    week_label = f"{week_short} · {week_range_label}"
    return {
        "iso_year": iso_year,
        "iso_week": iso_week,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "week_label": week_label,
        "week_range_label": week_range_label,
        "week_full_label": week_label,
    }


def _month_bucket_key(trip_date: date) -> str:
    return f"{trip_date.year:04d}-{trip_date.month:02d}"


def _round_distribution_to_total(
    values: List[float],
    total: float,
    *,
    lower_bound: Optional[float] = None,
    upper_bound: Optional[float] = None,
) -> List[float]:
    rounded = [round(v, 2) for v in values]
    diff = round(total - sum(rounded), 2)
    if not rounded or abs(diff) < 0.01:
        return rounded

    candidate_indices = list(range(len(rounded) - 1, -1, -1))
    for idx in candidate_indices:
        candidate = round(rounded[idx] + diff, 2)
        if lower_bound is not None and candidate < round(lower_bound, 2) - 0.01:
            continue
        if upper_bound is not None and candidate > round(upper_bound, 2) + 0.01:
            continue
        rounded[idx] = candidate
        return rounded

    rounded[-1] = round(rounded[-1] + diff, 2)
    return rounded


def _daily_plan_values(monthly_total: Optional[float], month_dates: List[date]) -> Dict[str, Optional[float]]:
    if monthly_total is None:
        return {trip_date.isoformat(): None for trip_date in month_dates}
    if not month_dates:
        return {}
    total = float(monthly_total)
    if abs(total) < 1e-9:
        return {trip_date.isoformat(): 0.0 for trip_date in month_dates}
    values = _round_distribution_to_total(
        [total / len(month_dates) for _ in month_dates],
        total,
    )
    return {
        trip_date.isoformat(): value
        for trip_date, value in zip(month_dates, values)
    }


def _build_plan_distribution(plan: Dict[str, Any], plan_month: date) -> Dict[str, Any]:
    month_start = plan_month.replace(day=1)
    month_dates = _iter_month_dates(month_start)
    _, _, days_in_month = _month_bounds(month_start)
    daily_plans: Dict[str, Dict[str, Optional[float]]] = {}
    weekly_plans: Dict[str, Dict[str, Optional[float]]] = {kpi: {} for kpi in PROJECTABLE_KPIS}
    weekly_rows: Dict[str, Dict[str, Any]] = {}
    daily_rows: List[Dict[str, Any]] = []

    iso_context_by_date = {
        trip_date.isoformat(): _iso_week_context(trip_date)
        for trip_date in month_dates
    }

    for kpi in PROJECTABLE_KPIS:
        monthly_total = _safe_float(plan.get(_plan_column(kpi)))
        daily_plans[kpi] = _daily_plan_values(monthly_total, month_dates)

        for trip_date in month_dates:
            trip_date_key = trip_date.isoformat()
            iso_ctx = iso_context_by_date[trip_date_key]
            week_start = iso_ctx["week_start"]
            daily_value = daily_plans[kpi][trip_date_key]
            weekly_plans[kpi][week_start] = round(
                (weekly_plans[kpi].get(week_start) or 0.0) + (daily_value or 0.0),
                2,
            )

    weekly_sum = {
        kpi: round(sum(v for v in weekly_plans[kpi].values() if v is not None), 2)
        for kpi in PROJECTABLE_KPIS
    }
    daily_sum = {
        kpi: round(sum(v for v in daily_plans[kpi].values() if v is not None), 2)
        for kpi in PROJECTABLE_KPIS
    }

    for trip_date in month_dates:
        trip_date_key = trip_date.isoformat()
        iso_ctx = iso_context_by_date[trip_date_key]
        week_start = iso_ctx["week_start"]
        month_bucket = _month_bucket_key(trip_date)
        week_row = weekly_rows.setdefault(
            week_start,
            {
                **iso_ctx,
                "days_by_month": defaultdict(int),
                "trip_dates": [],
            },
        )
        week_row["days_by_month"][month_bucket] += 1
        week_row["trip_dates"].append(trip_date_key)
        daily_rows.append(
            {
                "trip_date": trip_date_key,
                "year": trip_date.year,
                "month_number": trip_date.month,
                "month_source": _month_bucket_key(trip_date),
                **iso_ctx,
            }
        )

    for week_start, week_row in weekly_rows.items():
        week_row["days_by_month"] = dict(sorted(week_row["days_by_month"].items()))
        week_row["weekly_plan"] = {
            kpi: weekly_plans[kpi].get(week_start)
            for kpi in PROJECTABLE_KPIS
        }
        week_row["daily_plan"] = {
            trip_date: {
                kpi: daily_plans[kpi].get(trip_date)
                for kpi in PROJECTABLE_KPIS
            }
            for trip_date in week_row["trip_dates"]
        }

    return {
        "month": _month_key(month_start),
        "days_in_month": days_in_month,
        "month_source": _month_bucket_key(month_start),
        "daily_rows": daily_rows,
        "weekly_rows": [weekly_rows[k] for k in sorted(weekly_rows.keys())],
        "weekly_plans": weekly_plans,
        "daily_plans": daily_plans,
        "weekly_sum": weekly_sum,
        "daily_sum": daily_sum,
    }


def _distribution_debug_entry(
    plan: Dict[str, Any],
    plan_key: Tuple,
    distribution: Dict[str, Any],
    *,
    grain: str,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "month": distribution["month"],
        "month_source": distribution["month_source"],
        "country": plan.get("country"),
        "city": plan.get("city"),
        "business_slice_name": plan.get("business_slice_name"),
        "days_in_month": distribution["days_in_month"],
        "weeks": [],
        "days": distribution.get("daily_rows", []),
        "weekly_sum": distribution.get("weekly_sum", {}),
        "daily_sum": distribution.get("daily_sum", {}),
    }

    for segment in distribution["weekly_rows"]:
        week_item: Dict[str, Any] = {
            "week_start": segment["week_start"],
            "week_end": segment["week_end"],
            "iso_year": segment["iso_year"],
            "iso_week": segment["iso_week"],
            "week_label": segment["week_label"],
            "week_range_label": segment["week_range_label"],
            "week_full_label": segment["week_full_label"],
            "days_by_month": segment["days_by_month"],
            "weekly_plan": segment["weekly_plan"],
        }
        if grain in ("weekly", "daily"):
            week_item["trip_dates"] = segment["trip_dates"]
            week_item["daily_plan"] = segment["daily_plan"]
        entry["weeks"].append(week_item)

    entry["plan_key"] = {
        "month": plan_key[0],
        "country": plan_key[1],
        "city": plan_key[2],
        "business_slice_name": plan_key[3],
    }
    return entry


def _slice_month_plan_key(r: Dict[str, Any]) -> Optional[Tuple]:
    """Agrupa filas projection por mismo criterio que _projection_join_key (canonical_value normalizado)."""
    mk = r.get("month")
    if not mk:
        return None
    co = _country_to_fact_name(str(r.get("country") or ""))
    ci = _city_to_fact_name(str(r.get("city") or ""))
    bsn = _canonical_slice_join_segment(r.get("business_slice_name"))
    return (mk, co, ci, bsn)


def _year_end_week_starts_included(year: int, month: int) -> List[str]:
    """Lunes en mes previo cuya semana ISO intersecta el mes pedido (ej. S1 / ene)."""
    first_day = date(year, month, 1)
    min_week_start = first_day - timedelta(days=first_day.weekday())
    if min_week_start < first_day:
        return [min_week_start.isoformat()]
    return []


def _reconcile_weekly_conservation(
    rows: List[Dict[str, Any]],
    plan_by_key: Dict[Tuple, Dict],
) -> Dict[str, Any]:
    """Ajusta la última semana del mes por tajada si SUM(week_plan) != plan mensual."""
    groups: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        k = _slice_month_plan_key(r)
        if k:
            groups[k].append(r)

    max_drift_pct = 0.0
    slices_adjusted = 0

    for key, group_rows in groups.items():
        plan = plan_by_key.get(key)
        if not plan:
            continue
        group_rows.sort(key=lambda x: (x.get("week_start") or ""))

        # FASE_KPI_CONSISTENCY: reconciliar conservation solo sobre KPIs aditivos
        # (trips_completed, revenue_yego_net). active_drivers se proyecta pero
        # NO se reconcilia (semi_additive_distinct).
        for kpi in ADDITIVE_PROJECTABLE_KPIS:
            plan_total = _safe_float(plan.get(_plan_column(kpi)))
            if plan_total is None:
                continue
            col = f"{kpi}_projected_total"
            s = sum((_safe_float(x.get(col)) or 0.0) for x in group_rows)
            drift_abs = abs(plan_total - s)
            drift_pct = (drift_abs / plan_total * 100.0) if plan_total else 0.0
            max_drift_pct = max(max_drift_pct, drift_pct)

            if _conservation_tolerance_ok(drift_abs, plan_total):
                continue
            if not group_rows:
                continue
            last = group_rows[-1]
            cur = _safe_float(last.get(col)) or 0.0
            adj = round(plan_total - s, 2)
            last[col] = round(cur + adj, 2)
            last[f"{kpi}_conservation_adjustment_applied"] = True
            last[f"{kpi}_conservation_adjustment_value"] = adj
            slices_adjusted += 1
            basis = last.get(f"{kpi}_comparison_basis") or "partial_week"
            actual = _safe_float(last.get(kpi))
            week_expected = _safe_float(last.get(f"{kpi}_projected_expected"))
            week_plan_total = _safe_float(last.get(col))
            canon = compute_canonical_metrics(actual, week_expected, week_plan_total, basis)
            last[f"{kpi}_attainment_pct"] = canon["avance_pct"]
            last[f"{kpi}_gap_to_expected"] = canon["gap_abs"]
            last[f"{kpi}_gap_pct"] = canon["gap_pct"]
            if actual is not None and week_plan_total is not None:
                last[f"{kpi}_gap_to_full"] = round(actual - week_plan_total, 2)
            if actual is not None and week_plan_total and week_plan_total > 0:
                last[f"{kpi}_completion_pct"] = round((actual / week_plan_total) * 100.0, 2)
            last[f"{kpi}_signal"] = resolve_signal(canon["avance_pct"], actual)

    return {
        "weekly_sum_checked": True,
        "max_drift_pct": round(max_drift_pct, 6),
        "slices_adjusted": slices_adjusted,
    }


def _reconcile_daily_conservation(
    rows: List[Dict[str, Any]],
    plan_by_key: Dict[Tuple, Dict],
) -> Dict[str, Any]:
    groups: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        k = _slice_month_plan_key(r)
        if k:
            groups[k].append(r)

    max_drift_pct = 0.0
    slices_adjusted = 0

    for key, group_rows in groups.items():
        plan = plan_by_key.get(key)
        if not plan:
            continue
        group_rows.sort(key=lambda x: (x.get("trip_date") or ""))

        # FASE_KPI_CONSISTENCY: reconciliar conservation solo sobre KPIs aditivos.
        for kpi in ADDITIVE_PROJECTABLE_KPIS:
            plan_total = _safe_float(plan.get(_plan_column(kpi)))
            if plan_total is None:
                continue
            col = f"{kpi}_projected_total"
            s = sum((_safe_float(x.get(col)) or 0.0) for x in group_rows)
            drift_abs = abs(plan_total - s)
            drift_pct = (drift_abs / plan_total * 100.0) if plan_total else 0.0
            max_drift_pct = max(max_drift_pct, drift_pct)

            if _conservation_tolerance_ok(drift_abs, plan_total):
                continue
            if not group_rows:
                continue
            last = group_rows[-1]
            cur = _safe_float(last.get(col)) or 0.0
            adj = round(plan_total - s, 2)
            last[col] = round(cur + adj, 2)
            last[f"{kpi}_conservation_adjustment_applied"] = True
            last[f"{kpi}_conservation_adjustment_value"] = adj
            basis = "full_day"
            actual = _safe_float(last.get(kpi))
            daily_expected = _safe_float(last.get(f"{kpi}_projected_expected"))
            plan_shard = _safe_float(last.get(col))
            canon = compute_canonical_metrics(actual, daily_expected, plan_shard, basis)
            last[f"{kpi}_attainment_pct"] = canon["avance_pct"]
            last[f"{kpi}_gap_to_expected"] = canon["gap_abs"]
            last[f"{kpi}_gap_pct"] = canon["gap_pct"]
            last[f"{kpi}_gap_to_full"] = canon["gap_abs"]
            last[f"{kpi}_completion_pct"] = canon["avance_pct"]
            last[f"{kpi}_signal"] = resolve_signal(canon["avance_pct"], actual)

    return {
        "daily_sum_checked": True,
        "max_drift_pct": round(max_drift_pct, 6),
        "slices_adjusted": slices_adjusted,
    }


def _fallback_level_summary(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in rows:
        for kpi in PROJECTABLE_KPIS:
            lv = r.get(f"{kpi}_fallback_level")
            if lv is None:
                continue
            key = str(int(lv))
            counts[key] = counts.get(key, 0) + 1
    return counts


def _validate_weekly_output(
    rows: List[Dict[str, Any]],
    plan_by_key: Dict[Tuple, Dict],
    year: Optional[int],
    month: Optional[int],
) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    if year is not None and month is not None:
        m0 = date(year, month, 1)
        week_edge = m0 - timedelta(days=m0.weekday())
        if week_edge < m0:
            edge_iso = week_edge.isoformat()
            for r in rows:
                if r.get("week_start") != edge_iso:
                    continue
                if _safe_float(r.get("trips_completed")) is None:
                    continue
                st = r.get("comparison_status")
                ok = st != "missing_plan"
                checks.append(
                    {
                        "name": "year_end_week_real_has_plan_row",
                        "week_start": edge_iso,
                        "passed": ok,
                        "comparison_status": st,
                        "note": None if ok else "REAL presente pero sin fila de plan emparejada",
                    }
                )
                break

    checks.append(
        {
            "name": "weekly_month_conservation_not_forced",
            "passed": True,
            "note": "weekly ISO cruza meses; no se exige SUM(weekly del mes) == monthly_plan",
        }
    )

    seen_week_slots: Set[Tuple[str, str, str]] = set()
    duplicated_slots: List[Dict[str, Any]] = []
    missing_iso_meta = 0
    for r in rows:
        slot = (
            r.get("week_start") or "",
            _city_to_fact_name(str(r.get("city") or "")),
            _canonical_slice_join_segment(r.get("business_slice_name")),
        )
        if slot in seen_week_slots:
            duplicated_slots.append(
                {
                    "week_start": r.get("week_start"),
                    "city": r.get("city"),
                    "business_slice_name": r.get("business_slice_name"),
                }
            )
        else:
            seen_week_slots.add(slot)
        if not r.get("week_end") or not r.get("iso_year") or not r.get("iso_week"):
            missing_iso_meta += 1

    checks.append(
        {
            "name": "iso_week_unique_slots",
            "duplicates": duplicated_slots,
            "passed": len(duplicated_slots) == 0,
        }
    )
    checks.append(
        {
            "name": "iso_week_metadata_present",
            "missing_rows": missing_iso_meta,
            "passed": missing_iso_meta == 0,
        }
    )

    vol_anomalies: List[Dict[str, Any]] = []
    by_g: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        k = _slice_month_plan_key(r)
        if k:
            by_g[k].append(r)
    for k, grp in by_g.items():
        grp.sort(key=lambda x: (x.get("week_start") or ""))
        vals = [_safe_float(r.get("trips_completed_projected_total")) for r in grp]
        vals = [v for v in vals if v is not None]
        if len(vals) < 2:
            continue
        avg_w = sum(vals) / len(vals)
        if avg_w <= 0:
            continue
        for r in grp:
            wv = _safe_float(r.get("trips_completed_projected_total"))
            if wv is None:
                continue
            if wv / avg_w > 1.5:
                vol_anomalies.append(
                    {
                        "week_start": r.get("week_start"),
                        "city": r.get("city"),
                        "business_slice_name": r.get("business_slice_name"),
                        "ratio_to_slice_avg": round(wv / avg_w, 4),
                    }
                )

    checks.append(
        {
            "name": "volatility_week_plan_vs_avg",
            "threshold_ratio": 1.5,
            "anomalies": vol_anomalies,
            "passed": len(vol_anomalies) == 0,
        }
    )

    passed_all = all(
        c.get("passed", True) for c in checks if isinstance(c, dict) and "passed" in c
    )
    return {"checks": checks, "passed_all": passed_all}


def _validate_daily_output(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Volatilidad diaria: share diario vs promedio de la tajada en el mes."""
    anomalies: List[Dict[str, Any]] = []
    by_g: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        k = _slice_month_plan_key(r)
        if k:
            by_g[k].append(r)
    for _, grp in by_g.items():
        grp.sort(key=lambda x: (x.get("trip_date") or ""))
        vals = [_safe_float(r.get("trips_completed_projected_total")) for r in grp]
        vals = [v for v in vals if v is not None]
        if len(vals) < 2:
            continue
        avg_d = sum(vals) / len(vals)
        if avg_d <= 0:
            continue
        for r in grp:
            dv = _safe_float(r.get("trips_completed_projected_total"))
            if dv is None:
                continue
            if dv / avg_d > 1.5:
                anomalies.append(
                    {
                        "trip_date": r.get("trip_date"),
                        "city": r.get("city"),
                        "business_slice_name": r.get("business_slice_name"),
                        "ratio_to_slice_avg": round(dv / avg_d, 4),
                    }
                )

    chk = {
        "name": "volatility_daily_plan_vs_avg",
        "threshold_ratio": 1.5,
        "anomalies": anomalies,
        "passed": len(anomalies) == 0,
    }
    return {"checks": [chk], "passed_all": len(anomalies) == 0}


def _compute_projection_confidence(row: Dict[str, Any]) -> str:
    fl = int(row.get("trips_completed_fallback_level") or 5)
    ca_val = abs(_safe_float(row.get("trips_completed_conservation_adjustment_value")) or 0.0)
    pt = _safe_float(row.get("trips_completed_projected_total")) or 0.0
    ca_pct = (ca_val / pt * 100.0) if pt > 0 else 0.0
    if fl <= 2 and ca_pct < 5.0:
        return "high"
    if fl <= 4 and ca_pct < 15.0:
        return "medium"
    return "low"


def _enrich_projection_row_trust(
    display_rows: List[Dict[str, Any]],
    grain: str,
    qa_checks_payload: Dict[str, Any],
) -> None:
    """In-place: projection_confidence y projection_anomaly (volatilidad vs media)."""
    weekly_vol_keys: Set[Tuple] = set()
    daily_vol_keys: Set[Tuple] = set()

    for chk in qa_checks_payload.get("checks") or []:
        if not isinstance(chk, dict):
            continue
        if chk.get("name") == "volatility_week_plan_vs_avg":
            for a in chk.get("anomalies") or []:
                weekly_vol_keys.add(
                    (
                        a.get("week_start"),
                        _city_to_fact_name(str(a.get("city") or "")),
                        _canonical_slice_join_segment(a.get("business_slice_name")),
                    )
                )
        if chk.get("name") == "volatility_daily_plan_vs_avg":
            for a in chk.get("anomalies") or []:
                daily_vol_keys.add(
                    (
                        a.get("trip_date"),
                        _city_to_fact_name(str(a.get("city") or "")),
                        _canonical_slice_join_segment(a.get("business_slice_name")),
                    )
                )

    for r in display_rows:
        r["projection_confidence"] = _compute_projection_confidence(r)
        if grain == "weekly":
            key = (
                r.get("week_start"),
                _city_to_fact_name(str(r.get("city") or "")),
                _canonical_slice_join_segment(r.get("business_slice_name")),
            )
            r["projection_anomaly"] = key in weekly_vol_keys
        elif grain == "daily":
            key = (
                r.get("trip_date"),
                _city_to_fact_name(str(r.get("city") or "")),
                _canonical_slice_join_segment(r.get("business_slice_name")),
            )
            r["projection_anomaly"] = key in daily_vol_keys
        else:
            r["projection_anomaly"] = False


_COUNTRY_NORM = {
    "peru": "pe", "perú": "pe", "pe": "pe",
    "colombia": "co", "col": "co", "co": "co",
}

_COUNTRY_FULL = {"pe": "peru", "co": "colombia"}

# Nombres de país tal como aparecen en ops.business_slice_mapping_rules
_COUNTRY_FOR_RULES = {"pe": "Perú", "co": "Colombia"}


def _norm_country(raw: str) -> str:
    return _COUNTRY_NORM.get((raw or "").strip().lower(), (raw or "").strip().lower())


def _to_full_country(code: str) -> str:
    return _COUNTRY_FULL.get(code, code)


def _country_to_rules_name(raw: str) -> str:
    """Convierte cualquier forma de país al nombre exacto en business_slice_mapping_rules."""
    code = _norm_country(raw)
    return _COUNTRY_FOR_RULES.get(code, raw)


def _country_to_fact_name(raw: str) -> str:
    """Convierte cualquier forma de país al nombre en FACT_MONTHLY (lowercase, sin tilde)."""
    code = _norm_country(raw)
    return _COUNTRY_FULL.get(code, remove_accents((raw or "").strip()).lower())


def _country_sql_match_values(raw: Optional[str]) -> list[str]:
    """Variantes de etiqueta de país para `lower(trim(column)) IN (...)` en plan y facts.

    Algunas tablas guardan 'colombia', otras 'co' o 'CO'; sin esto el filtro devuelve 0 filas
    y REAL-FIRST deja la matriz vacía aunque el plan exista.
    """
    if raw is None or not str(raw).strip():
        return []
    code = _norm_country(str(raw))
    variants: Set[str] = set()
    stripped = remove_accents(str(raw).strip()).lower()
    if stripped:
        variants.add(stripped)
    full = _to_full_country(code)
    if full:
        variants.add(full)
    if code and code != full:
        variants.add(code)
    for alias, mapped in _COUNTRY_NORM.items():
        if mapped == code:
            variants.add(alias)
    rules_label = _COUNTRY_FOR_RULES.get(code)
    if rules_label:
        variants.add(remove_accents(rules_label).lower())
    return sorted({v for v in variants if v and str(v).strip()})


def _append_country_sql_filter(
    clauses: list[str],
    params: list[Any],
    country: Optional[str],
    column: str = "country",
) -> None:
    vals = _country_sql_match_values(country)
    if not vals:
        return
    if len(vals) == 1:
        clauses.append(f"lower(trim({column})) = lower(trim(%s))")
        params.append(vals[0])
        return
    placeholders = ", ".join(["%s"] * len(vals))
    clauses.append(f"lower(trim({column})) IN ({placeholders})")
    params.extend(vals)


def _city_to_fact_name(raw: str) -> str:
    """Normaliza ciudad al formato de FACT_MONTHLY: lowercase sin tildes."""
    return remove_accents((raw or "").strip()).lower()


def _canonical_slice_join_segment(value: Any) -> str:
    """
    Segmento estable para join Plan vs Real: normalize(canonical_value) según dim_business_slice_mapping.
    Equivalente conceptual a canonical_business_slice en la dimensión (no usar business_slice raw).
    """
    c = canonicalize_business_slice_name(value)
    return normalize_business_slice_key(c)


def _append_business_slice_sql_filter(clauses: List[str], params: List[Any], business_slice: Optional[str]) -> None:
    if not business_slice:
        return
    variants = business_slice_filter_variants(business_slice)
    placeholders = ", ".join(["%s"] * len(variants))
    clauses.append(f"lower(trim(business_slice_name)) IN ({placeholders})")
    params.extend(normalize_business_slice_key(v) for v in variants)


def _log_projection_key_overlap(stage: str, plan_by_key: Dict[Tuple, Any], real_map: Dict[Tuple, Any]) -> None:
    """Diagnóstico: muestra tamaño intersección de claves plan vs fact (canonical join)."""
    rk = set(real_map.keys())
    pk = set(plan_by_key.keys())
    matched = pk & rk
    intersection_rate = round((len(matched) / len(pk) * 100.0), 1) if pk else 0.0
    logger.info(
        "%s join keys: real=%d plan=%d intersection=%d plan_only=%d real_only=%d intersection_rate=%.1f%%",
        stage,
        len(rk),
        len(pk),
        len(matched),
        len(pk - rk),
        len(rk - pk),
        intersection_rate,
    )
    if logger.isEnabledFor(logging.DEBUG) and (pk - rk):
        logger.debug("%s PLAN_ONLY sample (first 12):", stage)
        for x in sorted(pk - rk)[:12]:
            logger.debug("  period=%s country=%s city=%s bsn=%s", x[0], x[1], x[2], x[3])
    if logger.isEnabledFor(logging.DEBUG) and (rk - pk):
        logger.debug("%s REAL_ONLY sample (first 12):", stage)
        for x in sorted(rk - pk)[:12]:
            logger.debug("  period=%s country=%s city=%s bsn=%s", x[0], x[1], x[2], x[3])


def _merge_real_projection_rows(result: Dict[Tuple[str, str, str, str], Dict[str, Any]], key, row: Dict[str, Any]) -> None:
    if key not in result:
        result[key] = row
        return
    existing = result[key]
    for field in (
        "real_trips",
        "real_revenue",
        "real_revenue_raw",
        "real_active_drivers",
        "real_trips_cancelled",
    ):
        if existing.get(field) is None and row.get(field) is None:
            continue
        existing[field] = (existing.get(field) or 0) + (row.get(field) or 0)
    if existing.get("real_trips") and existing["real_trips"] > 0:
        weight_prev = float(existing.get("real_trips") or 0) - float(row.get("real_trips") or 0)
        weight_new = float(row.get("real_trips") or 0)
        total_weight = weight_prev + weight_new
        for field in ("real_avg_ticket", "real_commission_pct"):
            prev_val = existing.get(field)
            new_val = row.get(field)
            if total_weight > 0 and (prev_val is not None or new_val is not None):
                prev_num = float(prev_val or 0)
                new_num = float(new_val or 0)
                existing[field] = ((prev_num * weight_prev) + (new_num * weight_new)) / total_weight
    drivers = float(existing.get("real_active_drivers") or 0)
    trips = float(existing.get("real_trips") or 0)
    existing["real_trips_per_driver"] = (trips / drivers) if drivers > 0 else None
    den = float(existing.get("real_trips") or 0) + float(existing.get("real_trips_cancelled") or 0)
    existing["real_cancel_rate_pct"] = (100.0 * float(existing.get("real_trips_cancelled") or 0) / den) if den > 0 else None


def _projection_join_key(period_key: str, country: Any, city: Any, business_slice: Any) -> Tuple[str, str, str, str]:
    """Clave canónica compartida por plan resuelto y facts reales."""
    return (
        period_key,
        _country_to_fact_name(str(country or "")),
        _city_to_fact_name(str(city or "")),
        _canonical_slice_join_segment(str(business_slice or "")),
    )


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


def _semantic_ui_revenue(v: Any) -> Optional[float]:
    """Revenue en semántica UI: signo positivo sin perder el raw audit trail."""
    fv = _safe_float(v)
    if fv is None:
        return None
    return abs(fv)


def _copy_aux_real_metrics(row: Dict[str, Any], real_data: Optional[Dict[str, Any]]) -> None:
    """Completa KPIs no proyectables para que la UI no pierda ejecución real."""
    real = real_data or {}
    row["trips_cancelled"] = _safe_float(real.get("real_trips_cancelled"))
    row["avg_ticket"] = _safe_float(real.get("real_avg_ticket"))
    row["commission_pct"] = _safe_float(real.get("real_commission_pct"))
    row["trips_per_driver"] = _safe_float(real.get("real_trips_per_driver"))
    row["cancel_rate_pct"] = _safe_float(real.get("real_cancel_rate_pct"))
    row["revenue_yego_net_audit_raw"] = _safe_float(real.get("real_revenue_raw"))


def _scope_months_for_weekly_iso(
    year: Optional[int],
    month: Optional[int],
    today: date,
) -> List[Tuple[int, int]]:
    months: Set[Tuple[int, int]] = set()
    for week_start in _get_weeks_for_scope(year, month, today):
        for offset in range(7):
            trip_date = week_start + timedelta(days=offset)
            months.add((trip_date.year, trip_date.month))
    return sorted(months)


def _load_plan_for_projection_scope(
    plan_version: str,
    grain: str,
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
    today: date,
) -> List[Dict[str, Any]]:
    if grain != "weekly":
        return _load_plan(plan_version, country, city, year, month)

    scope_months = _scope_months_for_weekly_iso(year, month, today)
    if not scope_months:
        return _load_plan(plan_version, country, city, year, month)

    rows: List[Dict[str, Any]] = []
    for scope_year, scope_month in scope_months:
        rows.extend(_load_plan(plan_version, country, city, scope_year, scope_month))
    return rows


def _normalize_projection_scope(
    grain: str,
    year: Optional[int],
    month: Optional[int],
) -> Tuple[Optional[int], Optional[int], bool]:
    if grain == "weekly":
        return year, None, month is not None
    return year, month, False


def get_omniview_projection(
    plan_version: str,
    grain: str = "monthly",
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    debug_distribution: bool = False,
) -> Dict[str, Any]:
    """Main entry point for the Omniview Projection mode."""
    _t0 = time.perf_counter()
    today = date.today()
    requested_month = month
    year, month, ignored_month_filter = _normalize_projection_scope(grain, year, month)

    logger.info(
        "get_omniview_projection START grain=%s plan=%s country=%s city=%s year=%s month=%s",
        grain, plan_version, country, city, year, month,
    )
    if ignored_month_filter:
        logger.warning(
            "get_omniview_projection: grain=weekly ignora month=%s y usa scope ISO anual completo para year=%s",
            requested_month,
            year,
        )

    _t1 = time.perf_counter()
    plan_rows = _load_plan_for_projection_scope(
        plan_version, grain, country, city, year, month, today
    )
    logger.info("get_omniview_projection load_plan=%.2fs rows=%d", time.perf_counter() - _t1, len(plan_rows))

    if not plan_rows:
        df_empty = compute_matrix_data_freshness(
            grain,
            country=country,
            city=city,
            business_slice=business_slice,
            year=year,
            month=month,
        )
        return {
            "granularity": grain,
            "plan_version": plan_version,
            "data": [],
            "data_freshness": df_empty,
            "meta": {
                "plan_version": plan_version,
                "plan_loaded_at": None,
                "curve_summary": {"total_combinations": 0, "by_method": {}, "avg_confidence": None},
                "kpis_with_projection": list(PROJECTABLE_KPIS),
                "plan_derivation": {
                    "monthly_plan_only": True,
                    "response_grain": grain,
                    "weekly_daily_from_monthly": grain in ("weekly", "daily"),
                    "derivation_source": "ops.v_plan_projection_control_loop",
                    "distribution_model": "iso_week_from_daily_monthly_plan" if grain == "weekly" else ("daily_from_monthly_month_days" if grain == "daily" else "monthly_unchanged"),
                    "weekly_scope": "iso_full_weeks_by_year" if grain == "weekly" else None,
                    "requested_month_filter": requested_month,
                    "effective_month_filter": month,
                    "ignored_month_filter": ignored_month_filter,
                    "smoothing_applied": False,
                    "smoothing_alpha_week": None,
                    "smoothing_alpha_day": None,
                    "conservation_enforced": grain == "daily",
                    "year_end_weeks_included": [],
                    "fallback_level_summary": {},
                    "guardrails": None,
                },
                "conservation": {},
                "qa_checks": {},
                "kpi_contract": (lambda: __import__(
                    "app.config.kpi_aggregation_rules", fromlist=["kpi_contract_for_meta"]
                ).kpi_contract_for_meta())(),
                "distribution_debug": {"enabled": debug_distribution, "grain": grain, "rows": []},
                "message": "No hay proyección cargada para esta versión / filtros.",
                "data_freshness": df_empty,
            },
        }

    # Geos en formato que ops.business_slice_mapping_rules entiende: "Perú"/"Colombia" + ciudad con tildes
    geos: Set[Tuple[str, str]] = set()
    for p in plan_rows:
        co_rules = _country_to_rules_name(str(p["country"]))
        ci_raw = str(p["city"])
        geos.add((co_rules, ci_raw))

    _t2 = time.perf_counter()
    idx = load_rules_index_for_geos(geos)
    map_rows = load_map_fallback_rows()
    logger.info("get_omniview_projection load_rules=%.2fs", time.perf_counter() - _t2)

    _t3 = time.perf_counter()
    plan_by_key = _resolve_and_index_plan(plan_rows, idx, map_rows)
    logger.info("get_omniview_projection resolve_plan=%.2fs keys=%d", time.perf_counter() - _t3, len(plan_by_key))

    # Separar filas resueltas de no resueltas para trazabilidad
    resolved_plan_by_key: Dict[Tuple, Dict] = {}
    unresolved_list: List[Dict] = []
    for key, plan in plan_by_key.items():
        if plan.get("resolution_status") == "resolved":
            resolved_plan_by_key[key] = plan
        else:
            unresolved_list.append({
                "raw_city": plan.get("raw_city", ""),
                "city_norm": plan.get("city", ""),
                "raw_lob": plan.get("raw_lob", ""),
                "bsn_fallback": plan.get("business_slice_name", ""),
                "resolution_source": plan.get("resolution_source", "unresolved"),
            })

    if unresolved_list:
        logger.warning(
            "get_omniview_projection: %d filas del plan sin resolver a tajada canónica — %s",
            len(unresolved_list),
            [f"{u['raw_city']}:{u['raw_lob']}" for u in unresolved_list[:5]],
        )

    logger.info(
        "get_omniview_projection plan_rows=%d resolved_plan_keys=%d unresolved_plan=%d",
        len(plan_rows),
        len(resolved_plan_by_key),
        len(unresolved_list),
    )

    _t4 = time.perf_counter()
    distribution_debug_rows: List[Dict[str, Any]] = []
    with get_db() as conn:
        if grain == "monthly":
            result_rows, plan_without_real, real_rows = _build_monthly(
                conn, resolved_plan_by_key, today, country, city, business_slice, year, month
            )
        elif grain == "weekly":
            result_rows, plan_without_real, real_rows, distribution_debug_rows = _build_weekly(
                conn, resolved_plan_by_key, today, country, city, business_slice, year, month
            )
        else:
            result_rows, plan_without_real, real_rows, distribution_debug_rows = _build_daily(
                conn, resolved_plan_by_key, today, country, city, business_slice, year, month
            )

    # REAL-FIRST: result_rows = base real (matched + missing_plan). Las filas solo-plan
    # deben seguir en `data` para que la matriz no quede vacía cuando el hecho no trae filas.
    display_rows: List[Dict[str, Any]] = list(result_rows) + list(plan_without_real)

    year_end_weeks_included: List[str] = []
    if year is not None and month is not None:
        year_end_weeks_included = _year_end_week_starts_included(year, month)

    conservation_meta: Dict[str, Any] = {}
    qa_checks_payload: Dict[str, Any] = {}
    if grain == "weekly":
        conservation_meta = {
            "weekly_sum_checked": False,
            "note": "weekly_iso_from_daily: no se fuerza SUM(weekly dentro del mes) == monthly_plan",
        }
        qa_checks_payload = _validate_weekly_output(
            display_rows, resolved_plan_by_key, year, month
        )
    elif grain == "daily":
        conservation_meta = _reconcile_daily_conservation(
            display_rows, resolved_plan_by_key
        )
        qa_checks_payload = _validate_daily_output(display_rows)

    if grain in ("weekly", "daily"):
        _enrich_projection_row_trust(display_rows, grain, qa_checks_payload)
    elif grain == "monthly":
        for r in display_rows:
            r["projection_confidence"] = _compute_projection_confidence(r)
            r["projection_anomaly"] = False

    if len(plan_without_real) > 0 and len(result_rows) == 0:
        logger.warning(
            "get_omniview_projection: REAL-FIRST vacío pero hay plan_without_real (n=%d)",
            len(plan_without_real),
        )

    if len(plan_without_real) > 0 and len(display_rows) == 0:
        logger.error(
            "get_omniview_projection: inconsistencia plan_without_real>0 y data vacío; reinyectando filas",
        )
        display_rows = list(plan_without_real)

    _build_elapsed = time.perf_counter() - _t4

    matched_count   = sum(1 for r in result_rows if r.get("comparison_status") == "matched")
    missing_plan_ct = sum(1 for r in result_rows if r.get("comparison_status") == "missing_plan")

    logger.info(
        "get_omniview_projection derive grain=%s monthly_plan_rows_loaded=%d resolved_plan_keys=%d "
        "real_rows_loaded=%d main_result_rows=%d plan_without_real_rows=%d data_rows=%d "
        "matched_rows=%d missing_plan_rows=%d unresolved_plan_rows=%d build_s=%.2f",
        grain,
        len(plan_rows),
        len(resolved_plan_by_key),
        real_rows,
        len(result_rows),
        len(plan_without_real),
        len(display_rows),
        matched_count,
        missing_plan_ct,
        len(unresolved_list),
        _build_elapsed,
    )

    curve_summary = _compute_curve_summary(display_rows)
    fallback_level_summary = _fallback_level_summary(display_rows)
    logger.info("get_omniview_projection TOTAL=%.2fs", time.perf_counter() - _t0)

    last_loaded = None
    for p in plan_rows:
        la = p.get("last_loaded_at")
        if la:
            last_loaded = str(la)
            break

    try:
        from app.config.kpi_aggregation_rules import kpi_contract_for_meta as _kpi_contract_for_meta
        kpi_contract_meta = _kpi_contract_for_meta()
    except Exception as _e_contract:
        logger.debug("kpi_contract_for_meta unavailable: %s", _e_contract)
        kpi_contract_meta = {}

    df_fresh = compute_matrix_data_freshness(
        grain,
        country=country,
        city=city,
        business_slice=business_slice,
        year=year,
        month=month,
    )

    return {
        "granularity": grain,
        "plan_version": plan_version,
        "data": display_rows,
        "data_freshness": df_fresh,
        "meta": {
            "plan_version": plan_version,
            "plan_loaded_at": last_loaded,
            "plan_derivation": {
                "monthly_plan_only": True,
                "response_grain": grain,
                "weekly_daily_from_monthly": grain in ("weekly", "daily"),
                "derivation_source": "ops.v_plan_projection_control_loop",
                "distribution_model": "iso_week_from_daily_monthly_plan" if grain == "weekly" else ("daily_from_monthly_month_days" if grain == "daily" else "monthly_unchanged"),
                "weekly_scope": "iso_full_weeks_by_year" if grain == "weekly" else None,
                "requested_month_filter": requested_month,
                "effective_month_filter": month,
                "ignored_month_filter": ignored_month_filter,
                "smoothing_applied": False,
                "smoothing_alpha_week": None,
                "smoothing_alpha_day": None,
                "conservation_enforced": grain == "daily",
                "year_end_weeks_included": year_end_weeks_included,
                "fallback_level_summary": fallback_level_summary,
                "guardrails": None,
            },
            "curve_summary": curve_summary,
            "conservation": conservation_meta,
            "qa_checks": qa_checks_payload,
            "kpis_with_projection": list(PROJECTABLE_KPIS),
            # FASE_KPI_CONSISTENCY: contrato cross-grain para que la UI sepa
            # qué KPIs son aditivos, distinct y ratios, y qué notas mostrar
            # en tooltip / drill / badges sin inducir comparaciones inválidas.
            "kpi_contract": kpi_contract_meta,
            # ── No mapeados (sin resolución a tajada) ──────────────────────────
            "unresolved": {
                "count": len(unresolved_list),
                "rows": unresolved_list,
            },
            # ── Plan resuelto pero sin ejecución real ──────────────────────────
            "plan_without_real": {
                "count": len(plan_without_real),
                "rows": plan_without_real,
            },
            "distribution_debug": {
                "enabled": debug_distribution,
                "grain": grain,
                "rows": distribution_debug_rows if debug_distribution and grain in ("weekly", "daily") else [],
            },
            # ── Estadísticas de reconciliación ─────────────────────────────────
            "reconciliation": {
                "matched":           matched_count,
                "missing_plan":      missing_plan_ct,
                "plan_without_real": len(plan_without_real),
                "unresolved_plan":   len(unresolved_list),
                "total_real_rows":   len(result_rows),
                "total_display_rows": len(display_rows),
            },
            "data_freshness": df_fresh,
        },
    }


def _load_plan(
    plan_version: str,
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> List[Dict[str, Any]]:
    """
    Carga filas del plan para la version dada.
    Fuente primaria: ops.v_plan_projection_control_loop (staging.control_loop_plan_metric_long).
    Fuente secundaria: ops.plan_trips_monthly (planes subidos via upload_ruta27_ui).
    Si la fuente primaria no tiene filas para plan_version, se usa la secundaria.
    """
    params: List[Any] = [plan_version]
    clauses = ["plan_version = %s"]

    _append_country_sql_filter(clauses, params, country)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())

    where = " AND ".join(clauses)

    # ── Fuente primaria: vista control loop ──────────────────────────────
    primary_params = list(params)
    primary_clauses = list(clauses)
    if year:
        primary_clauses.append("EXTRACT(YEAR FROM period_date) = %s")
        primary_params.append(year)
    if month:
        primary_clauses.append("EXTRACT(MONTH FROM period_date) = %s")
        primary_params.append(month)

    primary_sql = f"""
        SELECT plan_version, period_date, country, city,
               linea_negocio_canonica, linea_negocio_excel,
               projected_trips, projected_revenue, projected_active_drivers,
               last_loaded_at
        FROM ops.v_plan_projection_control_loop
        WHERE {' AND '.join(primary_clauses)}
    """

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(primary_sql, primary_params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

    if rows:
        return rows

    # ── Fuente secundaria: ops.plan_trips_monthly ────────────────────────
    # Se activa cuando la vista no tiene datos para la version pedida
    # (planes subidos via upload_ruta27_ui / plantilla Control Tower).
    secondary_params = list(params)
    secondary_clauses = list(clauses)
    if year:
        secondary_clauses.append("EXTRACT(YEAR FROM month) = %s")
        secondary_params.append(year)
    if month:
        secondary_clauses.append("EXTRACT(MONTH FROM month) = %s")
        secondary_params.append(month)

    secondary_sql = f"""
        SELECT
            plan_version,
            month                   AS period_date,
            country,
            city,
            lob_base                AS linea_negocio_canonica,
            lob_base                AS linea_negocio_excel,
            projected_trips,
            projected_revenue,
            projected_drivers       AS projected_active_drivers,
            created_at              AS last_loaded_at
        FROM ops.plan_trips_monthly
        WHERE {' AND '.join(secondary_clauses)}
    """

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(secondary_sql, secondary_params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

    if rows:
        logger.info(
            "_load_plan: usando fuente secundaria (ops.plan_trips_monthly) "
            "para plan_version=%s — %d filas", plan_version, len(rows)
        )

    return rows


def _resolve_and_index_plan(
    plan_rows: List[Dict[str, Any]],
    idx,
    map_rows: List[dict],
) -> Dict[Tuple[str, str, str, str], Dict[str, Any]]:
    """
    Resuelve líneas de plan a business_slice_name canónico e indexa por
    (month, country_fact, city_fact, bsn_lower).

    Normalización de formatos:
    - country: cualquier forma → "peru"/"colombia" (formato FACT_MONTHLY)
    - city: cualquier forma → lowercase sin tildes (formato FACT_MONTHLY)
    - bsn: nombre canónico de tajada desde business_slice_mapping_rules

    Para lookup en reglas se usa "Perú"/"Colombia" + ciudad con tildes
    (formato exact de ops.business_slice_mapping_rules).
    """
    result: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}

    for p in plan_rows:
        ci_raw = str(p["city"])
        co_raw = str(p["country"])

        # Formato para lookup en reglas (ops.business_slice_mapping_rules)
        co_rules = _country_to_rules_name(co_raw)   # "Perú" / "Colombia"

        # Formato para matchear FACT_MONTHLY (display y clave real_map)
        co_fact = _country_to_fact_name(co_raw)     # "peru" / "colombia"
        ci_fact = _city_to_fact_name(ci_raw)         # "lima", "bogota" (sin tildes, lowercase)

        lob_excel = str(p.get("linea_negocio_excel") or "")
        lob_canon = str(p.get("linea_negocio_canonica") or "")

        # Derivar clave canónica snake_case ("auto_taxi") para PLAN_LINE_TO_SLICE_CANDIDATES.
        # Necesario cuando el plan almacena etiquetas de display ("Auto Taxi") en vez de la clave.
        canon_key, _ = resolve_excel_line_to_canonical(lob_excel or lob_canon)
        plan_line_key = canon_key or lob_canon or lob_excel

        # Resolver usando formato de reglas para país/ciudad
        bsn, source = resolve_to_business_slice_name(
            idx, map_rows, co_rules, ci_raw, lob_excel, plan_line_key
        )
        is_resolved = bool(bsn) and source != "unresolved"
        if not bsn:
            bsn = lob_excel or lob_canon or "__unresolved__"
        bsn = canonicalize_business_slice_name(bsn)

        mk = _month_key(p["period_date"])
        # Clave canónica: usa formato FACT_MONTHLY para matchear real_map correctamente
        key = _projection_join_key(mk, co_fact, ci_fact, bsn)

        if key in result:
            existing = result[key]
            for metric_key in ("projected_trips", "projected_revenue", "projected_active_drivers"):
                ev = _safe_float(existing.get(metric_key))
                nv = _safe_float(p.get(metric_key))
                if ev is not None and nv is not None:
                    existing[metric_key] = ev + nv
                elif nv is not None:
                    existing[metric_key] = nv
        else:
            result[key] = {
                "period_date": p["period_date"],
                "country": co_fact,        # "peru"/"colombia" — mismo que FACT_MONTHLY
                "city": ci_fact,           # "lima"/"bogota" — mismo que FACT_MONTHLY
                "raw_city": ci_raw,        # "LIMA PE", "Bogotá" — para auditoría
                "raw_lob": lob_excel or lob_canon,
                "business_slice_name": bsn,
                "resolution_source": source,
                "resolution_status": "resolved" if is_resolved else "unresolved",
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
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """Construcción de filas mensuales en modo REAL-FIRST.

    Retorna (main_result, plan_without_real, real_map_key_count):
      main_result:       filas con base real (con o sin plan)
      plan_without_real: filas con plan resuelto pero sin ejecución real visible
      real_map_key_count: len(real_map) — filas/claves cargadas desde facts
    """
    real_map = _load_real_monthly(conn, country, city, business_slice, year, month)
    _log_projection_key_overlap("_build_monthly", plan_by_key, real_map)

    # Caché compartido por request (evita SQL repetidas para el mes actual)
    _curve_cache: Dict = {}
    _dist_cache:  Dict = {}

    main_result: List[Dict[str, Any]] = []
    seen_plan_keys: Set[Tuple] = set()

    # ── LOOP 1: REAL-FIRST — iterar ejecución real como base ──────────────────
    for real_key, real_data in real_map.items():
        bsn_lower = real_key[3]
        if business_slice and business_slice.strip().lower() != bsn_lower:
            continue

        mk = real_key[0]
        co_norm, ci_norm = real_key[1], real_key[2]
        month_date = date.fromisoformat(mk)
        cutoff = _monthly_cutoff(month_date, today)

        plan = plan_by_key.get(real_key)
        if plan:
            seen_plan_keys.add(real_key)
            row = _build_projection_row_monthly(
                conn, plan, month_date, cutoff, co_norm, ci_norm, bsn_lower,
                real_map, "monthly",
                _cache=_curve_cache, _dist_cache=_dist_cache,
            )
            row["comparison_status"] = "matched"
        else:
            row = _build_no_plan_row(real_data, mk, "monthly")
            # comparison_status ya está en _build_no_plan_row = "missing_plan"
        main_result.append(row)

    # ── LOOP 2: PLAN SIN REAL — filas del plan sin ejecución correspondiente ──
    plan_without_real: List[Dict[str, Any]] = []
    for plan_key, plan in plan_by_key.items():
        if plan_key in seen_plan_keys:
            continue
        mk = plan_key[0]
        co_norm, ci_norm, bsn_lower = plan_key[1], plan_key[2], plan_key[3]
        month_date = date.fromisoformat(mk)
        cutoff = _monthly_cutoff(month_date, today)
        # Construir la fila con plan pero sin real (real_map vacío para este key)
        row = _build_projection_row_monthly(
            conn, plan, month_date, cutoff, co_norm, ci_norm, bsn_lower,
            {}, "monthly",  # empty real_map → actual=None para todos los KPIs
            _cache=_curve_cache, _dist_cache=_dist_cache,
        )
        row["comparison_status"] = "plan_without_real"
        plan_without_real.append(row)

    def _sort_key(r: Dict) -> Tuple:
        return (
            r.get("month", ""),
            0 if r.get("country", "") == "peru" else 1,
            r.get("city", ""),
            r.get("business_slice_name", ""),
        )

    main_result.sort(key=_sort_key)
    plan_without_real.sort(key=_sort_key)
    return main_result, plan_without_real, len(real_map)


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
    _cache: Optional[Dict] = None,
    _dist_cache: Optional[Dict] = None,
) -> Dict[str, Any]:
    bsn = plan["business_slice_name"]
    co_full = plan["country"]   # "peru"/"colombia" — formato FACT_MONTHLY
    ci = plan["city"]           # "lima"/"bogota" — formato FACT_MONTHLY

    real_key = (_month_key(month_date), co_norm, ci_norm, bsn_lower)
    real = real_map.get(real_key, {})

    row: Dict[str, Any] = {
        "country": co_full,
        "city": ci,
        "business_slice_name": bsn,
        "fleet_display_name": "",  # evita duplicación visual "Auto Taxi · Auto Taxi"
        "is_subfleet": False,
        "subfleet_name": "",
        "month": _month_key(month_date),
    }

    # Para meses completos (pasados y futuros), cutoff_day == último día del mes
    # → ratio esperado = 1.0. Solo el mes actual parcial necesita la curva estacional.
    days_in_month = monthrange(month_date.year, month_date.month)[1]
    is_full_month = cutoff_day >= days_in_month
    _full_month_curve = {
        "expected_ratio_to_date": 1.0,
        "curve_method": "full_month",
        "confidence": "exact",
        "fallback_level": 0,
    }

    # ── Semántica canónica: comparison_basis es igual para todos los KPIs del mes ──
    comparison_basis = resolve_comparison_basis(is_full_month, "monthly")

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

        curve = (
            _full_month_curve
            if is_full_month
            else compute_expected_ratio(
                _to_full_country(co_norm), ci, bsn, kpi, month_date, cutoff_day, conn=conn,
                _cache=_cache, _dist_cache=_dist_cache,
            )
        )
        expected_ratio = curve["expected_ratio_to_date"]
        expected_to_date = round(plan_total * expected_ratio, 2) if plan_total is not None else None

        # ── Métricas canónicas (FASE 3.5) ─────────────────────────────────
        canon = compute_canonical_metrics(actual, expected_to_date, plan_total, comparison_basis)

        gap_to_full = None
        if actual is not None and plan_total is not None:
            gap_to_full = round(actual - plan_total, 2)

        completion = None
        if actual is not None and plan_total is not None and plan_total > 0:
            completion = round((actual / plan_total) * 100.0, 2)

        row[kpi] = actual
        row[f"{kpi}_projected_total"]    = plan_total
        row[f"{kpi}_projected_expected"] = expected_to_date
        row[f"{kpi}_attainment_pct"]     = canon["avance_pct"]   # NUNCA negativo
        row[f"{kpi}_gap_to_expected"]    = canon["gap_abs"]
        row[f"{kpi}_gap_pct"]            = canon["gap_pct"]       # campo canónico nuevo
        row[f"{kpi}_gap_to_full"]        = gap_to_full
        row[f"{kpi}_completion_pct"]     = completion
        row[f"{kpi}_signal"]             = resolve_signal(canon["avance_pct"], actual)
        row[f"{kpi}_curve_method"]       = curve.get("curve_method", "linear_fallback")
        row[f"{kpi}_curve_confidence"]   = curve.get("confidence", "fallback")
        row[f"{kpi}_fallback_level"]     = curve.get("fallback_level", 5)
        row[f"{kpi}_expected_ratio"]     = expected_ratio
        row[f"{kpi}_comparison_basis"]   = comparison_basis       # campo canónico nuevo

    _copy_aux_real_metrics(row, real)
    return row


def _week_intersects_month(week_start: date, month_start: date) -> bool:
    """True si el bloque lun-dom de week_start intersecta el mes calendar de month_start."""
    m0 = month_start.replace(day=1)
    week_end = week_start + timedelta(days=6)
    next_m = date(m0.year + (m0.month // 12), (m0.month % 12) + 1, 1)
    month_end = next_m - timedelta(days=1)
    return week_start <= month_end and week_end >= m0


def _scope_month_start(year: Optional[int], month: Optional[int], today: date) -> Optional[date]:
    if year is not None and month is not None:
        return date(year, month, 1)
    return None


def _build_iso_plan_maps(
    plan_by_key: Dict[Tuple, Dict],
) -> Tuple[Dict[Tuple, Dict[str, Any]], Dict[Tuple, Dict[str, Any]], List[Dict[str, Any]]]:
    daily_plan_map: Dict[Tuple, Dict[str, Any]] = {}
    weekly_plan_map: Dict[Tuple, Dict[str, Any]] = {}
    distribution_debug: List[Dict[str, Any]] = []

    for plan_key, plan in plan_by_key.items():
        mk, co_norm, ci_norm, bsn_lower = plan_key
        distribution = _build_plan_distribution(plan, date.fromisoformat(mk))
        distribution_debug.append(
            _distribution_debug_entry(plan, plan_key, distribution, grain="daily")
        )

        for day_meta in distribution["daily_rows"]:
            trip_date = day_meta["trip_date"]
            slot = (trip_date, co_norm, ci_norm, bsn_lower)
            daily_plan_map[slot] = {
                "country": plan["country"],
                "city": plan["city"],
                "business_slice_name": plan["business_slice_name"],
                "month": distribution["month"],
                "month_source": day_meta["month_source"],
                "trip_date": trip_date,
                "week_start": day_meta["week_start"],
                "week_end": day_meta["week_end"],
                "iso_year": day_meta["iso_year"],
                "iso_week": day_meta["iso_week"],
                "week_label": day_meta["week_label"],
                "week_range_label": day_meta["week_range_label"],
                "week_full_label": day_meta["week_full_label"],
                "daily_plan": {
                    kpi: distribution["daily_plans"][kpi].get(trip_date)
                    for kpi in PROJECTABLE_KPIS
                },
                "monthly_totals": {
                    kpi: _safe_float(plan.get(_plan_column(kpi)))
                    for kpi in PROJECTABLE_KPIS
                },
            }

        for week_meta in distribution["weekly_rows"]:
            week_start = week_meta["week_start"]
            slot = (week_start, co_norm, ci_norm, bsn_lower)
            entry = weekly_plan_map.setdefault(
                slot,
                {
                    "country": plan["country"],
                    "city": plan["city"],
                    "business_slice_name": plan["business_slice_name"],
                    "month": None,
                    "week_start": week_meta["week_start"],
                    "week_end": week_meta["week_end"],
                    "iso_year": week_meta["iso_year"],
                    "iso_week": week_meta["iso_week"],
                    "week_label": week_meta["week_label"],
                    "week_range_label": week_meta["week_range_label"],
                    "week_full_label": week_meta["week_full_label"],
                    "days_by_month": defaultdict(int),
                    "weekly_plan": {kpi: 0.0 for kpi in PROJECTABLE_KPIS},
                },
            )
            for month_bucket, days_count in week_meta["days_by_month"].items():
                entry["days_by_month"][month_bucket] += days_count
            for kpi in PROJECTABLE_KPIS:
                entry["weekly_plan"][kpi] = round(
                    (entry["weekly_plan"].get(kpi) or 0.0)
                    + (week_meta["weekly_plan"].get(kpi) or 0.0),
                    2,
                )

    for entry in weekly_plan_map.values():
        months_sorted = sorted(entry["days_by_month"].keys())
        entry["days_by_month"] = dict(sorted(entry["days_by_month"].items()))
        entry["month"] = f"{months_sorted[0]}-01" if months_sorted else None

    return daily_plan_map, weekly_plan_map, distribution_debug


def _build_weekly_row_from_iso_plan(
    weekly_plan_data: Dict[str, Any],
    real_data: Optional[Dict[str, Any]],
    comparison_status: str,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "country": weekly_plan_data["country"],
        "city": weekly_plan_data["city"],
        "business_slice_name": weekly_plan_data["business_slice_name"],
        "fleet_display_name": "",
        "is_subfleet": False,
        "subfleet_name": "",
        "month": weekly_plan_data.get("month"),
        "week_start": weekly_plan_data["week_start"],
        "week_end": weekly_plan_data["week_end"],
        "iso_year": weekly_plan_data["iso_year"],
        "iso_week": weekly_plan_data["iso_week"],
        "week_label": weekly_plan_data["week_label"],
        "week_range_label": weekly_plan_data["week_range_label"],
        "week_full_label": weekly_plan_data["week_full_label"],
        "days_by_month": weekly_plan_data["days_by_month"],
        "distribution_model": "iso_week_from_daily_monthly_plan",
        "comparison_status": comparison_status,
    }

    for kpi in PROJECTABLE_KPIS:
        week_plan_total = _safe_float(weekly_plan_data["weekly_plan"].get(kpi))
        actual = _safe_float(real_data.get(_real_column(kpi))) if real_data else None
        canon = compute_canonical_metrics(actual, week_plan_total, week_plan_total, "full_week")

        row[kpi] = actual
        row[f"{kpi}_projected_total"] = week_plan_total
        row[f"{kpi}_projected_expected"] = week_plan_total
        row[f"{kpi}_attainment_pct"] = canon["avance_pct"]
        row[f"{kpi}_gap_to_expected"] = canon["gap_abs"]
        row[f"{kpi}_gap_pct"] = canon["gap_pct"]
        row[f"{kpi}_gap_to_full"] = round(actual - week_plan_total, 2) if actual is not None and week_plan_total is not None else None
        row[f"{kpi}_completion_pct"] = round((actual / week_plan_total) * 100.0, 2) if actual is not None and week_plan_total and week_plan_total > 0 else None
        row[f"{kpi}_signal"] = resolve_signal(canon["avance_pct"], actual)
        row[f"{kpi}_curve_method"] = "iso_week_from_daily_monthly_plan"
        row[f"{kpi}_curve_confidence"] = "exact"
        row[f"{kpi}_fallback_level"] = 0
        row[f"{kpi}_expected_ratio"] = None
        row[f"{kpi}_comparison_basis"] = "full_week"

    _copy_aux_real_metrics(row, real_data)
    return row


def _build_daily_row_from_monthly_daily_plan(
    daily_plan_data: Dict[str, Any],
    real_data: Optional[Dict[str, Any]],
    comparison_status: str,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "country": daily_plan_data["country"],
        "city": daily_plan_data["city"],
        "business_slice_name": daily_plan_data["business_slice_name"],
        "fleet_display_name": "",
        "is_subfleet": False,
        "subfleet_name": "",
        "month": daily_plan_data["month"],
        "month_source": daily_plan_data["month_source"],
        "trip_date": daily_plan_data["trip_date"],
        "week_start": daily_plan_data["week_start"],
        "week_end": daily_plan_data["week_end"],
        "iso_year": daily_plan_data["iso_year"],
        "iso_week": daily_plan_data["iso_week"],
        "week_label": daily_plan_data["week_label"],
        "week_range_label": daily_plan_data["week_range_label"],
        "week_full_label": daily_plan_data["week_full_label"],
        "distribution_model": "daily_from_monthly_month_days",
        "comparison_status": comparison_status,
    }
    td0 = daily_plan_data["trip_date"]
    td_s = td0.isoformat()[:10] if hasattr(td0, "isoformat") else str(td0)[:10]
    row.update(explicit_day_temporal_fields(td_s))

    for kpi in PROJECTABLE_KPIS:
        daily_plan = _safe_float(daily_plan_data["daily_plan"].get(kpi))
        monthly_total = _safe_float(daily_plan_data["monthly_totals"].get(kpi))
        actual = _safe_float(real_data.get(_real_column(kpi))) if real_data else None
        canon = compute_canonical_metrics(actual, daily_plan, daily_plan, "full_day")

        row[kpi] = actual
        row[f"{kpi}_projected_total"] = daily_plan
        row[f"{kpi}_projected_expected"] = daily_plan
        row[f"{kpi}_attainment_pct"] = canon["avance_pct"]
        row[f"{kpi}_gap_to_expected"] = canon["gap_abs"]
        row[f"{kpi}_gap_pct"] = canon["gap_pct"]
        row[f"{kpi}_gap_to_full"] = canon["gap_abs"]
        row[f"{kpi}_completion_pct"] = canon["avance_pct"]
        row[f"{kpi}_signal"] = resolve_signal(canon["avance_pct"], actual)
        row[f"{kpi}_curve_method"] = "daily_from_monthly_month_days"
        row[f"{kpi}_curve_confidence"] = "exact"
        row[f"{kpi}_fallback_level"] = 0
        row[f"{kpi}_expected_ratio"] = round((daily_plan / monthly_total), 6) if monthly_total not in (None, 0) and daily_plan is not None else None
        row[f"{kpi}_comparison_basis"] = "full_day"

    _copy_aux_real_metrics(row, real_data)
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
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, List[Dict[str, Any]]]:
    """REAL-FIRST weekly. Plan semanal ISO completo derivado desde daily_plan."""
    real_map = _load_real_weekly(conn, country, city, business_slice, year, month)
    _log_projection_key_overlap("_build_weekly", plan_by_key, real_map)
    _, weekly_plan_map, _distribution_debug = _build_iso_plan_maps(plan_by_key)
    distribution_debug = [
        {
            "country": data["country"],
            "city": data["city"],
            "business_slice_name": data["business_slice_name"],
            "week_start": data["week_start"],
            "week_end": data["week_end"],
            "iso_year": data["iso_year"],
            "iso_week": data["iso_week"],
            "week_label": data["week_label"],
            "week_range_label": data["week_range_label"],
            "week_full_label": data["week_full_label"],
            "days_by_month": data["days_by_month"],
            "weekly_plan": data["weekly_plan"],
        }
        for _, data in sorted(weekly_plan_map.items())
    ]

    main_result: List[Dict[str, Any]] = []
    plan_without_real: List[Dict[str, Any]] = []
    target_week_keys = {week_start.isoformat() for week_start in _get_weeks_for_scope(year, month, today)}

    all_slots = sorted(set(real_map.keys()) | set(weekly_plan_map.keys()))
    for slot in all_slots:
        ws, _, _, bsn_lower = slot
        if ws not in target_week_keys:
            continue
        if business_slice and business_slice.strip().lower() != bsn_lower:
            continue

        real_data = real_map.get(slot)
        weekly_plan_data = weekly_plan_map.get(slot)

        if weekly_plan_data and real_data:
            main_result.append(
                _build_weekly_row_from_iso_plan(weekly_plan_data, real_data, "matched")
            )
        elif weekly_plan_data:
            plan_without_real.append(
                _build_weekly_row_from_iso_plan(weekly_plan_data, None, "plan_without_real")
            )
        elif real_data:
            row = _build_no_plan_row(real_data, ws, "weekly")
            row["week_end"] = (date.fromisoformat(ws) + timedelta(days=6)).isoformat()
            main_result.append(row)

    main_result.sort(key=lambda r: (r.get("week_start", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    plan_without_real.sort(key=lambda r: (r.get("week_start", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    return main_result, plan_without_real, len(real_map), distribution_debug


def _build_daily(
    conn,
    plan_by_key: Dict[Tuple, Dict],
    today: date,
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, List[Dict[str, Any]]]:
    """REAL-FIRST daily. Plan diario derivado directamente del mensual."""
    real_map = _load_real_daily(conn, country, city, business_slice, year, month)
    _log_projection_key_overlap("_build_daily", plan_by_key, real_map)
    daily_plan_map, _, distribution_debug = _build_iso_plan_maps(plan_by_key)

    main_result: List[Dict[str, Any]] = []
    plan_without_real: List[Dict[str, Any]] = []
    target_day_keys = {trip_date.isoformat() for trip_date in _get_days_for_scope(year, month, today)}

    all_slots = sorted(set(real_map.keys()) | set(daily_plan_map.keys()))
    for slot in all_slots:
        td, _, _, bsn_lower = slot
        if td not in target_day_keys:
            continue
        if business_slice and business_slice.strip().lower() != bsn_lower:
            continue

        real_data = real_map.get(slot)
        daily_plan_data = daily_plan_map.get(slot)

        if daily_plan_data and real_data:
            main_result.append(
                _build_daily_row_from_monthly_daily_plan(daily_plan_data, real_data, "matched")
            )
        elif daily_plan_data:
            plan_without_real.append(
                _build_daily_row_from_monthly_daily_plan(daily_plan_data, None, "plan_without_real")
            )
        elif real_data:
            row = _build_no_plan_row(real_data, td, "daily")
            main_result.append(row)

    main_result.sort(key=lambda r: (r.get("trip_date", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    plan_without_real.sort(key=lambda r: (r.get("trip_date", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    return main_result, plan_without_real, len(real_map), distribution_debug


# ── Real data loaders ──────────────────────────────────────────────────────

def _load_real_monthly(conn, country, city, business_slice, year, month):
    clauses = ["(NOT is_subfleet OR is_subfleet IS NULL)"]
    params: List[Any] = []

    _append_country_sql_filter(clauses, params, country)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    _append_business_slice_sql_filter(clauses, params, business_slice)
    if year:
        clauses.append("EXTRACT(YEAR FROM month) = %s")
        params.append(year)
    if month:
        clauses.append("EXTRACT(MONTH FROM month) = %s")
        params.append(month)

    sql = f"""
        SELECT month, country, city, business_slice_name,
               trips_completed AS real_trips,
               ABS(COALESCE(revenue_yego_final, revenue_yego_net)) AS real_revenue,
               COALESCE(revenue_yego_final, revenue_yego_net) AS real_revenue_raw,
               active_drivers AS real_active_drivers,
               trips_cancelled AS real_trips_cancelled,
               avg_ticket AS real_avg_ticket,
               commission_pct AS real_commission_pct,
               trips_per_driver AS real_trips_per_driver,
               NULL::numeric AS real_cancel_rate_pct
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
        key = _projection_join_key(
            mk,
            r.get("country"),
            r.get("city"),
            r.get("business_slice_name"),
        )
        row = dict(r)
        row["business_slice_name"] = canonicalize_business_slice_name(row.get("business_slice_name"))
        _merge_real_projection_rows(result, key, row)
    return result


def _load_real_weekly(conn, country, city, business_slice, year, month):
    clauses = ["(NOT is_subfleet OR is_subfleet IS NULL)"]
    params: List[Any] = []

    _append_country_sql_filter(clauses, params, country)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    _append_business_slice_sql_filter(clauses, params, business_slice)
    if year is not None and month is not None:
        first_day = date(year, month, 1)
        next_m = date(first_day.year + (first_day.month // 12), (first_day.month % 12) + 1, 1)
        last_day = next_m - timedelta(days=1)
        min_week_start = first_day - timedelta(days=first_day.weekday())
        max_week_start = last_day - timedelta(days=last_day.weekday())
        clauses.append("week_start >= %s AND week_start <= %s")
        params.append(min_week_start)
        params.append(max_week_start)
    elif year is not None:
        first_day = date(year, 1, 1)
        last_day = date(year, 12, 31)
        min_week_start = first_day - timedelta(days=first_day.weekday())
        max_week_start = last_day - timedelta(days=last_day.weekday())
        clauses.append("week_start >= %s AND week_start <= %s")
        params.append(min_week_start)
        params.append(max_week_start)
    elif month is not None:
        clauses.append("EXTRACT(MONTH FROM week_start) = %s")
        params.append(month)

    sql = f"""
        SELECT week_start, country, city, business_slice_name,
               trips_completed AS real_trips,
               ABS(COALESCE(revenue_yego_final, revenue_yego_net)) AS real_revenue,
               COALESCE(revenue_yego_final, revenue_yego_net) AS real_revenue_raw,
               active_drivers AS real_active_drivers,
               trips_cancelled AS real_trips_cancelled,
               avg_ticket AS real_avg_ticket,
               commission_pct AS real_commission_pct,
               trips_per_driver AS real_trips_per_driver,
               cancel_rate_pct AS real_cancel_rate_pct
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
        key = _projection_join_key(
            ws,
            r.get("country"),
            r.get("city"),
            r.get("business_slice_name"),
        )
        row = dict(r)
        row["business_slice_name"] = canonicalize_business_slice_name(row.get("business_slice_name"))
        _merge_real_projection_rows(result, key, row)
    return result


def _load_real_daily(conn, country, city, business_slice, year, month):
    clauses = ["(NOT is_subfleet OR is_subfleet IS NULL)"]
    params: List[Any] = []

    _append_country_sql_filter(clauses, params, country)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    _append_business_slice_sql_filter(clauses, params, business_slice)
    if year:
        clauses.append("EXTRACT(YEAR FROM trip_date) = %s")
        params.append(year)
    if month:
        clauses.append("EXTRACT(MONTH FROM trip_date) = %s")
        params.append(month)

    sql = f"""
        SELECT trip_date, country, city, business_slice_name,
               trips_completed AS real_trips,
               ABS(COALESCE(revenue_yego_final, revenue_yego_net)) AS real_revenue,
               COALESCE(revenue_yego_final, revenue_yego_net) AS real_revenue_raw,
               active_drivers AS real_active_drivers,
               trips_cancelled AS real_trips_cancelled,
               avg_ticket AS real_avg_ticket,
               commission_pct AS real_commission_pct,
               trips_per_driver AS real_trips_per_driver,
               cancel_rate_pct AS real_cancel_rate_pct
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
        key = _projection_join_key(
            td,
            r.get("country"),
            r.get("city"),
            r.get("business_slice_name"),
        )
        row = dict(r)
        row["business_slice_name"] = canonicalize_business_slice_name(row.get("business_slice_name"))
        _merge_real_projection_rows(result, key, row)
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
        # fleet_display_name = "" para mantener consistencia con _build_projection_row_monthly
        # y evitar que el frontend genere dos filas distintas para la misma tajada
        # (una con plan y fleet_display_name="" y otra sin plan con fleet_display_name=bsn)
        "fleet_display_name": "",
        "is_subfleet": False,
        "subfleet_name": "",
        "comparison_status": "missing_plan",
    }

    if grain == "monthly":
        row["month"] = period_key
    elif grain == "weekly":
        row["week_start"] = period_key
        week_start = date.fromisoformat(period_key)
        iso_ctx = _iso_week_context(week_start)
        row["week_end"] = iso_ctx["week_end"]
        row["iso_year"] = iso_ctx["iso_year"]
        row["iso_week"] = iso_ctx["iso_week"]
        row["week_label"] = iso_ctx["week_label"]
        row["week_range_label"] = iso_ctx["week_range_label"]
        row["week_full_label"] = iso_ctx["week_full_label"]
    else:
        row["trip_date"] = period_key
        trip_date = date.fromisoformat(period_key)
        iso_ctx = _iso_week_context(trip_date)
        row["week_start"] = iso_ctx["week_start"]
        row["week_end"] = iso_ctx["week_end"]
        row["iso_year"] = iso_ctx["iso_year"]
        row["iso_week"] = iso_ctx["iso_week"]
        row["week_label"] = iso_ctx["week_label"]
        row["week_range_label"] = iso_ctx["week_range_label"]
        row["week_full_label"] = iso_ctx["week_full_label"]

    for kpi in PROJECTABLE_KPIS:
        real_kpi = _real_column(kpi)
        actual = _safe_float(real_data.get(real_kpi))
        row[kpi] = actual
        row[f"{kpi}_projected_total"]    = None
        row[f"{kpi}_projected_expected"] = None
        row[f"{kpi}_attainment_pct"]     = None
        row[f"{kpi}_gap_to_expected"]    = None
        row[f"{kpi}_gap_pct"]            = None   # campo canónico nuevo
        row[f"{kpi}_gap_to_full"]        = None
        row[f"{kpi}_completion_pct"]     = None
        row[f"{kpi}_signal"]             = "no_data"
        row[f"{kpi}_curve_method"]       = None
        row[f"{kpi}_curve_confidence"]   = None
        row[f"{kpi}_fallback_level"]     = None
        row[f"{kpi}_expected_ratio"]     = None
        row[f"{kpi}_comparison_basis"]   = "unknown"  # campo canónico nuevo

    _copy_aux_real_metrics(row, real_data)
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

    if not year and not month:
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
        last = nxt - timedelta(days=1)
    elif year:
        first = date(year, 1, 1)
        last = date(year, 12, 31)
    else:
        first = date(today.year, today.month, 1)
        last = today

    days = []
    d = first
    while d <= last:
        days.append(d)
        d += timedelta(days=1)
    if year:
        return days
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


class JoinMismatchCause(str, Enum):
    COUNTRY_MISMATCH = "COUNTRY_MISMATCH"
    CITY_MISMATCH = "CITY_MISMATCH"
    BUSINESS_SLICE_MISMATCH = "BUSINESS_SLICE_MISMATCH"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    TRUE_NO_REAL = "TRUE_NO_REAL"
    TRUE_NO_PLAN = "TRUE_NO_PLAN"


def _analyze_join_mismatch(plan_key: Tuple[str, str, str, str], real_keys: Set[Tuple]) -> JoinMismatchCause:
    """Clasifica causa de mismatch comparando clave plan vs real keys disponibles."""
    period, country, city, bsn = plan_key
    for real_key in real_keys:
        r_period, r_country, r_city, r_bsn = real_key
        mismatches = []
        if r_period == period:
            if r_country != country:
                mismatches.append("COUNTRY_MISMATCH")
            if r_city != city:
                mismatches.append("CITY_MISMATCH")
            if r_bsn != bsn:
                mismatches.append("BUSINESS_SLICE_MISMATCH")
        else:
            mismatches.append("PERIOD_MISMATCH")
        if mismatches:
            return JoinMismatchCause(mismatches[0])
    if real_keys:
        return JoinMismatchCause.TRUE_NO_REAL
    return JoinMismatchCause.TRUE_NO_PLAN


def _compute_join_diagnostics(
    grain: str,
    plan_version: str,
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
    today: date,
) -> Dict[str, Any]:
    """Computa estadísticas de join Plan vs Real para diagnóstico."""
    year, month, _ = _normalize_projection_scope(grain, year, month)

    plan_rows = _load_plan_for_projection_scope(
        plan_version, grain, country, city, year, month, today
    )

    if not plan_rows:
        return {
            "grain": grain,
            "plan_version": plan_version,
            "filters": {
                "country": country,
                "city": city,
                "business_slice": business_slice,
                "year": year,
                "month": month,
            },
            "status": "no_plan",
            "plan_keys": 0,
            "real_keys": 0,
            "intersection": 0,
            "plan_only": 0,
            "real_only": 0,
            "intersection_rate_pct": 0.0,
            "by_cause": {},
        }

    geos: Set[Tuple[str, str]] = set()
    for p in plan_rows:
        co_rules = _country_to_rules_name(str(p["country"]))
        ci_raw = str(p["city"])
        geos.add((co_rules, ci_raw))

    idx = load_rules_index_for_geos(geos)
    map_rows = load_map_fallback_rows()
    plan_by_key = _resolve_and_index_plan(plan_rows, idx, map_rows)

    # FIX: Expandir claves del plan al grain apropiado para match con REAL
    # Monthly: period_key = YYYY-MM-01 (sin cambio)
    # Weekly: period_key = week_start ISO (YYYY-MM-DD del lunes)
    # Daily: period_key = date (YYYY-MM-DD)
    # Aplicar filtro business_slice PRIMERO
    bsn_filter = business_slice.strip().lower() if business_slice else None

    # Filtrar plan_by_key por business_slice ANTES de expandir
    if bsn_filter:
        plan_keys_filtered = {k: v for k, v in plan_by_key.items() if k[3] == bsn_filter}
    else:
        plan_keys_filtered = plan_by_key

    # FIX: Para weekly/daily, filtrar SOLO el mes solicitado antes de expandir
    # El plan_by_key puede contener múltiples meses (ej: enero-marzo)
    # Pero debemos expandir SOLO el mes solicitado (month param)
    if grain in ("weekly", "daily") and month is not None and year is not None:
        target_month_key = f"{year:04d}-{month:02d}-01"
        plan_keys_filtered = {k: v for k, v in plan_keys_filtered.items() if k[0] == target_month_key}
        logger.warning(
            "JOIN_MONTH_FILTER: grain=%s year=%s month=%s target=%s before=%d after=%d keys=%s",
            grain, year, month, target_month_key, len(plan_by_key), len(plan_keys_filtered),
            list(plan_keys_filtered.keys())[:3],
        )

    if grain == "weekly":
        plan_keys_expanded: Set[Tuple[str, str, str, str]] = set()
        for plan_key in plan_keys_filtered.keys():
            mk, co_norm, ci_norm, bsn_lower = plan_key
            # Generar todas las semanas ISO que intersectan este mes
            month_date = date.fromisoformat(mk)
            first, last, _ = _month_bounds(month_date)
            monday = first - timedelta(days=first.weekday())
            while monday <= last:
                week_start = monday.isoformat()
                plan_keys_expanded.add((week_start, co_norm, ci_norm, bsn_lower))
                monday += timedelta(days=7)
        pk = plan_keys_expanded
    elif grain == "daily":
        plan_keys_expanded = set()
        for plan_key in plan_keys_filtered.keys():
            mk, co_norm, ci_norm, bsn_lower = plan_key
            # Generar todos los días del mes
            month_date = date.fromisoformat(mk)
            for trip_date in _iter_month_dates(month_date):
                plan_keys_expanded.add((trip_date.isoformat(), co_norm, ci_norm, bsn_lower))
        pk = plan_keys_expanded
    else:
        # Monthly: usar claves filtradas (ya están en formato YYYY-MM-01)
        pk = set(plan_keys_filtered.keys())

    with get_db() as conn:
        if grain == "monthly":
            real_map = _load_real_monthly(conn, country, city, business_slice, year, month)
        elif grain == "weekly":
            real_map = _load_real_weekly(conn, country, city, business_slice, year, month)
        else:
            real_map = _load_real_daily(conn, country, city, business_slice, year, month)

    rk = set(real_map.keys())
    matched = pk & rk
    intersection_rate = round((len(matched) / len(pk) * 100.0), 1) if pk else 0.0

    plan_only_keys = pk - rk
    real_only_keys = rk - pk

    plan_only_cause_counts: Dict[str, int] = defaultdict(int)
    for pk_ in plan_only_keys:
        cause = _analyze_join_mismatch(pk_, rk)
        plan_only_cause_counts[cause.value] += 1

    real_only_cause_counts: Dict[str, int] = defaultdict(int)
    for rk_ in real_only_keys:
        cause = _analyze_join_mismatch(rk_, pk)
        real_only_cause_counts[cause.value] += 1

    by_cause = {
        "plan_only": dict(plan_only_cause_counts),
        "real_only": dict(real_only_cause_counts),
    }

    threshold_85 = intersection_rate >= 85.0
    threshold_92 = intersection_rate >= 92.0

    # DEBUG: Loguear samples de claves para diagnóstico de PERIOD_MISMATCH
    if grain in ("weekly", "daily"):
        logger.warning(
            "JOIN_DEBUG grain=%s bsn_filter=%s: plan_sample=%s real_sample=%s",
            grain,
            bsn_filter,
            [list(k) for k in sorted(pk)[:3]],
            [list(k) for k in sorted(rk)[:3]],
        )

    return {
        "grain": grain,
        "plan_version": plan_version,
        "filters": {
            "country": country,
            "city": city,
            "business_slice": business_slice,
            "year": year,
            "month": month,
        },
        "status": "computed",
        "plan_keys": len(pk),
        "real_keys": len(rk),
        "intersection": len(matched),
        "plan_only": len(plan_only_keys),
        "real_only": len(real_only_keys),
        "intersection_rate_pct": intersection_rate,
        "go_threshold_85": threshold_85,
        "go_threshold_92": threshold_92,
        "by_cause": by_cause,
        "plan_only_sample": [list(k) for k in sorted(plan_only_keys)[:12]],
        "real_only_sample": [list(k) for k in sorted(real_only_keys)[:12]],
    }
