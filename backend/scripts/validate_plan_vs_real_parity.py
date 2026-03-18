"""
Validación de paridad: Plan vs Real legacy vs canónico (real desde v_trips_real_canon).

Compara agregado por (period_date, country): sum(trips_real), sum(revenue_real).
Ejecutar: python -m scripts.validate_plan_vs_real_parity [--year 2025] [--country pe|co] [--out plan_vs_real_parity.csv]

Criterio: MATCH → OK; MINOR_DIFF → OK documentado; MAJOR_DIFF → STOP.
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
    """Agrupa por (month_ym, country) y suma trips_real, revenue_real."""
    agg: dict[tuple[str, str], dict] = defaultdict(lambda: {"trips_real": 0, "revenue_real": 0.0})
    for r in rows:
        period = r.get("period_date")
        month_ym = period.strftime("%Y-%m") if period else ""
        country = (r.get("country") or "").strip().lower() or "global"
        key = (month_ym, country)
        agg[key]["trips_real"] += int(r.get("trips_real") or 0)
        agg[key]["revenue_real"] += float(r.get("revenue_real") or 0)
    return dict(agg)


def _compare(
    legacy_agg: dict[tuple[str, str], dict],
    canonical_agg: dict[tuple[str, str], dict],
    tol_pct: float = 1.0,
    tol_abs_trips: int = 50,
) -> tuple[list[dict], str]:
    all_keys = sorted(set(legacy_agg) | set(canonical_agg))
    rows = []
    max_diff_pct = 0.0
    max_abs_trips = 0
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
        if diff_trips > max_abs_trips:
            max_abs_trips = diff_trips
        if pct_trips > max_diff_pct:
            max_diff_pct = pct_trips
        if pct_rev > max_diff_pct:
            max_diff_pct = pct_rev
        rows.append({
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
        })
    if max_abs_trips <= tol_abs_trips and max_diff_pct <= tol_pct:
        diagnosis = "MATCH"
    elif max_diff_pct <= 5.0:
        diagnosis = "MINOR_DIFF"
    else:
        diagnosis = "MAJOR_DIFF"
    return rows, diagnosis


def main() -> None:
    ap = argparse.ArgumentParser(description="Paridad Plan vs Real legacy vs canónico (real)")
    ap.add_argument("--year", type=int, default=None, help="Año a filtrar (ej. 2025); si no se pasa, se usan todos los meses disponibles")
    ap.add_argument("--country", type=str, default=None, help="Filtrar país (pe, co); si no se pasa, global + pe + co")
    ap.add_argument("--out", type=str, default=None, help="Ruta CSV de salida (evidencia)")
    ap.add_argument("--tol-pct", type=float, default=1.0)
    ap.add_argument("--tol-abs-trips", type=int, default=50)
    args = ap.parse_args()

    try:
        legacy = get_plan_vs_real_monthly(country=args.country, use_canonical=False)
        canonical = get_plan_vs_real_monthly(country=args.country, use_canonical=True)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    legacy_agg = _aggregate_by_month_country(legacy)
    canonical_agg = _aggregate_by_month_country(canonical)

    if args.year:
        legacy_agg = {k: v for k, v in legacy_agg.items() if k[0].startswith(str(args.year))}
        canonical_agg = {k: v for k, v in canonical_agg.items() if k[0].startswith(str(args.year))}

    rows, diagnosis = _compare(
        legacy_agg,
        canonical_agg,
        tol_pct=args.tol_pct,
        tol_abs_trips=args.tol_abs_trips,
    )

    fieldnames = ["month", "country", "trips_legacy", "trips_canonical", "diff_trips", "diff_trips_pct",
                  "revenue_legacy", "revenue_canonical", "diff_revenue", "diff_revenue_pct"]
    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            w.writeheader()
            w.writerows(rows)
        print(f"Evidencia guardada en: {args.out}")

    print("month;country;trips_legacy;trips_canonical;diff_trips;diff_trips_pct;revenue_legacy;revenue_canonical;diff_revenue;diff_revenue_pct")
    for r in rows:
        print(
            f"{r['month']};{r['country']};{r['trips_legacy']};{r['trips_canonical']};{r['diff_trips']};{r['diff_trips_pct']};"
            f"{r['revenue_legacy']};{r['revenue_canonical']};{r['diff_revenue']};{r['diff_revenue_pct']}"
        )
    print("")
    print(f"DIAGNOSIS: {diagnosis}")
    print(f"Legacy cells: {len(legacy_agg)} | Canonical cells: {len(canonical_agg)} | Rows compared: {len(rows)}")


if __name__ == "__main__":
    main()
