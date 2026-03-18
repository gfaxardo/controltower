"""
Valida cobertura temporal canónica para Real mensual (año dado).
Responde: qué meses tienen datos de trips, revenue y drivers core en fuentes canónicas.
Uso: python -m scripts.validate_real_monthly_coverage [--year 2025] [--country PE]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor


def main() -> None:
    ap = argparse.ArgumentParser(description="Cobertura temporal canónica Real mensual")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--country", type=str, default=None)
    ap.add_argument("--timeout", type=int, default=300, help="Statement timeout segundos")
    args = ap.parse_args()
    year = args.year
    country = args.country

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = %s", (str(args.timeout * 1000),))

        # 1) Cobertura desde canónica mensual histórica (mv_real_monthly_canonical_hist)
        where_hist = ["EXTRACT(YEAR FROM month_start) = %s"]
        params_hist = [year]
        if country:
            c = (country or "").lower().strip()
            if c in ("pe", "peru"):
                where_hist.append("LOWER(TRIM(country)) IN ('pe', 'peru')")
            elif c in ("co", "colombia"):
                where_hist.append("LOWER(TRIM(country)) IN ('co', 'colombia')")
            else:
                where_hist.append("LOWER(TRIM(country)) = %s")
                params_hist.append(c)
        cur.execute("""
            SELECT month_start, SUM(trips) AS trips, SUM(COALESCE(margin_total, 0)) AS revenue,
                   SUM(COALESCE(active_drivers_core, 0))::bigint AS active_drivers
            FROM ops.mv_real_monthly_canonical_hist
            WHERE """ + " AND ".join(where_hist) + """
            GROUP BY month_start
            ORDER BY month_start
        """, params_hist)
        drill_months = {}
        driver_months = {}
        for r in cur.fetchall():
            k = r["month_start"].strftime("%Y-%m") if hasattr(r["month_start"], "strftime") else str(r["month_start"])[:7]
            drill_months[k] = {"trips": int(r["trips"] or 0), "revenue": float(r["revenue"] or 0)}
            driver_months[k] = int(r["active_drivers"] or 0)

        cur.close()

    # 3) Todos los meses del año
    all_months = [f"{year}-{m:02d}" for m in range(1, 13)]
    scope = f"year={year}" + (f" country={country}" if country else " global")

    print(f"COVERAGE CANONICAL REAL MONTHLY — {scope}")
    print("month;has_trips_revenue;trips;revenue;has_drivers_core;active_drivers")
    for mon in all_months:
        dr = drill_months.get(mon, {})
        trips = dr.get("trips", 0)
        rev = dr.get("revenue", 0)
        has_trips = "yes" if trips or rev else "no"
        dr_count = driver_months.get(mon, 0)
        has_dr = "yes" if dr_count else "no"
        print(f"{mon};{has_trips};{trips};{round(rev, 2)};{has_dr};{dr_count}")

    print("")
    print("SUMMARY:")
    months_with_trips = sum(1 for m in all_months if (drill_months.get(m, {}).get("trips") or drill_months.get(m, {}).get("revenue")))
    months_with_drivers = sum(1 for m in all_months if driver_months.get(m, 0))
    print(f"  Months with trips/revenue (mv_real_monthly_canonical_hist): {months_with_trips}/12")
    print(f"  Months with drivers core (mv_real_monthly_canonical_hist): {months_with_drivers}/12")
    print("  (Fuente: ops.mv_real_monthly_canonical_hist; cobertura histórica completa si la MV está refrescada.)")


if __name__ == "__main__":
    main()
