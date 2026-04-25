#!/usr/bin/env python3
"""
Auditoría E2E del pipeline REAL de Omniview Matrix / Vs Proyección.

Valida:
  A. Base directa desde ops.v_real_trips_business_slice_resolved (completed only)
  B. Fact mensual usado por Omniview
  C. Fact semanal usado por Omniview
  D. Fact diario usado por Omniview
  E. Servicio final get_omniview_projection()
  F. Comparación por country/city/lob/period
  G. Filas donde base tiene ejecución pero API devuelve 0/null
  H. Filas donde plan existe pero no matchea por claves
  I. Divergencias de normalización país/ciudad/tajada

Uso:
  cd backend
  python scripts/audit_omniview_real_pipeline.py --year 2026
  python scripts/audit_omniview_real_pipeline.py --year 2026 --country peru --business-slice Delivery
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Tuple

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from psycopg2.extras import RealDictCursor  # noqa: E402

from app.db.connection import get_db_audit  # noqa: E402
from app.services.control_loop_business_slice_resolve import (  # noqa: E402
    load_map_fallback_rows,
    load_rules_index_for_geos,
)
from app.services.projection_expected_progress_service import (  # noqa: E402
    _country_to_rules_name,
    _load_plan,
    _projection_join_key,
    _resolve_and_index_plan,
    get_omniview_projection,
)


GRAINS = ("monthly", "weekly", "daily")
BASE_SOURCE_USED: Dict[str, str] = {}


@dataclass(frozen=True)
class AuditKey:
    grain: str
    period: str
    country: str
    city: str
    lob: str


def _norm_country(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("peru", "perú", "pe"):
        return "peru"
    if s in ("colombia", "col", "co"):
        return "colombia"
    return s


def _norm_city(raw: Any) -> str:
    from app.contracts.data_contract import remove_accents

    return remove_accents(str(raw or "").strip()).lower()


def _norm_slice(raw: Any) -> str:
    from app.contracts.data_contract import remove_accents

    return remove_accents(str(raw or "").strip()).lower()


def _api_key(grain: str, row: Dict[str, Any]) -> Optional[AuditKey]:
    period = (
        row.get("month")
        if grain == "monthly"
        else row.get("week_start")
        if grain == "weekly"
        else row.get("trip_date")
    )
    if not period:
        return None
    return AuditKey(
        grain=grain,
        period=str(period),
        country=_norm_country(row.get("country")),
        city=_norm_city(row.get("city")),
        lob=_norm_slice(row.get("business_slice_name")),
    )


def _real_metrics_from_row(row: Dict[str, Any]) -> Dict[str, Optional[float]]:
    return {
        "trips": _num(row.get("trips_completed") or row.get("real_trips")),
        "drivers": _num(row.get("active_drivers") or row.get("real_active_drivers")),
        "revenue": _num(row.get("revenue_yego_net") or row.get("real_revenue")),
        "avg_ticket": _num(row.get("avg_ticket")),
        "tpd": _num(row.get("trips_per_driver")),
    }


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _latest_plan_version() -> Optional[str]:
    sql = """
        SELECT plan_version
        FROM (
            SELECT plan_version, MAX(last_loaded_at) AS loaded_at
            FROM ops.v_plan_projection_control_loop
            GROUP BY 1
            UNION ALL
            SELECT plan_version, MAX(created_at) AS loaded_at
            FROM ops.plan_trips_monthly
            GROUP BY 1
        ) t
        ORDER BY loaded_at DESC NULLS LAST, plan_version DESC
        LIMIT 1
    """
    with get_db_audit() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql)
        row = cur.fetchone()
        cur.close()
    return row["plan_version"] if row else None


def _resolved_sql(grain: str, source_view: str = "ops.v_real_trips_business_slice_resolved") -> str:
    if grain == "monthly":
        period_expr = "r.trip_month::date"
    elif grain == "weekly":
        period_expr = "date_trunc('week', r.trip_date)::date"
    else:
        period_expr = "r.trip_date::date"
    return f"""
        SELECT
            {period_expr} AS period,
            r.country,
            r.city,
            r.business_slice_name,
            COUNT(*) FILTER (WHERE r.completed_flag) AS trips_completed,
            COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag AND r.driver_id IS NOT NULL) AS active_drivers,
            AVG(r.ticket) FILTER (WHERE r.completed_flag AND r.ticket IS NOT NULL) AS avg_ticket,
            CASE
                WHEN COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag AND r.driver_id IS NOT NULL) > 0
                THEN COUNT(*) FILTER (WHERE r.completed_flag)::numeric
                    / COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag AND r.driver_id IS NOT NULL)
                ELSE NULL
            END AS trips_per_driver,
            SUM(ABS(COALESCE(r.revenue_yego_net, 0))) FILTER (WHERE r.completed_flag) AS revenue_yego_net
        FROM {source_view} r
        WHERE r.resolution_status = 'resolved'
          AND r.business_slice_name IS NOT NULL
          AND TRIM(r.business_slice_name::text) <> ''
          AND EXTRACT(YEAR FROM {period_expr}) = %s
          {{month_filter}}
          {{country_filter}}
          {{city_filter}}
          {{slice_filter}}
        GROUP BY 1, 2, 3, 4
        HAVING COUNT(*) FILTER (WHERE r.completed_flag) > 0
        ORDER BY 1, 2, 3, 4
    """


def _fact_sql(grain: str) -> Tuple[str, str]:
    if grain == "monthly":
        table = "ops.real_business_slice_month_fact"
        period_col = "month"
    elif grain == "weekly":
        table = "ops.real_business_slice_week_fact"
        period_col = "week_start"
    else:
        table = "ops.real_business_slice_day_fact"
        period_col = "trip_date"
    sql = f"""
        SELECT
            {period_col} AS period,
            country,
            city,
            business_slice_name,
            trips_completed,
            active_drivers,
            avg_ticket,
            trips_per_driver,
            ABS(COALESCE(revenue_yego_final, revenue_yego_net, 0)) AS revenue_yego_net
        FROM {table}
        WHERE EXTRACT(YEAR FROM {period_col}) = %s
          {{month_filter}}
          {{country_filter}}
          {{city_filter}}
          {{slice_filter}}
          AND (NOT is_subfleet OR is_subfleet IS NULL)
    """
    return table, sql


def _filters(
    year: int,
    month: Optional[int],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    month_expr: str,
) -> Tuple[Dict[str, str], List[Any]]:
    parts = {
        "month_filter": "",
        "country_filter": "",
        "city_filter": "",
        "slice_filter": "",
    }
    params: List[Any] = [year]
    if month is not None:
        parts["month_filter"] = f"AND EXTRACT(MONTH FROM {month_expr}) = %s"
        params.append(month)
    if country:
        parts["country_filter"] = "AND LOWER(TRIM(country::text)) IN (%s, %s, %s)"
        c = _norm_country(country)
        params.extend([c, "pe" if c == "peru" else "co" if c == "colombia" else c, country.strip().lower()])
    if city:
        parts["city_filter"] = "AND LOWER(TRIM(city::text)) = %s"
        params.append(_norm_city(city))
    if business_slice:
        parts["slice_filter"] = "AND LOWER(TRIM(business_slice_name::text)) = %s"
        params.append(_norm_slice(business_slice))
    return parts, params


def _run_sql(sql: str, params: List[Any]) -> List[Dict[str, Any]]:
    with get_db_audit() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_base_map(
    grain: str,
    year: int,
    month: Optional[int],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
) -> Dict[AuditKey, Dict[str, Optional[float]]]:
    month_expr = "r.trip_month::date" if grain == "monthly" else "date_trunc('week', r.trip_date)::date" if grain == "weekly" else "r.trip_date::date"
    filters, params = _filters(year, month, country, city, business_slice, month_expr)
    source_view = "ops.v_real_trips_business_slice_resolved"
    sql = _resolved_sql(grain, source_view=source_view).format(**filters)
    try:
        rows = _run_sql(sql, params)
        BASE_SOURCE_USED[grain] = source_view
    except Exception:
        try:
            source_view = "ops.v_real_trips_business_slice_resolved_mv12"
            sql = _resolved_sql(grain, source_view=source_view).format(**filters)
            rows = _run_sql(sql, params)
            BASE_SOURCE_USED[grain] = source_view
        except Exception:
            _, fallback_map = _load_fact_map(grain, year, month, country, city, business_slice)
            BASE_SOURCE_USED[grain] = "fact_fallback_due_resolved_unavailable"
            return fallback_map
    out: Dict[AuditKey, Dict[str, Optional[float]]] = {}
    for row in rows:
        period = str(row["period"])
        key = AuditKey(
            grain=grain,
            period=period,
            country=_norm_country(row.get("country")),
            city=_norm_city(row.get("city")),
            lob=_norm_slice(row.get("business_slice_name")),
        )
        out[key] = _real_metrics_from_row(row)
    return out


def _load_fact_map(
    grain: str,
    year: int,
    month: Optional[int],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
) -> Tuple[str, Dict[AuditKey, Dict[str, Optional[float]]]]:
    table, sql_template = _fact_sql(grain)
    month_expr = "month" if grain == "monthly" else "week_start" if grain == "weekly" else "trip_date"
    filters, params = _filters(year, month, country, city, business_slice, month_expr)
    sql = sql_template.format(**filters)
    rows = _run_sql(sql, params)
    out: Dict[AuditKey, Dict[str, Optional[float]]] = {}
    for row in rows:
        key = AuditKey(
            grain=grain,
            period=str(row["period"]),
            country=_norm_country(row.get("country")),
            city=_norm_city(row.get("city")),
            lob=_norm_slice(row.get("business_slice_name")),
        )
        out[key] = _real_metrics_from_row(row)
    return table, out


def _load_api_map(
    plan_version: str,
    grain: str,
    year: int,
    month: Optional[int],
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
) -> Tuple[Dict[AuditKey, Dict[str, Optional[float]]], Dict[str, Any]]:
    payload = get_omniview_projection(
        plan_version=plan_version,
        grain=grain,
        country=country,
        city=city,
        business_slice=business_slice,
        year=year,
        month=month,
    )
    out: Dict[AuditKey, Dict[str, Optional[float]]] = {}
    for row in payload.get("data") or []:
        key = _api_key(grain, row)
        if key is None:
            continue
        out[key] = _real_metrics_from_row(row)
    return out, payload


def _load_plan_key_maps(
    plan_version: str,
    year: int,
    month: Optional[int],
    country: Optional[str],
    city: Optional[str],
) -> Tuple[Dict[Tuple[str, str, str, str], Dict[str, Any]], Counter]:
    plan_rows = _load_plan(plan_version, country, city, year, month)
    geos = {
        (_country_to_rules_name(str(p.get("country") or "")), str(p.get("city") or ""))
        for p in plan_rows
    }
    idx = load_rules_index_for_geos(geos)
    map_rows = load_map_fallback_rows()
    plan_by_key = _resolve_and_index_plan(plan_rows, idx, map_rows)
    unresolved = Counter()
    for plan in plan_by_key.values():
        if plan.get("resolution_status") != "resolved":
            unresolved[(plan.get("raw_city") or "", plan.get("raw_lob") or "")] += 1
    return plan_by_key, unresolved


def _plan_exists_for(audit_key: AuditKey, plan_by_key: Dict[Tuple[str, str, str, str], Dict[str, Any]]) -> bool:
    if audit_key.grain == "monthly":
        plan_month = audit_key.period
    else:
        plan_month = f"{audit_key.period[:7]}-01"
    return _projection_join_key(plan_month, audit_key.country, audit_key.city, audit_key.lob) in plan_by_key


def _status(
    base_trips: Optional[float],
    mv_trips: Optional[float],
    api_trips: Optional[float],
    plan_exists: bool,
) -> str:
    b = base_trips or 0.0
    m = mv_trips or 0.0
    a = api_trips or 0.0
    if b <= 0 and m <= 0 and a <= 0:
        return "SOURCE_EMPTY"
    if b > 0 and m <= 0:
        return "REAL_LOST_IN_MV"
    if max(b, m) > 0 and a <= 0:
        return "REAL_LOST_IN_JOIN" if plan_exists else "KEY_MISMATCH"
    return "OK"


def _render_table(rows: List[Dict[str, Any]]) -> str:
    headers = [
        "layer",
        "grain",
        "period",
        "country",
        "city",
        "lob",
        "base_trips",
        "mv_trips",
        "api_trips",
        "active_drivers",
        "revenue",
        "status",
    ]
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row.get(h, ""))))
    sep = " | "
    out = [
        sep.join(h.ljust(widths[h]) for h in headers),
        sep.join("-" * widths[h] for h in headers),
    ]
    for row in rows:
        out.append(sep.join(str(row.get(h, "")).ljust(widths[h]) for h in headers))
    return "\n".join(out)


def _sample_json(payload: Dict[str, Any]) -> str:
    rows = payload.get("data") or []
    return str(rows[:2])[:1200]


def main() -> int:
    ap = argparse.ArgumentParser(description="Auditar pipeline REAL de Omniview")
    ap.add_argument("--plan-version", help="Versión de plan; default = última disponible")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int)
    ap.add_argument("--country")
    ap.add_argument("--city")
    ap.add_argument("--business-slice")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    plan_version = args.plan_version or _latest_plan_version()
    if not plan_version:
        print("No se pudo resolver plan_version para la auditoría.")
        return 1

    plan_by_key, unresolved = _load_plan_key_maps(
        plan_version=plan_version,
        year=args.year,
        month=args.month,
        country=args.country,
        city=args.city,
    )

    all_rows: List[Dict[str, Any]] = []
    api_samples: Dict[str, str] = {}
    for grain in GRAINS:
        base_map = _load_base_map(grain, args.year, args.month, args.country, args.city, args.business_slice)
        fact_source, fact_map = _load_fact_map(grain, args.year, args.month, args.country, args.city, args.business_slice)
        api_map, api_payload = _load_api_map(
            plan_version=plan_version,
            grain=grain,
            year=args.year,
            month=args.month,
            country=args.country,
            city=args.city,
            business_slice=args.business_slice,
        )
        api_samples[grain] = _sample_json(api_payload)
        keys = sorted(set(base_map) | set(fact_map) | set(api_map), key=lambda k: (k.period, k.country, k.city, k.lob))
        for key in keys[: args.limit]:
            base = base_map.get(key, {})
            fact = fact_map.get(key, {})
            api = api_map.get(key, {})
            plan_exists = _plan_exists_for(key, plan_by_key)
            all_rows.append(
                {
                    "layer": fact_source,
                    "grain": key.grain,
                    "period": key.period,
                    "country": key.country,
                    "city": key.city,
                    "lob": key.lob,
                    "base_trips": round(base.get("trips") or 0.0, 2),
                    "mv_trips": round(fact.get("trips") or 0.0, 2),
                    "api_trips": round(api.get("trips") or 0.0, 2),
                    "active_drivers": round(api.get("drivers") or fact.get("drivers") or base.get("drivers") or 0.0, 2),
                    "revenue": round(api.get("revenue") or fact.get("revenue") or base.get("revenue") or 0.0, 2),
                    "status": _status(base.get("trips"), fact.get("trips"), api.get("trips"), plan_exists),
                }
            )

    problem_rows = [r for r in all_rows if r["status"] != "OK"]
    print(f"plan_version={plan_version}")
    print(f"scope year={args.year} month={args.month or 'ALL'} country={args.country or 'ALL'} city={args.city or 'ALL'} lob={args.business_slice or 'ALL'}")
    print()
    print(_render_table(problem_rows[: args.limit] if problem_rows else all_rows[: args.limit]))
    print()
    print("=== API sample JSON ===")
    for grain in GRAINS:
        print(f"[{grain}] {api_samples.get(grain, '[]')}")
    print()
    print("=== Diagnostics ===")
    status_counts = Counter(r["status"] for r in all_rows)
    for status, count in status_counts.most_common():
        print(f"{status}: {count}")
    for grain in GRAINS:
        print(f"base_source[{grain}]={BASE_SOURCE_USED.get(grain, 'unknown')}")
    if unresolved:
        print("plan_unresolved_keys:")
        for (raw_city, raw_lob), count in unresolved.most_common(20):
            print(f"  {raw_city} / {raw_lob}: {count}")
    mismatched_plan_keys = [
        k for k, v in plan_by_key.items()
        if v.get("resolution_status") == "resolved"
    ]
    print(f"resolved_plan_keys={len(mismatched_plan_keys)}")
    print("country_normalization_variants_checked=peru/perú/pe and colombia/col/co")
    print("city_normalization=remove_accents + lower")
    print("slice_normalization=remove_accents + lower")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
