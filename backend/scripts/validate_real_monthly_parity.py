"""
Validación de paridad: Real mensual legacy (mv_real_trips_monthly) vs canónico (real_drill_dim_fact).
Ejecutar: python -m scripts.validate_real_monthly_parity [--year 2025] [--country PE]
Salida: tabla de diferencias, diagnóstico MATCH | MINOR_DIFF | MAJOR_DIFF.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Backend root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.plan_real_split_service import get_real_monthly as get_legacy
from app.services.canonical_real_monthly_service import get_real_monthly_canonical as get_canonical


def _to_key(row: dict) -> str:
    return str(row.get("period") or row.get("month") or "")


def _compare(
    legacy: list[dict],
    canonical: list[dict],
    tol_pct: float = 1.0,
    tol_abs_trips: int = 50,
) -> tuple[list[dict], str]:
    """
    Compara listas por period. Devuelve filas de comparación y diagnóstico.
    tol_pct: tolerancia porcentual para considerar MINOR_DIFF.
    tol_abs_trips: tolerancia absoluta en viajes para MATCH.
    """
    by_leg = {_to_key(r): r for r in legacy}
    by_can = {_to_key(r): r for r in canonical}
    all_periods = sorted(set(by_leg) | set(by_can))
    rows = []
    max_diff_pct = 0.0
    max_abs_trips = 0
    for period in all_periods:
        L = by_leg.get(period) or {}
        C = by_can.get(period) or {}
        trips_l = int(L.get("trips_real_completed") or 0)
        trips_c = int(C.get("trips_real_completed") or 0)
        rev_l = float(L.get("revenue_real_yego") or 0)
        rev_c = float(C.get("revenue_real_yego") or 0)
        dr_l = int(L.get("active_drivers_real") or 0)
        dr_c = int(C.get("active_drivers_real") or 0)
        diff_trips = abs(trips_c - trips_l)
        diff_rev = abs(rev_c - rev_l)
        diff_dr = abs(dr_c - dr_l)
        pct_trips = (100.0 * diff_trips / trips_l) if trips_l else (100.0 if trips_c else 0)
        pct_rev = (100.0 * diff_rev / rev_l) if rev_l else (100.0 if rev_c else 0)
        if diff_trips > max_abs_trips:
            max_abs_trips = diff_trips
        if pct_trips > max_diff_pct:
            max_diff_pct = pct_trips
        if pct_rev > max_diff_pct:
            max_diff_pct = pct_rev
        rows.append({
            "period": period,
            "trips_legacy": trips_l,
            "trips_canonical": trips_c,
            "diff_trips": diff_trips,
            "diff_trips_pct": round(pct_trips, 2),
            "revenue_legacy": round(rev_l, 2),
            "revenue_canonical": round(rev_c, 2),
            "diff_revenue": round(diff_rev, 2),
            "diff_revenue_pct": round(pct_rev, 2),
            "drivers_legacy": dr_l,
            "drivers_canonical": dr_c,
            "diff_drivers": diff_dr,
        })
    if max_abs_trips <= tol_abs_trips and max_diff_pct <= tol_pct:
        diagnosis = "MATCH"
    elif max_diff_pct <= 5.0:
        diagnosis = "MINOR_DIFF"
    else:
        diagnosis = "MAJOR_DIFF"
    return rows, diagnosis


def main() -> None:
    ap = argparse.ArgumentParser(description="Paridad Real mensual legacy vs canónico")
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--country", type=str, default=None)
    ap.add_argument("--tol-pct", type=float, default=1.0)
    ap.add_argument("--tol-abs-trips", type=int, default=50)
    args = ap.parse_args()
    try:
        legacy = get_legacy(country=args.country, year=args.year)
        canonical = get_canonical(country=args.country, year=args.year)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    rows, diagnosis = _compare(
        legacy,
        canonical,
        tol_pct=args.tol_pct,
        tol_abs_trips=args.tol_abs_trips,
    )
    print("period;trips_legacy;trips_canonical;diff_trips;diff_trips_pct;revenue_legacy;revenue_canonical;diff_revenue;diff_revenue_pct;drivers_legacy;drivers_canonical;diff_drivers")
    for r in rows:
        print(
            f"{r['period']};{r['trips_legacy']};{r['trips_canonical']};{r['diff_trips']};{r['diff_trips_pct']};"
            f"{r['revenue_legacy']};{r['revenue_canonical']};{r['diff_revenue']};{r['diff_revenue_pct']};"
            f"{r['drivers_legacy']};{r['drivers_canonical']};{r['diff_drivers']}"
        )
    print("")
    print(f"DIAGNOSIS: {diagnosis}")
    print(f"Legacy periods: {len(legacy)} | Canonical periods: {len(canonical)}")


if __name__ == "__main__":
    main()
