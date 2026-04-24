"""
FASE_KPI_CONSISTENCY — Diagnóstico fuerte de ROLLUP_MISMATCH.

Compara, por cada (country, city, business_slice, month):

  A) trips_month_fact / revenue_month_fact:
       SUM desde ops.real_business_slice_month_fact

  B) trips_recomputed / revenue_recomputed:
       SUM desde ops.real_business_slice_day_fact (rollup canónico
       del mes calendario).

  C) trips_resolved / revenue_resolved:
       SUM desde ops.v_real_trips_business_slice_resolved (universo
       canon de viajes resueltos en el mes), si está disponible.
       *Opcional* mediante --include-resolved (puede ser pesado).

Para cada celda con mismatch significativo, sugiere `suspected_cause`:

  * stale_month_fact:    refreshed_at(month_fact) << refreshed_at(day_fact)
  * stale_day_fact:      refreshed_at(day_fact)   << refreshed_at(month_fact)
  * country_mismatch:    el país del fact no normaliza igual al del day_fact
  * mapping_mismatch:    business_slice_name presente en uno pero no en el otro
  * duplication:         day_fact > month_fact > 0 pero también para subfleet
  * filter_mismatch:     diff persistente sin causa clara → revisar filtros condicion
  * negligible:          diff dentro de tolerancia
  * resolved_drift:      diff vs resolved (solo con --include-resolved)

Uso:
  python -m backend.scripts.debug_rollup_mismatch --year 2026 --month 4
  python -m backend.scripts.debug_rollup_mismatch --year 2026 --month 4 --country "España" --include-resolved

Salida:
  backend/scripts/outputs/rollup_mismatch_<YYYYMMDDTHHMMSS>.csv
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import date, datetime
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

from app.db.connection import get_db  # noqa: E402

# Tolerancias
TRIP_REL_EPS = 0.005   # 0.5%
TRIP_ABS_EPS = 1.0
REV_REL_EPS  = 0.005
REV_ABS_EPS  = 5.0


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


def _build_filter(country: Optional[str], city: Optional[str], business_slice: Optional[str]) -> Tuple[str, List[Any]]:
    where = []
    params: List[Any] = []
    if country:
        where.append("country IS NOT DISTINCT FROM %s")
        params.append(country)
    if city:
        where.append("city IS NOT DISTINCT FROM %s")
        params.append(city)
    if business_slice:
        where.append("business_slice_name IS NOT DISTINCT FROM %s")
        params.append(business_slice)
    sql = (" AND " + " AND ".join(where)) if where else ""
    return sql, params


def _month_bounds(year: int, month: int) -> Tuple[date, date]:
    import calendar

    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _load_month_fact(year: int, month: int, country: Optional[str], city: Optional[str], bs: Optional[str]) -> Dict[Tuple, Dict[str, Any]]:
    extra_where, extra_params = _build_filter(country, city, bs)
    sql = f"""
        SELECT country, city, business_slice_name,
               SUM(trips_completed)::numeric AS trips_month_fact,
               SUM(revenue_yego_net)::numeric AS revenue_month_fact,
               MAX(refreshed_at) AS month_refreshed_at
        FROM ops.real_business_slice_month_fact
        WHERE month = %s::date {extra_where}
        GROUP BY country, city, business_slice_name
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


def _load_day_rollup(year: int, month: int, country: Optional[str], city: Optional[str], bs: Optional[str]) -> Dict[Tuple, Dict[str, Any]]:
    extra_where, extra_params = _build_filter(country, city, bs)
    start, end = _month_bounds(year, month)
    sql = f"""
        SELECT country, city, business_slice_name,
               SUM(trips_completed)::numeric AS trips_recomputed,
               SUM(revenue_yego_net)::numeric AS revenue_recomputed,
               MIN(trip_date) AS first_day,
               MAX(trip_date) AS last_day,
               COUNT(DISTINCT trip_date) AS distinct_days,
               MAX(refreshed_at) AS day_refreshed_at
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= %s::date AND trip_date <= %s::date {extra_where}
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


def _load_resolved_rollup(year: int, month: int, country: Optional[str], city: Optional[str], bs: Optional[str]) -> Dict[Tuple, Dict[str, Any]]:
    """Universo canónico desde la vista resolved. Puede ser pesado."""
    extra_where, extra_params = _build_filter(country, city, bs)
    start, end = _month_bounds(year, month)
    sql = f"""
        SELECT country, city, business_slice_name,
               COUNT(*) FILTER (WHERE completed_flag)::numeric AS trips_resolved,
               SUM(revenue_yego_net) FILTER (WHERE completed_flag)::numeric AS revenue_resolved
        FROM ops.v_real_trips_business_slice_resolved
        WHERE resolution_status = 'resolved'
          AND business_slice_name IS NOT NULL
          AND trip_date >= %s::date
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


