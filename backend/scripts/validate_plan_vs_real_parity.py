"""
Validación de paridad: Plan vs Real legacy vs canónico (real desde v_trips_real_canon).

Compara agregado por (month, country): trips_real, revenue_real, trips_plan, revenue_plan.
Umbrales: MATCH < 0.1%%, MINOR_DIFF < 2%%, MAJOR_DIFF >= 2%%.

Ejecutar:
  python -m scripts.validate_plan_vs_real_parity --year 2025 --out outputs/plan_vs_real_parity_2025.csv
  python -m scripts.validate_plan_vs_real_parity --year 2025 --country pe --save-audit
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.plan_vs_real_service import get_plan_vs_real_monthly

# Umbrales (no negociables): MATCH < 0.1%, MINOR < 2%, MAJOR >= 2%
THRESHOLD_MATCH_PCT = 0.1
THRESHOLD_MINOR_PCT = 2.0


def _aggregate_by_month_country(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """Agrupa por (month_ym, country) y suma trips_real, revenue_real, trips_plan, revenue_plan."""
    agg: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "trips_real": 0, "revenue_real": 0.0,
        "trips_plan": 0, "revenue_plan": 0.0,
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
    return dict(agg)


def _classify_diagnosis(max_diff_pct: float) -> str:
    """MATCH < 0.1%, MINOR_DIFF < 2%, MAJOR_DIFF >= 2%."""
    if max_diff_pct < THRESHOLD_MATCH_PCT:
        return "MATCH"
    if max_diff_pct < THRESHOLD_MINOR_PCT:
        return "MINOR_DIFF"
    return "MAJOR_DIFF"


def _data_completeness(rows: list[dict], legacy_agg: dict, canonical_agg: dict) -> str:
    """FULL = sin celdas faltantes; PARTIAL = alguna canonical faltante; MISSING = huecos mayores."""
    missing_canonical = 0
    missing_legacy = 0
    for r in rows:
        key = (r["month"], r["country"])
        l = legacy_agg.get(key, {})
        c = canonical_agg.get(key, {})
        trips_l = l.get("trips_real", 0) or 0
        trips_c = c.get("trips_real", 0) or 0
        if trips_l > 0 and trips_c == 0:
            missing_canonical += 1
        if trips_c > 0 and trips_l == 0:
            missing_legacy += 1
    if missing_canonical > len(rows) // 2 or missing_legacy > len(rows) // 2:
        return "MISSING"
    if missing_canonical > 0 or missing_legacy > 0:
        return "PARTIAL"
    return "FULL"


def _compare(
    legacy_agg: dict[tuple[str, str], dict],
    canonical_agg: dict[tuple[str, str], dict],
) -> tuple[list[dict], str, float, str]:
    """Compara por (month, country). Devuelve (filas, diagnosis, max_diff_pct, data_completeness)."""
    all_keys = sorted(set(legacy_agg) | set(canonical_agg))
    rows = []
    max_diff_pct = 0.0
    for (month_ym, country) in all_keys:
        L = legacy_agg.get((month_ym, country), {"trips_real": 0, "revenue_real": 0.0, "trips_plan": 0, "revenue_plan": 0.0})
        C = canonical_agg.get((month_ym, country), {"trips_real": 0, "revenue_real": 0.0, "trips_plan": 0, "revenue_plan": 0.0})
        trips_l = L["trips_real"]
        trips_c = C["trips_real"]
        rev_l = L["revenue_real"]
        rev_c = C["revenue_real"]
        diff_trips = abs(trips_c - trips_l)
        diff_rev = abs(rev_c - rev_l)
        pct_trips = (100.0 * diff_trips / trips_l) if trips_l else (100.0 if trips_c else 0)
        pct_rev = (100.0 * diff_rev / rev_l) if rev_l else (100.0 if rev_c else 0)
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
            "trips_plan_legacy": L["trips_plan"],
            "trips_plan_canonical": C["trips_plan"],
            "revenue_plan_legacy": round(L["revenue_plan"], 2),
            "revenue_plan_canonical": round(C["revenue_plan"], 2),
        })
    diagnosis = _classify_diagnosis(max_diff_pct)
    data_completeness = _data_completeness(rows, legacy_agg, canonical_agg)
    return rows, diagnosis, max_diff_pct, data_completeness


def _save_audit(scope: str, diagnosis: str, max_diff_pct: float, data_completeness: str, details: dict) -> None:
    from app.db.connection import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ops.plan_vs_real_parity_audit
            (run_at, scope, diagnosis, max_diff_pct, data_completeness, details, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                datetime.now(timezone.utc),
                scope,
                diagnosis,
                round(max_diff_pct, 4),
                data_completeness,
                json.dumps(details) if details else None,
            ),
        )
        conn.commit()
        cur.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Paridad Plan vs Real legacy vs canónico")
    ap.add_argument("--year", type=int, default=None, help="Año a filtrar (ej. 2025)")
    ap.add_argument("--country", type=str, default=None, help="Filtrar país (pe, co); si no se pasa = global")
    ap.add_argument("--out", type=str, default=None, help="Ruta CSV de salida")
    ap.add_argument("--save-audit", action="store_true", help="Guardar resultado en ops.plan_vs_real_parity_audit")
    args = ap.parse_args()

    # Pasar year al servicio para empujar filtro a DB y evitar scan completo (performance).
    year_arg = args.year
    try:
        legacy = get_plan_vs_real_monthly(country=args.country, year=year_arg, use_canonical=False)
        canonical = get_plan_vs_real_monthly(country=args.country, year=year_arg, use_canonical=True)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    legacy_agg = _aggregate_by_month_country(legacy)
    canonical_agg = _aggregate_by_month_country(canonical)

    if args.year:
        legacy_agg = {k: v for k, v in legacy_agg.items() if k[0].startswith(str(args.year))}
        canonical_agg = {k: v for k, v in canonical_agg.items() if k[0].startswith(str(args.year))}

    rows, diagnosis, max_diff_pct, data_completeness = _compare(legacy_agg, canonical_agg)

    scope = (args.country or "global").strip().lower() or "global"
    details = {
        "legacy_cells": len(legacy_agg),
        "canonical_cells": len(canonical_agg),
        "rows_compared": len(rows),
        "max_diff_pct": round(max_diff_pct, 4),
    }
    if args.save_audit:
        _save_audit(scope, diagnosis, max_diff_pct, data_completeness, details)
        print(f"Audit guardado en ops.plan_vs_real_parity_audit (scope={scope})")

    fieldnames = [
        "month", "country",
        "trips_legacy", "trips_canonical", "diff_trips", "diff_trips_pct",
        "revenue_legacy", "revenue_canonical", "diff_revenue", "diff_revenue_pct",
        "trips_plan_legacy", "trips_plan_canonical", "revenue_plan_legacy", "revenue_plan_canonical",
    ]
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            w.writeheader()
            w.writerows(rows)
        print(f"Evidencia guardada en: {args.out}")

    print("month;country;trips_legacy;trips_canonical;diff_trips;diff_trips_pct;revenue_legacy;revenue_canonical;diff_revenue;diff_revenue_pct;trips_plan_legacy;trips_plan_canonical;revenue_plan_legacy;revenue_plan_canonical")
    for r in rows:
        print(
            f"{r['month']};{r['country']};{r['trips_legacy']};{r['trips_canonical']};{r['diff_trips']};{r['diff_trips_pct']};"
            f"{r['revenue_legacy']};{r['revenue_canonical']};{r['diff_revenue']};{r['diff_revenue_pct']};"
            f"{r['trips_plan_legacy']};{r['trips_plan_canonical']};{r['revenue_plan_legacy']};{r['revenue_plan_canonical']}"
        )
    print("")
    print(f"DIAGNOSIS: {diagnosis}")
    print(f"DATA_COMPLETENESS: {data_completeness}")
    print(f"max_diff_pct: {max_diff_pct:.4f}")
    print(f"Legacy cells: {len(legacy_agg)} | Canonical cells: {len(canonical_agg)} | Rows compared: {len(rows)}")


if __name__ == "__main__":
    main()
