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
import time
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from psycopg2.extras import RealDictCursor

from app.config.control_loop_lob_mapping import resolve_excel_line_to_canonical
from app.contracts.data_contract import remove_accents
from app.db.connection import get_db
from app.services.business_slice_service import FACT_DAILY, FACT_MONTHLY, FACT_WEEKLY
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
    compute_daily_expected_ratio,
    compute_expected_ratio,
    compute_weekly_expected_ratio,
)

logger = logging.getLogger(__name__)


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


def _slice_month_plan_key(r: Dict[str, Any]) -> Optional[Tuple]:
    mk = r.get("month")
    if not mk:
        return None
    co = (r.get("country") or "").strip().lower()
    ci = (r.get("city") or "").strip().lower()
    bsn = (r.get("business_slice_name") or "").strip().lower()
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

        for kpi in PROJECTABLE_KPIS:
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

        for kpi in PROJECTABLE_KPIS:
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

    conserv_ok = 0
    conserv_fail = 0
    for key, plan in plan_by_key.items():
        grp = [r for r in rows if _slice_month_plan_key(r) == key]
        if len(grp) < 3:
            continue
        plan_total = _safe_float(plan.get("projected_trips"))
        if plan_total is None:
            continue
        s = sum((_safe_float(r.get("trips_completed_projected_total")) or 0.0) for r in grp)
        if _conservation_tolerance_ok(abs(plan_total - s), plan_total):
            conserv_ok += 1
        else:
            conserv_fail += 1

    checks.append(
        {
            "name": "conservation_trips_sample",
            "groups_checked_ge_3_weeks": conserv_ok + conserv_fail,
            "passed_slices": conserv_ok,
            "failed_slices": conserv_fail,
            "passed": conserv_fail == 0,
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
                        (a.get("city") or "").strip().lower(),
                        (a.get("business_slice_name") or "").strip().lower(),
                    )
                )
        if chk.get("name") == "volatility_daily_plan_vs_avg":
            for a in chk.get("anomalies") or []:
                daily_vol_keys.add(
                    (
                        a.get("trip_date"),
                        (a.get("city") or "").strip().lower(),
                        (a.get("business_slice_name") or "").strip().lower(),
                    )
                )

    for r in display_rows:
        r["projection_confidence"] = _compute_projection_confidence(r)
        if grain == "weekly":
            key = (
                r.get("week_start"),
                (r.get("city") or "").strip().lower(),
                (r.get("business_slice_name") or "").strip().lower(),
            )
            r["projection_anomaly"] = key in weekly_vol_keys
        elif grain == "daily":
            key = (
                r.get("trip_date"),
                (r.get("city") or "").strip().lower(),
                (r.get("business_slice_name") or "").strip().lower(),
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
    _t0 = time.perf_counter()
    today = date.today()

    logger.info(
        "get_omniview_projection START grain=%s plan=%s country=%s city=%s year=%s month=%s",
        grain, plan_version, country, city, year, month,
    )

    _t1 = time.perf_counter()
    plan_rows = _load_plan(plan_version, country, city, year, month)
    logger.info("get_omniview_projection load_plan=%.2fs rows=%d", time.perf_counter() - _t1, len(plan_rows))

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
                "plan_derivation": {
                    "monthly_plan_only": True,
                    "response_grain": grain,
                    "weekly_daily_from_monthly": grain in ("weekly", "daily"),
                    "derivation_source": "ops.v_plan_projection_control_loop",
                    "smoothing_applied": True,
                    "smoothing_alpha_week": 0.7,
                    "smoothing_alpha_day": 0.7,
                    "conservation_enforced": False,
                    "year_end_weeks_included": [],
                    "fallback_level_summary": {},
                },
                "conservation": {},
                "qa_checks": {},
                "message": "No hay proyección cargada para esta versión / filtros.",
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
    with get_db() as conn:
        if grain == "monthly":
            result_rows, plan_without_real, real_rows = _build_monthly(
                conn, resolved_plan_by_key, today, country, city, business_slice, year, month
            )
        elif grain == "weekly":
            result_rows, plan_without_real, real_rows = _build_weekly(
                conn, resolved_plan_by_key, today, country, city, business_slice, year, month
            )
        else:
            result_rows, plan_without_real, real_rows = _build_daily(
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
        conservation_meta = _reconcile_weekly_conservation(display_rows, resolved_plan_by_key)
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

    try:
        from app.settings import settings as _settings_proj

        smoothing_alpha_week = float(
            getattr(_settings_proj, "PROJECTION_SMOOTHING_ALPHA_WEEK", 0.7)
        )
        smoothing_alpha_day = float(
            getattr(_settings_proj, "PROJECTION_SMOOTHING_ALPHA_DAY", 0.7)
        )
    except Exception:
        smoothing_alpha_week = 0.7
        smoothing_alpha_day = 0.7

    last_loaded = None
    for p in plan_rows:
        la = p.get("last_loaded_at")
        if la:
            last_loaded = str(la)
            break

    return {
        "granularity": grain,
        "plan_version": plan_version,
        "data": display_rows,
        "meta": {
            "plan_version": plan_version,
            "plan_loaded_at": last_loaded,
            "plan_derivation": {
                "monthly_plan_only": True,
                "response_grain": grain,
                "weekly_daily_from_monthly": grain in ("weekly", "daily"),
                "derivation_source": "ops.v_plan_projection_control_loop",
                "smoothing_applied": True,
                "smoothing_alpha_week": smoothing_alpha_week,
                "smoothing_alpha_day": smoothing_alpha_day,
                "conservation_enforced": grain in ("weekly", "daily"),
                "year_end_weeks_included": year_end_weeks_included,
                "fallback_level_summary": fallback_level_summary,
            },
            "curve_summary": curve_summary,
            "conservation": conservation_meta,
            "qa_checks": qa_checks_payload,
            "kpis_with_projection": list(PROJECTABLE_KPIS),
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
            # ── Estadísticas de reconciliación ─────────────────────────────────
            "reconciliation": {
                "matched":           matched_count,
                "missing_plan":      missing_plan_ct,
                "plan_without_real": len(plan_without_real),
                "unresolved_plan":   len(unresolved_list),
                "total_real_rows":   len(result_rows),
                "total_display_rows": len(display_rows),
            },
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

        mk = _month_key(p["period_date"])
        # Clave canónica: usa formato FACT_MONTHLY para matchear real_map correctamente
        key = (mk, co_fact, ci_fact, bsn.strip().lower())

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


def _fill_weekly_row_from_monthly_plan(
    conn,
    plan: Dict[str, Any],
    plan_month: date,
    week_start: date,
    co_norm: str,
    real_data: Optional[Dict[str, Any]],
    comparison_status: str,
    _curve_cache: Dict,
    _dist_cache: Dict,
    today: date,
) -> Dict[str, Any]:
    """Deriva KPIs semanales desde el plan mensual (seasonality_curve_engine)."""
    bsn = plan["business_slice_name"]
    co_full = plan["country"]
    ci = plan["city"]
    pm = plan_month.replace(day=1)
    plan_month_key = _month_key(pm)

    row: Dict[str, Any] = {
        "country": co_full,
        "city": ci,
        "business_slice_name": bsn,
        "fleet_display_name": "",
        "is_subfleet": False,
        "subfleet_name": "",
        "week_start": week_start.isoformat(),
        "month": plan_month_key,
        "comparison_status": comparison_status,
    }

    week_end = week_start + timedelta(days=6)
    cutoff_date = min(today, week_end)
    is_full_week = cutoff_date >= week_end
    week_comparison_basis = resolve_comparison_basis(is_full_week, "weekly")

    for kpi in PROJECTABLE_KPIS:
        plan_total = _safe_float(plan.get(_plan_column(kpi)))
        curve = compute_weekly_expected_ratio(
            _to_full_country(co_norm), ci, bsn, kpi,
            week_start, cutoff_date, pm, conn=conn,
            _cache=_curve_cache, _dist_cache=_dist_cache,
        )
        week_expected = round(plan_total * curve["expected_ratio_to_date"], 2) if plan_total is not None else None
        week_plan_total = round(plan_total * curve.get("week_share_of_month", 0), 2) if plan_total is not None else None
        actual = _safe_float(real_data.get(_real_column(kpi))) if real_data else None

        canon = compute_canonical_metrics(actual, week_expected, week_plan_total, week_comparison_basis)

        row[kpi] = actual
        row[f"{kpi}_projected_total"]    = week_plan_total
        row[f"{kpi}_projected_expected"] = week_expected
        row[f"{kpi}_attainment_pct"]     = canon["avance_pct"]
        row[f"{kpi}_gap_to_expected"]    = canon["gap_abs"]
        row[f"{kpi}_gap_pct"]            = canon["gap_pct"]
        row[f"{kpi}_gap_to_full"]        = round(actual - week_plan_total, 2) if actual is not None and week_plan_total is not None else None
        row[f"{kpi}_completion_pct"]     = round((actual / week_plan_total) * 100.0, 2) if actual is not None and week_plan_total and week_plan_total > 0 else None
        row[f"{kpi}_signal"]             = resolve_signal(canon["avance_pct"], actual)
        row[f"{kpi}_curve_method"]       = curve.get("curve_method", "linear_fallback")
        row[f"{kpi}_curve_confidence"]   = curve.get("confidence", "fallback")
        row[f"{kpi}_fallback_level"]     = curve.get("fallback_level", 5)
        row[f"{kpi}_expected_ratio"]     = curve.get("expected_ratio_to_date", 0)
        row[f"{kpi}_comparison_basis"]   = week_comparison_basis

    return row


def _fill_daily_row_from_monthly_plan(
    conn,
    plan: Dict[str, Any],
    plan_month: date,
    trip_date: date,
    co_norm: str,
    real_data: Optional[Dict[str, Any]],
    comparison_status: str,
    _curve_cache: Dict,
    _dist_cache: Dict,
) -> Dict[str, Any]:
    """Deriva KPIs diarios desde el plan mensual."""
    bsn = plan["business_slice_name"]
    co_full = plan["country"]
    ci = plan["city"]
    pm = plan_month.replace(day=1)
    plan_month_key = _month_key(pm)

    row: Dict[str, Any] = {
        "country": co_full,
        "city": ci,
        "business_slice_name": bsn,
        "fleet_display_name": "",
        "is_subfleet": False,
        "subfleet_name": "",
        "trip_date": trip_date.isoformat(),
        "month": plan_month_key,
        "comparison_status": comparison_status,
    }

    for kpi in PROJECTABLE_KPIS:
        plan_total = _safe_float(plan.get(_plan_column(kpi)))
        kpi_curve = compute_daily_expected_ratio(
            _to_full_country(co_norm), ci, bsn, kpi, trip_date, pm, conn=conn,
            _cache=_curve_cache, _dist_cache=_dist_cache,
        )
        daily_expected = round(plan_total * kpi_curve["expected_ratio_to_date"], 2) if plan_total is not None else None
        actual = _safe_float(real_data.get(_real_column(kpi))) if real_data else None

        canon = compute_canonical_metrics(actual, daily_expected, daily_expected, "full_day")

        row[kpi] = actual
        row[f"{kpi}_projected_total"]    = daily_expected
        row[f"{kpi}_projected_expected"] = daily_expected
        row[f"{kpi}_attainment_pct"]     = canon["avance_pct"]
        row[f"{kpi}_gap_to_expected"]    = canon["gap_abs"]
        row[f"{kpi}_gap_pct"]            = canon["gap_pct"]
        row[f"{kpi}_gap_to_full"]        = canon["gap_abs"]
        row[f"{kpi}_completion_pct"]     = canon["avance_pct"]
        row[f"{kpi}_signal"]             = resolve_signal(canon["avance_pct"], actual)
        row[f"{kpi}_curve_method"]       = kpi_curve.get("curve_method", "linear_fallback")
        row[f"{kpi}_curve_confidence"]   = kpi_curve.get("confidence", "fallback")
        row[f"{kpi}_fallback_level"]     = kpi_curve.get("fallback_level", 5)
        row[f"{kpi}_expected_ratio"]     = kpi_curve.get("expected_ratio_to_date", 0)
        row[f"{kpi}_comparison_basis"]   = "full_day"

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
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """REAL-FIRST weekly. Plan semanal siempre derivado del mensual cargado (no hay plan W en BD)."""
    real_map = _load_real_weekly(conn, country, city, business_slice, year, month)
    _curve_cache: Dict = {}
    _dist_cache:  Dict = {}

    main_result: List[Dict[str, Any]] = []
    seen_slots: Set[Tuple[str, str, str, str]] = set()

    target_weeks = _get_weeks_for_scope(year, month, today)
    scope_m = _scope_month_start(year, month, today)
    scope_month_key = _month_key(scope_m) if scope_m else None

    for week_start in target_weeks:
        if scope_m and not _week_intersects_month(week_start, scope_m):
            continue
        plan_month_date = scope_m or date(week_start.year, week_start.month, 1)
        plan_month_key = _month_key(plan_month_date.replace(day=1))

        for real_key, real_data in real_map.items():
            ws, co_norm, ci_norm, bsn_lower = real_key
            if ws != week_start.isoformat():
                continue
            if business_slice and business_slice.strip().lower() != bsn_lower:
                continue

            slot = (ws, co_norm, ci_norm, bsn_lower)
            plan_lookup_key = (plan_month_key, co_norm, ci_norm, bsn_lower)
            plan = plan_by_key.get(plan_lookup_key)

            if plan:
                seen_slots.add(slot)
                row = _fill_weekly_row_from_monthly_plan(
                    conn, plan, plan_month_date, week_start, co_norm, real_data, "matched",
                    _curve_cache, _dist_cache, today,
                )
            else:
                seen_slots.add(slot)
                row = _build_no_plan_row(real_data, week_start.isoformat(), "weekly")
                row["month"] = plan_month_key

            main_result.append(row)

    plan_without_real: List[Dict[str, Any]] = []
    for plan_key, plan in plan_by_key.items():
        mk, co_norm, ci_norm, bsn_lower = plan_key[0], plan_key[1], plan_key[2], plan_key[3]
        if scope_month_key and mk != scope_month_key:
            continue
        plan_month = date.fromisoformat(mk)

        for week_start in target_weeks:
            if not _week_intersects_month(week_start, plan_month):
                continue
            slot = (week_start.isoformat(), co_norm, ci_norm, bsn_lower)
            if slot in seen_slots:
                continue
            row = _fill_weekly_row_from_monthly_plan(
                conn, plan, plan_month, week_start, co_norm, None, "plan_without_real",
                _curve_cache, _dist_cache, today,
            )
            plan_without_real.append(row)

    main_result.sort(key=lambda r: (r.get("week_start", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    plan_without_real.sort(key=lambda r: (r.get("week_start", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    return main_result, plan_without_real, len(real_map)


def _build_daily(
    conn,
    plan_by_key: Dict[Tuple, Dict],
    today: date,
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """REAL-FIRST daily. Plan diario siempre derivado del mensual (no hay plan D en BD)."""
    real_map = _load_real_daily(conn, country, city, business_slice, year, month)
    _curve_cache: Dict = {}
    _dist_cache:  Dict = {}

    main_result: List[Dict[str, Any]] = []
    seen_slots: Set[Tuple[str, str, str, str]] = set()

    target_days = _get_days_for_scope(year, month, today)
    scope_m = _scope_month_start(year, month, today)
    scope_month_key = _month_key(scope_m) if scope_m else None

    for trip_date in target_days:
        day_month = date(trip_date.year, trip_date.month, 1)
        if scope_m and day_month != scope_m:
            continue
        plan_month_key = _month_key(day_month)

        for real_key, real_data in real_map.items():
            td, co_norm, ci_norm, bsn_lower = real_key
            if td != trip_date.isoformat():
                continue
            if business_slice and business_slice.strip().lower() != bsn_lower:
                continue

            slot = (td, co_norm, ci_norm, bsn_lower)
            plan_lookup_key = (plan_month_key, co_norm, ci_norm, bsn_lower)
            plan = plan_by_key.get(plan_lookup_key)

            if plan:
                seen_slots.add(slot)
                row = _fill_daily_row_from_monthly_plan(
                    conn, plan, day_month, trip_date, co_norm, real_data, "matched",
                    _curve_cache, _dist_cache,
                )
            else:
                seen_slots.add(slot)
                row = _build_no_plan_row(real_data, trip_date.isoformat(), "daily")
                row["month"] = plan_month_key

            main_result.append(row)

    plan_without_real: List[Dict[str, Any]] = []
    for plan_key, plan in plan_by_key.items():
        mk, co_norm, ci_norm, bsn_lower = plan_key[0], plan_key[1], plan_key[2], plan_key[3]
        if scope_month_key and mk != scope_month_key:
            continue
        plan_month = date.fromisoformat(mk)

        for trip_date in target_days:
            if date(trip_date.year, trip_date.month, 1) != plan_month:
                continue
            slot = (trip_date.isoformat(), co_norm, ci_norm, bsn_lower)
            if slot in seen_slots:
                continue
            row = _fill_daily_row_from_monthly_plan(
                conn, plan, plan_month, trip_date, co_norm, None, "plan_without_real",
                _curve_cache, _dist_cache,
            )
            plan_without_real.append(row)

    main_result.sort(key=lambda r: (r.get("trip_date", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    plan_without_real.sort(key=lambda r: (r.get("trip_date", ""), r.get("country", ""), r.get("city", ""), r.get("business_slice_name", "")))
    return main_result, plan_without_real, len(real_map)


# ── Real data loaders ──────────────────────────────────────────────────────

def _load_real_monthly(conn, country, city, business_slice, year, month):
    clauses = ["(NOT is_subfleet OR is_subfleet IS NULL)"]
    params: List[Any] = []

    _append_country_sql_filter(clauses, params, country)
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

    _append_country_sql_filter(clauses, params, country)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    if business_slice:
        clauses.append("lower(trim(business_slice_name)) = lower(trim(%s))")
        params.append(business_slice.strip().lower())
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
        clauses.append("EXTRACT(YEAR FROM week_start) = %s")
        params.append(year)
    elif month is not None:
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

    _append_country_sql_filter(clauses, params, country)
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
    else:
        row["trip_date"] = period_key

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
    # Mes explícito (year+month): todos los días del mes hasta hoy — suma diaria ≈ plan mensual.
    if year and month:
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
