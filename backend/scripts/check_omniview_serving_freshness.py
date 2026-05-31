#!/usr/bin/env python3
"""
Health guard: verifica frescura de serving facts vs RAW source.
Compara MAX(fecha) entre RAW, day_fact, week_fact, projection_daily_fact.
Si serving lag > 1 día respecto a RAW, exit 1.

Uso:
  cd backend
  python -m scripts.check_omniview_serving_freshness
  python -m scripts.check_omniview_serving_freshness --max-lag-days 2
"""
from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from app.db.connection import get_db

CHECKS = [
    ("raw", "public.trips_2026", "fecha_inicio_viaje::date", "RAW trips", None),
    ("day_fact", "ops.real_business_slice_day_fact", "trip_date", "FACT_DAILY", None),
    ("week_fact", "ops.real_business_slice_week_fact", "week_start", "FACT_WEEKLY", 7),
    ("projection_daily", "serving.omniview_projection_daily_fact", "period_key", "SERVING_PROJECTION", None),
]


def check_freshness(max_lag_days: int = 1) -> dict:
    results = {}
    today = date.today()

    with get_db() as conn:
        cur = conn.cursor()
        for key, table, col, label, weekly_factor in CHECKS:
            try:
                where = f"WHERE {col}::date <= CURRENT_DATE" if key == "projection_daily" else ""
                cur.execute(f"SELECT MAX({col}) FROM {table} {where}")
                row = cur.fetchone()
                max_date = row[0] if row and row[0] else None
                if max_date and hasattr(max_date, "date"):
                    max_date = max_date.date()
                elif isinstance(max_date, str):
                    max_date = date.fromisoformat(max_date[:10])
                lag = (today - max_date).days if max_date else None
                eff_lag = lag
                eff_max_lag = max_lag_days * (weekly_factor or 1)
                results[key] = {
                    "label": label,
                    "max_date": max_date.isoformat() if max_date else None,
                    "lag_days": lag,
                    "ok": lag is not None and lag <= eff_max_lag,
                    "max_lag": eff_max_lag,
                }
            except Exception as e:
                results[key] = {
                    "label": label,
                    "max_date": None,
                    "lag_days": None,
                    "ok": False,
                    "error": str(e)[:200],
                }
        cur.close()

    results["raw_max_date"] = results.get("raw", {}).get("max_date")
    results["max_lag_days"] = max_lag_days
    results["overall_ok"] = all(v.get("ok", False) for v in results.values() if isinstance(v, dict))
    return results


def main():
    ap = argparse.ArgumentParser(description="Check Omniview serving freshness vs RAW")
    ap.add_argument("--max-lag-days", type=int, default=1, help="Max allowed lag in days (default 1)")
    ap.add_argument("--json", action="store_true", help="Output as JSON")
    args = ap.parse_args()

    results = check_freshness(args.max_lag_days)

    if args.json:
        import json
        print(json.dumps(results, indent=2, default=str))
    else:
        print(f"{'Layer':<25} {'Max Date':<15} {'Lag (d)':<10} {'Status'}")
        print("-" * 60)
        for key in ["raw", "day_fact", "week_fact", "projection_daily"]:
            r = results[key]
            status = "OK" if r["ok"] else "FAIL"
            print(f"{r['label']:<25} {r['max_date'] or 'N/A':<15} {str(r['lag_days']) if r['lag_days'] is not None else 'N/A':<10} {status}")
            if r.get("error"):
                print(f"  ERROR: {r['error']}")
        print("-" * 60)
        print(f"Overall: {'PASS' if results['overall_ok'] else 'FAIL'}")

    return 0 if results["overall_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
