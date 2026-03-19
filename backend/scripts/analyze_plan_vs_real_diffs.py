"""
Análisis de diferencias Plan vs Real legacy vs canónico.

Detecta causas típicas: joins por park_id, normalización city, ABS(comision) vs lógica anterior, missing data por país.
Salida: outputs/plan_vs_real_diff_analysis_YYYY.csv (o --out).
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.plan_vs_real_service import get_plan_vs_real_monthly


def _aggregate_by_month_country(rows: list[dict]) -> dict[tuple[str, str], dict]:
    agg: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "trips_real": 0, "revenue_real": 0.0,
        "trips_plan": 0, "revenue_plan": 0.0,
        "cells": 0,
    })
    for r in rows:
        period = r.get("period_date")
        month_ym = period.strftime("%Y-%m") if period else ""
        country = (r.get("country") or "").strip().lower() or "global"
        key = (month_ym, country)
        agg[key]["trips_real"] += int(r.get("trips_real") or 0)
        agg[key]["revenue_real"] += float(r.get("revenue_real") or 0)
        agg[key]["trips_plan"] += int(r.get("trips_plan") or 0)
        agg[key]["revenue_plan"] += float(r.get("revenue_plan") or 0)
        agg[key]["cells"] += 1
    return dict(agg)


def _infer_cause(row: dict, legacy_agg: dict, canonical_agg: dict) -> str:
    """Inferir causa probable de la diferencia."""
    month, country = row["month"], row["country"]
    key = (month, country)
    L = legacy_agg.get(key, {})
    C = canonical_agg.get(key, {})
    trips_l = L.get("trips_real", 0) or 0
    trips_c = C.get("trips_real", 0) or 0
    rev_l = L.get("revenue_real", 0) or 0
    rev_c = C.get("revenue_real", 0) or 0

    causes = []
    if trips_l > 0 and trips_c == 0:
        causes.append("missing_data_canonical")
    if trips_c > 0 and trips_l == 0:
        causes.append("missing_data_legacy")
    if row.get("diff_revenue_pct", 0) > 5 and row.get("diff_trips_pct", 0) < 1:
        causes.append("revenue_abs_vs_signed")
    if row.get("diff_trips_pct", 0) > 2:
        causes.append("join_or_city_normalization")
    if country and country not in ("pe", "co", "global"):
        causes.append("country_filter_mismatch")
    if not causes:
        causes.append("minor_or_rounding")
    return "|".join(causes)


def main() -> None:
    ap = argparse.ArgumentParser(description="Análisis de diferencias Plan vs Real legacy vs canónico")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--country", type=str, default=None)
    ap.add_argument("--out", type=str, default=None, help="CSV salida; por defecto outputs/plan_vs_real_diff_analysis_YYYY.csv")
    args = ap.parse_args()

    try:
        legacy = get_plan_vs_real_monthly(country=args.country, year=args.year, use_canonical=False)
        canonical = get_plan_vs_real_monthly(country=args.country, year=args.year, use_canonical=True)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    legacy_agg = _aggregate_by_month_country(legacy)
    canonical_agg = _aggregate_by_month_country(canonical)
    if args.year:
        legacy_agg = {k: v for k, v in legacy_agg.items() if k[0].startswith(str(args.year))}
        canonical_agg = {k: v for k, v in canonical_agg.items() if k[0].startswith(str(args.year))}

    all_keys = sorted(set(legacy_agg) | set(canonical_agg))
    rows = []
    for (month_ym, country) in all_keys:
        L = legacy_agg.get((month_ym, country), {"trips_real": 0, "revenue_real": 0.0})
        C = canonical_agg.get((month_ym, country), {"trips_real": 0, "revenue_real": 0.0})
        trips_l = L["trips_real"]
        trips_c = C["trips_real"]
        rev_l = L["revenue_real"]
        rev_c = C["revenue_real"]
        diff_trips = abs(trips_c - trips_l)
        diff_rev = abs(rev_c - rev_l)
        pct_trips = (100.0 * diff_trips / trips_l) if trips_l else (100.0 if trips_c else 0)
        pct_rev = (100.0 * diff_rev / rev_l) if rev_l else (100.0 if rev_c else 0)
        row = {
            "month": month_ym,
            "country": country,
            "trips_legacy": trips_l,
            "trips_canonical": trips_c,
            "diff_trips": diff_trips,
            "diff_trips_pct": round(pct_trips, 2),
            "revenue_legacy": round(rev_l, 2),
            "revenue_canonical": round(rev_c, 2),
            "diff_revenue": round(diff_rev, 2),
            "diff_revenue_pct": round(pct_rev, 2),
        }
        row["inferred_cause"] = _infer_cause(row, legacy_agg, canonical_agg)
        rows.append(row)

    out_path = args.out or f"outputs/plan_vs_real_diff_analysis_{args.year}.csv"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"Análisis guardado en: {out_path}")
    print(f"Filas: {len(rows)}")


if __name__ == "__main__":
    main()