def _diagnose_cause(
    month_row: Dict[str, Any],
    day_row: Dict[str, Any],
    resolved_row: Optional[Dict[str, Any]],
    diff_trips_abs: float,
    diff_rev_abs: float,
    trips_ok: bool,
    rev_ok: bool,
) -> str:
    has_month = bool(month_row)
    has_day = bool(day_row)

    if has_day and not has_month:
        return "mapping_mismatch_only_in_day_fact"
    if has_month and not has_day:
        return "mapping_mismatch_only_in_month_fact"

    # Comparar refreshed_at
    m_ref = month_row.get("month_refreshed_at") if has_month else None
    d_ref = day_row.get("day_refreshed_at") if has_day else None
    if m_ref and d_ref:
        try:
            lag = (d_ref - m_ref).total_seconds()
        except Exception:
            lag = 0
        # >12h indica posible staleness
        if lag > 12 * 3600 and (not trips_ok or not rev_ok):
            return "stale_month_fact"
        if lag < -12 * 3600 and (not trips_ok or not rev_ok):
            return "stale_day_fact"

    if trips_ok and rev_ok:
        return "negligible"

    # Si hay resolved disponible, comparar contra él
    if resolved_row:
        r_t = _f(resolved_row.get("trips_resolved"))
        r_r = _f(resolved_row.get("revenue_resolved"))
        m_t = _f(month_row.get("trips_month_fact")) if has_month else 0.0
        d_t = _f(day_row.get("trips_recomputed")) if has_day else 0.0
        # Si day_fact coincide con resolved pero month_fact no -> stale_month_fact
        if not _within(m_t, r_t, TRIP_REL_EPS, TRIP_ABS_EPS) and _within(d_t, r_t, TRIP_REL_EPS, TRIP_ABS_EPS):
            return "stale_month_fact"
        # Si month_fact coincide con resolved pero day_fact no -> stale_day_fact
        if _within(m_t, r_t, TRIP_REL_EPS, TRIP_ABS_EPS) and not _within(d_t, r_t, TRIP_REL_EPS, TRIP_ABS_EPS):
            return "stale_day_fact"
        # Si ambos discrepan respecto a resolved pero entre sí coinciden -> filter_mismatch / mapping
        if not _within(m_t, r_t, TRIP_REL_EPS, TRIP_ABS_EPS) and not _within(d_t, r_t, TRIP_REL_EPS, TRIP_ABS_EPS):
            if _within(m_t, d_t, TRIP_REL_EPS, TRIP_ABS_EPS):
                return "filter_mismatch_vs_resolved"
            return "duplication_or_mapping"

    # Sin resolved: diferenciar cuándo day > month vs day < month
    if has_month and has_day:
        m_t = _f(month_row.get("trips_month_fact"))
        d_t = _f(day_row.get("trips_recomputed"))
        if d_t > m_t:
            return "day_gt_month_likely_stale_month_fact"
        if m_t > d_t:
            return "month_gt_day_possible_stale_day_fact_or_duplication"

    return "unknown"


CSV_COLUMNS = [
    "country", "city", "business_slice", "month",
    "trips_month_fact", "trips_recomputed", "trips_resolved",
    "diff_trips_abs", "diff_trips_pct",
    "revenue_month_fact", "revenue_recomputed", "revenue_resolved",
    "diff_revenue_abs", "diff_revenue_pct",
    "month_refreshed_at", "day_refreshed_at",
    "first_day", "last_day", "distinct_days",
    "status", "suspected_cause",
]


