"""
Paridad agregada: ops.v_plan_vs_real_realkey_final vs ops.mv_plan_vs_real_monthly_fact.
Mismos predicados que el endpoint (periodo mensual, optional country/city/real_tipo_servicio).

No compara fila a fila; suma trips/revenue/gap a nivel conjunto filtrado (tolerancia float).

Uso:
  cd backend && python -m scripts.validate_plan_vs_real_mv_parity --month 2026-01
  python -m scripts.validate_plan_vs_real_mv_parity --month 2025-12 --country pe --city lima
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

AGG_SQL = """
SELECT
  COUNT(*)::bigint AS row_count,
  COALESCE(SUM(trips_plan), 0)::numeric AS sum_trips_plan,
  COALESCE(SUM(trips_real), 0)::numeric AS sum_trips_real,
  COALESCE(SUM(revenue_plan), 0)::numeric AS sum_revenue_plan,
  COALESCE(SUM(revenue_real), 0)::numeric AS sum_revenue_real,
  COALESCE(SUM(trips_plan - trips_real), 0)::numeric AS sum_gap_trips,
  COALESCE(SUM(COALESCE(revenue_plan,0) - COALESCE(revenue_real,0)), 0)::numeric AS sum_gap_revenue
FROM {from_clause}
WHERE {where_sql}
"""


def _num(x) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    return float(x)


def _row(d: dict) -> dict:
    return {k: _num(v) for k, v in d.items()}


def _diff(a: dict, b: dict, tol: float) -> list[str]:
    out = []
    for k in set(a) | set(b):
        da, db = a.get(k, 0), b.get(k, 0)
        if abs(da - db) > tol:
            out.append(f"{k}: view={da} mv={db}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYY-MM")
    parser.add_argument("--country", default=None)
    parser.add_argument("--city", default=None)
    parser.add_argument("--real-tipo-servicio", default=None, dest="lob")
    parser.add_argument("--tol", type=float, default=0.5, help="Tolerancia absoluta en sums")
    args = parser.parse_args()

    ym = args.month.strip()
    y, mo = int(ym[0:4]), int(ym[5:7])
    from datetime import date as dcls

    start = dcls(y, mo, 1)
    end = dcls(y + 1, 1, 1) if mo == 12 else dcls(y, mo + 1, 1)

    where_parts = ["period_date >= %s::date", "period_date < %s::date"]
    params: list = [start, end]
    if args.country:
        where_parts.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(args.country)
    if args.city:
        where_parts.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(args.city)
    if args.lob:
        where_parts.append("LOWER(TRIM(real_tipo_servicio)) = LOWER(TRIM(%s))")
        params.append(args.lob)
    where_sql = " AND ".join(where_parts)

    from app.db.connection import init_db_pool, get_db
    from psycopg2.extras import RealDictCursor

    init_db_pool()

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        view_sql = AGG_SQL.format(from_clause="ops.v_plan_vs_real_realkey_final", where_sql=where_sql)
        mv_sql = AGG_SQL.format(from_clause="ops.mv_plan_vs_real_monthly_fact", where_sql=where_sql)
        cur.execute(view_sql, params)
        view_row = _row(dict(cur.fetchone() or {}))
        cur.execute(mv_sql, params)
        mv_row = _row(dict(cur.fetchone() or {}))
        cur.close()

    print("=== filtros ===", {"month": ym, "country": args.country, "city": args.city, "lob": args.lob})
    print("=== vista ===", view_row)
    print("=== mv    ===", mv_row)
    d = _diff(view_row, mv_row, args.tol)
    if d:
        print("=== DIFF (FAIL) ===")
        for x in d:
            print(" ", x)
        return 1
    print("=== Paridad OK (tol=%s) ===" % args.tol)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
