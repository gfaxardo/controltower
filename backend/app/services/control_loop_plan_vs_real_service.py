"""Comparación Plan vs Real — Control Loop alineado a tajadas Omniview (business_slice_name).

Real desde ops.real_business_slice_month_fact (misma fact table que Omniview Matrix).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.control_loop_business_slice_resolve import (
    load_map_fallback_rows,
    load_rules_index_for_geos,
    resolve_to_business_slice_name,
)

from app.services.serving_guardrails import (
    QueryMode as _QM,
    ServingPolicy,
    SourceType as _ST,
    context_from_policy,
    execute_db_gated_query,
    register_policy,
)

logger = logging.getLogger(__name__)

_SERVING_POLICY = ServingPolicy(
    feature_name="Control Loop Plan vs Real",
    query_mode=_QM.SERVING,
    preferred_source="ops.real_business_slice_month_fact",
    preferred_source_type=_ST.FACT,
    forbidden_sources=[
        "ops.v_real_monthly_control_loop_from_tajadas",
        "ops.v_real_trips_business_slice_resolved",
        "ops.v_real_trips_enriched_base",
    ],
    strict_mode=True,
    require_preferred_source_match=True,
)
register_policy(_SERVING_POLICY)

REAL_DRIVERS_SEMANTICS = (
    "real_active_drivers desde ops.real_business_slice_month_fact "
    "(misma fact table que Omniview Matrix, materializada por backfill)."
)

_COUNTRY_NORM = {
    "peru": "pe", "perú": "pe", "pe": "pe",
    "colombia": "co", "col": "co", "co": "co",
}


def _norm_country_fact(raw: str) -> str:
    return _COUNTRY_NORM.get((raw or "").strip().lower(), (raw or "").strip().lower())


def _month_range(period_from: Optional[str], period_to: Optional[str]) -> Tuple[Optional[date], Optional[date]]:
    def _p(s: Optional[str]) -> Optional[date]:
        if not s or len(s) < 7:
            return None
        y, m = int(s[:4]), int(s[5:7])
        return date(y, m, 1)

    return _p(period_from), _p(period_to)


def _period_key(pd: Any) -> str:
    if hasattr(pd, "strftime"):
        return pd.strftime("%Y-%m")
    return str(pd)[:7]


def _load_real_from_fact(
    country: Optional[str],
    city: Optional[str],
    d_from: Optional[date],
    d_to: Optional[date],
) -> List[Dict[str, Any]]:
    """Lee real mensual de la fact table materializada (rápida, <3s)."""
    params: List[Any] = []
    clauses = ["(NOT is_subfleet OR is_subfleet IS NULL)"]
    if country:
        cn = _norm_country_fact(country)
        full = {"pe": "peru", "co": "colombia"}.get(cn, cn)
        clauses.append("lower(trim(country)) = lower(trim(%s))")
        params.append(full)
    if city:
        clauses.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city.strip().lower())
    if d_from:
        clauses.append("month >= %s::date")
        params.append(d_from)
    if d_to:
        clauses.append("month <= %s::date")
        params.append(d_to)

    sql = f"""
        SELECT month, country, city, business_slice_name,
               trips_completed  AS real_trips,
               revenue_yego_final AS real_revenue,
               active_drivers  AS real_active_drivers
        FROM ops.real_business_slice_month_fact
        WHERE {" AND ".join(clauses)}
    """
    with get_db() as conn:
        _ctx = context_from_policy(_SERVING_POLICY, source_name="ops.real_business_slice_month_fact")
        rows = execute_db_gated_query(
            _ctx, _SERVING_POLICY, conn, sql, params,
            source_name="ops.real_business_slice_month_fact",
            source_type="fact",
            cursor_factory=RealDictCursor,
        )

    for r in rows:
        r["country_norm"] = _norm_country_fact(r["country"])
        r["city_norm"] = (r["city"] or "").strip().lower()
        co = r["country_norm"]
        r["currency"] = "PEN" if co == "pe" else "COP" if co == "co" else None
        r["source_rule_type"] = "real_business_slice_month_fact"
        r["source_match_detail"] = "fact_table"
    return rows


def get_control_loop_plan_vs_real(
    plan_version: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    linea_negocio: Optional[str] = None,
    period_from: Optional[str] = None,
    period_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Plan (staging pivot) vs Real desde ops.real_business_slice_month_fact.
    Resolución plan → business_slice_name vía reglas activas por ciudad.
    """
    d_from, d_to = _month_range(period_from, period_to)

    params: List[Any] = [plan_version]
    where_plan = ["plan_version = %s"]
    if country:
        where_plan.append("lower(trim(country)) = lower(trim(%s))")
        params.append(country)
    if city:
        where_plan.append("lower(trim(city)) = lower(trim(%s))")
        params.append(city)
    if d_from:
        where_plan.append("period_date >= %s::date")
        params.append(d_from)
    if d_to:
        where_plan.append("period_date <= %s::date")
        params.append(d_to)

    plan_sql = f"""
        SELECT plan_version, period_date, country, city, linea_negocio_canonica,
               linea_negocio_excel,
               projected_trips, projected_revenue, projected_active_drivers
        FROM ops.v_plan_projection_control_loop
        WHERE {" AND ".join(where_plan)}
    """

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(plan_sql, params)
        plans = [dict(r) for r in cur.fetchall()]
        cur.close()

    if linea_negocio:
        lf = linea_negocio.strip().lower()
        plans = [
            p
            for p in plans
            if (p.get("linea_negocio_canonica") or "").strip().lower() == lf
            or (p.get("linea_negocio_excel") or "").strip().lower() == lf
        ]

    geos: Set[Tuple[str, str]] = set()
    for p in plans:
        geos.add((str(p["country"]), str(p["city"])))

    idx = load_rules_index_for_geos(geos)
    map_rows = load_map_fallback_rows()

    reals = _load_real_from_fact(country, city, d_from, d_to)

    def rk(m, cn, cin, bsl: str) -> Tuple[str, str, str, str]:
        ms = m.strftime("%Y-%m") if hasattr(m, "strftime") else str(m)[:7]
        return (ms, str(cn).lower().strip(), str(cin).lower().strip(), bsl.strip().lower())

    real_map: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for r in reals:
        real_map[rk(r["month"], r["country_norm"], r["city_norm"], r["business_slice_name"])] = r

    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str, str]] = set()

    for p in plans:
        pd = p["period_date"]
        co, ci = str(p["country"]), str(p["city"])
        lob_c = str(p.get("linea_negocio_canonica") or "")
        lob_x = str(p.get("linea_negocio_excel") or "")
        bsn, rsrc = resolve_to_business_slice_name(idx, map_rows, co, ci, lob_x, lob_c)
        if bsn:
            kk = rk(pd, co, ci, bsn)
        else:
            kk = (_period_key(pd), co.lower().strip(), ci.lower().strip(), f"__unresolved__{lob_c}")

        seen.add(kk)
        real_row = real_map.get(rk(pd, co, ci, bsn)) if bsn else None
        out.append(
            _build_row(
                p,
                real_row,
                business_slice_resolved=bsn,
                resolution_source=rsrc,
                unresolved=(bsn is None),
            )
        )

    ln_filter = (linea_negocio or "").strip().lower()
    for key, rv in real_map.items():
        if key in seen:
            continue
        if ln_filter:
            if ln_filter not in (rv.get("business_slice_name") or "").lower():
                continue
        if country and str(rv.get("country_norm", "")).lower() != country.lower().strip():
            continue
        if city and str(rv.get("city_norm", "")).lower() != city.lower().strip():
            continue
        m = rv["month"]
        fake = {
            "period_date": m,
            "country": rv.get("country") or rv.get("country_norm"),
            "city": rv.get("city") or rv.get("city_norm"),
            "linea_negocio_canonica": rv.get("business_slice_name"),
            "linea_negocio_excel": rv.get("business_slice_name"),
            "projected_trips": None,
            "projected_revenue": None,
            "projected_active_drivers": None,
        }
        out.append(
            _build_row(
                fake,
                rv,
                business_slice_resolved=str(rv.get("business_slice_name") or ""),
                resolution_source="real_only",
                unresolved=False,
            )
        )

    out.sort(
        key=lambda x: (
            x["period"],
            x["country"],
            x["city"],
            x.get("business_slice_name") or x["linea_negocio"],
        )
    )
    logger.info("Control Loop plan vs real (fact table): %s filas", len(out))
    return out