def run_audit(
    year: int,
    month: int,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    include_resolved: bool = False,
) -> List[Dict[str, Any]]:
    print(
        f"[rollup-mismatch] year={year} month={month} country={country or '*'} "
        f"city={city or '*'} bs={business_slice or '*'} include_resolved={include_resolved}",
        flush=True,
    )

    month_data = _load_month_fact(year, month, country, city, business_slice)
    day_data = _load_day_rollup(year, month, country, city, business_slice)
    resolved_data: Dict[Tuple, Dict[str, Any]] = {}
    if include_resolved:
        try:
            resolved_data = _load_resolved_rollup(year, month, country, city, business_slice)
        except Exception as e:
            print(f"[rollup-mismatch] WARN resolved skipped: {e}", flush=True)

    keys = set(month_data.keys()) | set(day_data.keys()) | set(resolved_data.keys())
    print(
        f"[rollup-mismatch] cells: month_fact={len(month_data)} day_rollup={len(day_data)} "
        f"resolved={len(resolved_data)} merged={len(keys)}",
        flush=True,
    )

    month_iso = date(year, month, 1).isoformat()
    out: List[Dict[str, Any]] = []
    for k in sorted(keys, key=lambda x: tuple("" if v is None else str(v) for v in x)):
        co, ci, bs = k
        m = month_data.get(k, {})
        d = day_data.get(k, {})
        r = resolved_data.get(k) if include_resolved else None

        m_t = _f(m.get("trips_month_fact"))
        d_t = _f(d.get("trips_recomputed"))
        r_t = _f(r.get("trips_resolved")) if r else None
        m_r = _f(m.get("revenue_month_fact"))
        d_r = _f(d.get("revenue_recomputed"))
        r_r = _f(r.get("revenue_resolved")) if r else None

        diff_t_abs = round(m_t - d_t, 4)
        diff_r_abs = round(m_r - d_r, 4)
        base_t = max(abs(m_t), abs(d_t))
        base_r = max(abs(m_r), abs(d_r))
        diff_t_pct = round((diff_t_abs / base_t) * 100.0, 4) if base_t > 0 else 0.0
        diff_r_pct = round((diff_r_abs / base_r) * 100.0, 4) if base_r > 0 else 0.0

        trips_ok = _within(m_t, d_t, TRIP_REL_EPS, TRIP_ABS_EPS)
        rev_ok = _within(m_r, d_r, REV_REL_EPS, REV_ABS_EPS)
        status = "ok" if (trips_ok and rev_ok) else "mismatch"
        cause = _diagnose_cause(m, d, r, abs(diff_t_abs), abs(diff_r_abs), trips_ok, rev_ok)

        out.append({
            "country": co or "",
            "city": ci or "",
            "business_slice": bs or "",
            "month": month_iso,
            "trips_month_fact": m_t,
            "trips_recomputed": d_t,
            "trips_resolved": r_t if r_t is not None else "",
            "diff_trips_abs": diff_t_abs,
            "diff_trips_pct": diff_t_pct,
            "revenue_month_fact": m_r,
            "revenue_recomputed": d_r,
            "revenue_resolved": r_r if r_r is not None else "",
            "diff_revenue_abs": diff_r_abs,
            "diff_revenue_pct": diff_r_pct,
            "month_refreshed_at": m.get("month_refreshed_at") or "",
            "day_refreshed_at": d.get("day_refreshed_at") or "",
            "first_day": d.get("first_day") or "",
            "last_day": d.get("last_day") or "",
            "distinct_days": d.get("distinct_days") or 0,
            "status": status,
            "suspected_cause": cause,
        })
    return out


def write_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_COLUMNS})


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    mismatches = [r for r in rows if r.get("status") == "mismatch"]
    by_cause: Dict[str, int] = {}
    for r in mismatches:
        c = r.get("suspected_cause") or "unknown"
        by_cause[c] = by_cause.get(c, 0) + 1
    return {
        "cells": total,
        "ok": total - len(mismatches),
        "mismatch": len(mismatches),
        "by_cause": by_cause,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="FASE_KPI_CONSISTENCY rollup mismatch debugger")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--country", type=str, default=None)
    p.add_argument("--city", type=str, default=None)
    p.add_argument("--business-slice", dest="business_slice", type=str, default=None)
    p.add_argument("--include-resolved", action="store_true", help="Compara también contra v_real_trips_business_slice_resolved (más lento).")
    p.add_argument("--out", type=str, default=None)
    args = p.parse_args()

    rows = run_audit(args.year, args.month, args.country, args.city, args.business_slice, args.include_resolved)
    summary = summarize(rows)
    print(f"[rollup-mismatch] resumen: cells={summary['cells']} ok={summary['ok']} mismatch={summary['mismatch']}")
    for cause, n in summary["by_cause"].items():
        print(f"  - {cause}: {n}")

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_path = Path(args.out) if args.out else (_HERE / "outputs" / f"rollup_mismatch_{ts}.csv")
    write_csv(rows, out_path)
    print(f"[rollup-mismatch] CSV: {out_path}")

    if summary["mismatch"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
