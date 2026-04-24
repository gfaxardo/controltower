"""
test_kpi_consistency.py — FASE DECISION READINESS

QA script: valida la consistencia KPI entre monthly y daily (dentro del mes).
Carga datos reales desde la BD y llama a validate_kpi_consistency().

Uso:
  python -m scripts.test_kpi_consistency --year 2026 --month 4
  python -m scripts.test_kpi_consistency --year 2026 --month 2 --country PE

Salida:
  Imprime resultado por KPI.
  Exit code 0 = todo OK | 1 = warnings | 2 = mismatches detectados.
"""
from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config.kpi_semantics import KPI_SEMANTICS, get_db_column  # noqa: E402
from app.db.connection import get_db                                # noqa: E402
from app.services.kpi_consistency import (                         # noqa: E402
    validate_kpi_consistency,
    consistency_summary,
)


# ─── Carga de datos reales ────────────────────────────────────────────────────

def _load_monthly(
    year: int, month: int,
    country: Optional[str], city: Optional[str],
) -> List[Dict[str, Any]]:
    """Carga month_fact y devuelve lista de dicts."""
    db_cols = [get_db_column(k) for k in KPI_SEMANTICS if get_db_column(k)]
    col_list = ", ".join(set(db_cols))  # columnas únicas

    extra_where = ""
    extra_params: List[Any] = []
    if country:
        extra_where += " AND country IS NOT DISTINCT FROM %s"
        extra_params.append(country)
    if city:
        extra_where += " AND city IS NOT DISTINCT FROM %s"
        extra_params.append(city)

    sql = f"""
        SELECT {col_list}
        FROM ops.real_business_slice_month_fact
        WHERE month = %s::date {extra_where}
    """
    rows: List[Dict[str, Any]] = []
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, [date(year, month, 1)] + extra_params)
        cols = [c[0] for c in cur.description]
        for row in cur.fetchall():
            rows.append(dict(zip(cols, row)))
        cur.close()
    return rows


def _load_daily(
    year: int, month: int,
    country: Optional[str], city: Optional[str],
) -> List[Dict[str, Any]]:
    """Carga day_fact dentro del mes calendario y devuelve lista de dicts."""
    db_cols = [get_db_column(k) for k in KPI_SEMANTICS if get_db_column(k)]
    col_list = ", ".join(set(db_cols))

    last_day = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    extra_where = ""
    extra_params: List[Any] = []
    if country:
        extra_where += " AND country IS NOT DISTINCT FROM %s"
        extra_params.append(country)
    if city:
        extra_where += " AND city IS NOT DISTINCT FROM %s"
        extra_params.append(city)

    sql = f"""
        SELECT {col_list}
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= %s::date
          AND trip_date <= %s::date
          {extra_where}
    """
    rows: List[Dict[str, Any]] = []
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, [start, end] + extra_params)
        cols = [c[0] for c in cur.description]
        for row in cur.fetchall():
            rows.append(dict(zip(cols, row)))
        cur.close()
    return rows


# ─── Test principal ───────────────────────────────────────────────────────────

def test_consistency(
    year: int, month: int,
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> int:
    print(
        f"\n[test-kpi-consistency] year={year} month={month} "
        f"country={country or '*'} city={city or '*'}",
        flush=True,
    )
    print(
        "[test-kpi-consistency] base de comparación: SUM(daily dentro del mes calendario)\n",
        flush=True,
    )

    monthly_df = _load_monthly(year, month, country, city)
    daily_df = _load_daily(year, month, country, city)

    print(f"  monthly rows: {len(monthly_df)}  daily rows: {len(daily_df)}")

    results = validate_kpi_consistency(monthly_df, daily_df)

    print("\n  Resultado por KPI:")
    print(f"  {'KPI':<22} {'monthly':>14} {'daily_sum':>14} {'diff':>10} {'diff%':>8}  status")
    print("  " + "-" * 78)
    for r in results:
        m  = r['monthly']  if r['monthly']  is not None else "—"
        d  = r['daily_sum'] if r['daily_sum'] is not None else "—"
        df = r['diff']     if r['diff']      is not None else "—"
        dp = f"{r['diff_pct']:.2f}%" if r['diff_pct'] is not None else "—"
        st = r['status']
        marker = "❌" if st == "mismatch" else ("—" if st == "no_data" else "✅")
        fmt_m  = f"{m:>14.2f}" if isinstance(m,  float) else f"{'—':>14}"
        fmt_d  = f"{d:>14.2f}" if isinstance(d,  float) else f"{'—':>14}"
        fmt_df = f"{df:>10.4f}" if isinstance(df, float) else f"{'—':>10}"
        print(f"  {r['kpi']:<22}{fmt_m}{fmt_d}{fmt_df} {dp:>8}  {marker} {st}")

    summary = consistency_summary(results)
    print(f"\n  Resumen: ok={summary['ok']} mismatch={summary['mismatch']} no_data={summary['no_data']}")

    mismatches = [r for r in results if r["status"] == "mismatch"]
    if mismatches:
        print("\n❌ Inconsistencias detectadas:")
        for r in mismatches:
            print(f"   - {r['kpi']}: monthly={r['monthly']:.2f} vs daily_sum={r['daily_sum']:.2f} "
                  f"(diff={r['diff']:.4f}, {r['diff_pct']:.2f}%)")
        return 2
    else:
        print("\n✅ Consistencia validada — 0 mismatches en KPIs aditivos decision_ready")
        return 0


def main() -> int:
    p = argparse.ArgumentParser(description="QA: KPI consistency monthly vs daily-in-month")
    p.add_argument("--year",    type=int, required=True)
    p.add_argument("--month",   type=int, required=True)
    p.add_argument("--country", type=str, default=None)
    p.add_argument("--city",    type=str, default=None)
    args = p.parse_args()
    return test_consistency(args.year, args.month, args.country, args.city)


if __name__ == "__main__":
    raise SystemExit(main())