def list_control_loop_plan_versions() -> List[str]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT plan_version
            FROM staging.control_loop_plan_metric_long
            ORDER BY plan_version DESC
            """
        )
        rows = [r[0] for r in cur.fetchall()]
        cur.close()
    return rows


def _pct_delta(real: Optional[float], plan: Optional[float]) -> Optional[float]:
    if real is None or plan is None:
        return None
    if plan == 0:
        return None
    return round((real - plan) / plan * 100.0, 4)


def _pct_gap(gap: Optional[float], plan: Optional[float]) -> Optional[float]:
    if gap is None or plan is None:
        return None
    if plan == 0:
        return None
    return round(gap / plan * 100.0, 4)


def _status(
    pt: Optional[float],
    pr: Optional[float],
    pdrv: Optional[float],
    rt: Optional[float],
    rr: Optional[float],
    rd: Optional[float],
    unresolved: bool,
) -> str:
    has_plan = any(v is not None for v in (pt, pr, pdrv))
    has_real = any(v is not None for v in (rt, rr, rd))
    if unresolved and has_plan:
        return "NOT_MAPPED"
    if has_plan and has_real:
        return "COMPARABLE"
    if has_plan and not has_real:
        return "NO_REAL_YET"
    if has_real and not has_plan:
        return "NO_PLAN"
    return "NO_PLAN"


def _build_row(
    plan_row: Dict[str, Any],
    real_row: Optional[Dict[str, Any]],
    business_slice_resolved: Optional[str],
    resolution_source: str,
    unresolved: bool,
) -> Dict[str, Any]:
    pd = plan_row["period_date"]
    period = _period_key(pd)
    lob = str(plan_row.get("linea_negocio_canonica") or "")
    pt = float(plan_row["projected_trips"]) if plan_row.get("projected_trips") is not None else None
    pr = float(plan_row["projected_revenue"]) if plan_row.get("projected_revenue") is not None else None
    pdrv = float(plan_row["projected_active_drivers"]) if plan_row.get("projected_active_drivers") is not None else None

    rt = float(real_row["real_trips"]) if real_row and real_row.get("real_trips") is not None else None
    rr = float(real_row["real_revenue"]) if real_row and real_row.get("real_revenue") is not None else None
    rd = float(real_row["real_active_drivers"]) if real_row and real_row.get("real_active_drivers") is not None else None

    cty = str(plan_row["country"]).lower().strip()
    currency = "PEN" if cty == "pe" else "COP" if cty == "co" else (real_row or {}).get("currency")

    gap_t = (pt - rt) if pt is not None and rt is not None else None
    gap_r = (pr - rr) if pr is not None and rr is not None else None
    gap_d = (pdrv - rd) if pdrv is not None and rd is not None else None

    return {
        "period": period,
        "country": plan_row["country"],
        "city": plan_row["city"],
        "linea_negocio": lob,
        "linea_negocio_excel": plan_row.get("linea_negocio_excel"),
        "business_slice_name": business_slice_resolved,
        "resolution_source": resolution_source,
        "currency": currency,
        "projected_trips": pt,
        "real_trips": rt,
        "delta_trips": (rt - pt) if rt is not None and pt is not None else None,
        "delta_trips_pct": _pct_delta(rt, pt),
        "gap_trips": gap_t,
        "gap_trips_pct": _pct_gap(gap_t, pt),
        "projected_revenue": pr,
        "real_revenue": rr,
        "delta_revenue": (rr - pr) if rr is not None and pr is not None else None,
        "delta_revenue_pct": _pct_delta(rr, pr),
        "gap_revenue": gap_r,
        "gap_revenue_pct": _pct_gap(gap_r, pr),
        "projected_active_drivers": pdrv,
        "real_active_drivers": rd,
        "delta_active_drivers": (rd - pdrv) if rd is not None and pdrv is not None else None,
        "delta_active_drivers_pct": _pct_delta(rd, pdrv),
        "gap_active_drivers": gap_d,
        "gap_active_drivers_pct": _pct_gap(gap_d, pdrv),
        "comparison_status": _status(pt, pr, pdrv, rt, rr, rd, unresolved),
        "real_source_view": "ops.real_business_slice_month_fact",
        "real_active_drivers_semantics": REAL_DRIVERS_SEMANTICS,
    }
