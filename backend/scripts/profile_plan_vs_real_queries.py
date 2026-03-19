"""
Perfila con EXPLAIN ANALYZE las consultas usadas por Plan vs Real (paridad).
Identifica scans caros, joins, falta de índices.
Uso: python -m scripts.profile_plan_vs_real_queries [--year 2025]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.connection import get_db


def run_explain(conn, label: str, sql: str, params: tuple) -> None:
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    try:
        cur = conn.cursor()
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}", params)
        for row in cur.fetchall():
            print(row[0])
        cur.close()
    except Exception as e:
        print(f"ERROR: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2025)
    args = ap.parse_args()
    year = args.year
    start = f"{year}-01-01"
    end = f"{year + 1}-01-01"

    with get_db() as conn:
        # Query equivalente a get_plan_vs_real_monthly(year=year, use_canonical=True)
        run_explain(
            conn,
            f"v_plan_vs_real_realkey_canonical (year={year})",
            """
            SELECT country, city, park_id, park_name, real_tipo_servicio, period_date,
                   trips_plan, trips_real, revenue_plan, revenue_real,
                   variance_trips, variance_revenue
            FROM ops.v_plan_vs_real_realkey_canonical
            WHERE period_date >= %s::DATE AND period_date < %s::DATE
            ORDER BY period_date DESC NULLS LAST, country, city, park_id, real_tipo_servicio
            """,
            (start, end),
        )
        # Legacy
        run_explain(
            conn,
            f"v_plan_vs_real_realkey_final (year={year})",
            """
            SELECT country, city, park_id, park_name, real_tipo_servicio, period_date,
                   trips_plan, trips_real, revenue_plan, revenue_real,
                   variance_trips, variance_revenue
            FROM ops.v_plan_vs_real_realkey_final
            WHERE period_date >= %s::DATE AND period_date < %s::DATE
            ORDER BY period_date DESC NULLS LAST, country, city, park_id, real_tipo_servicio
            """,
            (start, end),
        )


if __name__ == "__main__":
    main()
