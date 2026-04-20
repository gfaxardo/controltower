#!/usr/bin/env python3
"""
Validación operativa E2E: monthly vs weekly vs daily (conservación, drift, volatilidad).

Uso:
  cd backend && python scripts/validate_projection_operational_integrity.py \\
    --plan-version VERSION --year 2026 --month 1 [--out-dir scripts/outputs]

Salida: tabla ASCII + CSV con evidencia por ciudad/tajada/KPI.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Permitir import app.*
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.services.projection_expected_progress_service import (  # noqa: E402
    get_omniview_projection,
)

# Objetivos mínimos (país código FACT, ciudad normalizada, tajada snake_case)
DEFAULT_TARGETS: List[Tuple[str, str, str]] = [
    ("peru", "lima", "auto regular"),
    ("peru", "lima", "delivery"),
    ("peru", "lima", "cargo"),
    ("colombia", "cali", "auto regular"),
    ("colombia", "cali", "delivery"),
    ("colombia", "barranquilla", "auto regular"),
]

KPIS = ("trips_completed", "revenue_yego_net", "active_drivers")
PROJ_COL = {
    "trips_completed": "trips_completed_projected_total",
    "revenue_yego_net": "revenue_yego_net_projected_total",
    "active_drivers": "active_drivers_projected_total",
}


def _norm_city(s: str) -> str:
    return (s or "").strip().lower()


def _norm_slice(s: str) -> str:
    return (s or "").strip().lower()


def _find_rows(
    data: List[Dict[str, Any]],
    country: str,
    city: str,
    business_slice: str,
) -> List[Dict[str, Any]]:
    co = country.strip().lower()
    ci = _norm_city(city)
    bs = _norm_slice(business_slice)
    out = []
    for r in data:
        if (r.get("country") or "").strip().lower() != co:
            continue
        if _norm_city(str(r.get("city") or "")) != ci:
            continue
        if _norm_slice(str(r.get("business_slice_name") or "")) != bs:
            continue
        out.append(r)
    return out


def _monthly_plan(rows: List[Dict[str, Any]], kpi: str) -> Optional[float]:
    if not rows:
        return None
    val = rows[0].get(PROJ_COL[kpi])
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _sum_weekly(rows: List[Dict[str, Any]], kpi: str) -> float:
    col = PROJ_COL[kpi]
    return sum(float(r.get(col) or 0) for r in rows)


def _sum_daily(rows: List[Dict[str, Any]], kpi: str) -> float:
    col = PROJ_COL[kpi]
    return sum(float(r.get(col) or 0) for r in rows)


def _max_variation_pct(vals: List[float]) -> float:
    vals = [v for v in vals if v is not None and v >= 0]
    if len(vals) < 2:
        return 0.0
    avg = sum(vals) / len(vals)
    if avg <= 0:
        return 0.0
    return max(abs(v / avg - 1.0) * 100.0 for v in vals)


def _verdict(w_drift_pct: float, d_drift_pct: float, max_w: float, max_d: float) -> str:
    if w_drift_pct <= 0.2 and d_drift_pct <= 0.2:
        return "PASS"
    if w_drift_pct <= 1.0 or d_drift_pct <= 1.0:
        return "WARN"
    return "REVIEW"


def main() -> int:
    ap = argparse.ArgumentParser(description="Validación operativa proyección Omniview")
    ap.add_argument("--plan-version", required=True, help="Versión de plan")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--month", type=int, required=True)
    ap.add_argument("--out-dir", default=os.path.join(_BACKEND_ROOT, "scripts", "outputs"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    mon = get_omniview_projection(
        args.plan_version, grain="monthly", year=args.year, month=args.month
    )
    wk = get_omniview_projection(
        args.plan_version, grain="weekly", year=args.year, month=args.month
    )
    dy = get_omniview_projection(
        args.plan_version, grain="daily", year=args.year, month=args.month
    )

    data_m = mon.get("data") or []
    data_w = wk.get("data") or []
    data_d = dy.get("data") or []

    rows_out: List[Dict[str, Any]] = []
    resolved = 0

    for country, city, bsn in DEFAULT_TARGETS:
        alias = f"{city}/{bsn}"
        row_base = {
            "city": city,
            "tajada": bsn,
            "month": f"{args.year}-{args.month:02d}",
        }

        mrows = _find_rows(data_m, country, city, bsn)
        wrows = _find_rows(data_w, country, city, bsn)
        drows = _find_rows(data_d, country, city, bsn)

        if mrows or wrows or drows:
            resolved += 1

        for kpi in KPIS:
            mp = _monthly_plan(mrows, kpi)

            ws = _sum_weekly(wrows, kpi)
            ds = _sum_daily(drows, kpi)

            w_vals = [float(r.get(PROJ_COL[kpi]) or 0) for r in wrows]
            d_vals = [float(r.get(PROJ_COL[kpi]) or 0) for r in drows]

            w_drift_abs = abs((mp or 0) - ws) if mp is not None else None
            d_drift_abs = abs((mp or 0) - ds) if mp is not None else None
            w_drift_pct = (w_drift_abs / mp * 100) if mp and mp > 0 and w_drift_abs is not None else None
            d_drift_pct = (d_drift_abs / mp * 100) if mp and mp > 0 and d_drift_abs is not None else None

            max_w = _max_variation_pct(w_vals)
            max_d = _max_variation_pct(d_vals)

            fb = None
            conf = None
            if wrows:
                fb = wrows[0].get("trips_completed_fallback_level") if kpi == "trips_completed" else wrows[0].get(
                    f"{kpi}_fallback_level"
                )
                conf = wrows[0].get("trips_completed_curve_confidence") if kpi == "trips_completed" else wrows[0].get(
                    f"{kpi}_curve_confidence"
                )

            verdict = "NO_DATA"
            if mp is not None:
                verdict = _verdict(
                    w_drift_pct or 999,
                    d_drift_pct or 999,
                    max_w,
                    max_d,
                )

            rec = {
                **row_base,
                "kpi": kpi,
                "monthly_plan": mp,
                "weekly_sum": ws,
                "daily_sum": ds,
                "weekly_drift_abs": w_drift_abs,
                "weekly_drift_pct": w_drift_pct,
                "daily_drift_abs": d_drift_abs,
                "daily_drift_pct": d_drift_pct,
                "max_weekly_variation_pct": max_w,
                "max_daily_variation_pct": max_d,
                "fallback_level": fb,
                "confidence_status": conf,
                "verdict": verdict,
            }
            rows_out.append(rec)

    # Imprimir tabla
    print("=== Validación operativa proyección ===")
    print(f"plan_version={args.plan_version}  period={args.year}-{args.month:02d}")
    print(f"combinaciones con al menos una fila (de {len(DEFAULT_TARGETS)} objetivo): {resolved}")
    print()
    for r in rows_out:
        if r["verdict"] == "NO_DATA":
            continue
        print(
            f"{r['city']}/{r['tajada'][:16]:<16} | {r['kpi'][:16]:<16} | "
            f"m={r['monthly_plan']!s:>12} wΣ={r['weekly_sum']!s:>12} dΣ={r['daily_sum']!s:>12} | "
            f"wΔ%={r['weekly_drift_pct']!s:>6} dΔ%={r['daily_drift_pct']!s:>6} | {r['verdict']}"
        )

    csv_path = os.path.join(
        args.out_dir,
        f"projection_operational_integrity_{args.plan_version}_{args.year}_{args.month:02d}.csv",
    )
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        if rows_out:
            w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
            w.writeheader()
            w.writerows(rows_out)
    print()
    print(f"CSV escrito: {csv_path}")

    if resolved < 6:
        print()
        print(f"ADVERTENCIA: menos de 6 combinaciones ciudad/tajada con datos (actual={resolved}).")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
