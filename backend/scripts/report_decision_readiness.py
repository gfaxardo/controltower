"""
FASE_VALIDATION_FIX — Report de Decision Readiness por KPI.

Genera una tabla con el estado de cada KPI respecto a su usabilidad
para decisiones ejecutivas en Omniview:

  decision_ready  : aditivo, comparable, permite drift alerts y priority scoring.
  scope_only      : semi_additive_distinct; leer solo dentro del mismo scope.
  formula_only    : ratio/derived_ratio; comparable por fórmula, no por suma.
  restricted      : no usar en decisiones cross-grain ni en alertas aditivas.

Columnas del CSV:
  kpi
  label
  aggregation_type
  comparable_across_grains
  allowed_for_cross_grain_decision
  allowed_for_drift_alerts
  allowed_for_priority_scoring
  validation_basis                  (daily_in_month | formula_internal | scope_max)
  decision_status                   (decision_ready | scope_only | formula_only | restricted)
  decision_note
  comparison_rule
  diagnostic_note
  recommended_ui_note

Uso:
  python -m scripts.report_decision_readiness
  python -m scripts.report_decision_readiness --out /ruta/personalizada.csv

Salida:
  backend/scripts/outputs/decision_readiness_<timestamp>.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config.kpi_aggregation_rules import (  # noqa: E402
    OMNIVIEW_MATRIX_VISIBLE_KPIS,
    get_omniview_kpi_rule,
    get_kpi_decision_status,
    AGG_ADDITIVE,
    AGG_SEMI_ADDITIVE,
    AGG_NON_ADDITIVE_RATIO,
    AGG_DERIVED_RATIO,
)

CSV_COLUMNS = [
    "kpi",
    "label",
    "aggregation_type",
    "comparable_across_grains",
    "allowed_for_cross_grain_decision",
    "allowed_for_drift_alerts",
    "allowed_for_priority_scoring",
    "validation_basis",
    "decision_status",
    "decision_note",
    "comparison_rule",
    "diagnostic_note",
    "recommended_ui_note",
]

_VALIDATION_BASIS_MAP = {
    AGG_ADDITIVE: "daily_in_month",
    AGG_SEMI_ADDITIVE: "scope_max (daily_max)",
    AGG_NON_ADDITIVE_RATIO: "formula_internal",
    AGG_DERIVED_RATIO: "formula_internal",
}


def build_decision_readiness_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for kpi_key in OMNIVIEW_MATRIX_VISIBLE_KPIS:
        try:
            r = get_omniview_kpi_rule(kpi_key)
        except KeyError:
            continue

        agg = r.get("aggregation_type") or ""
        decision_status = get_kpi_decision_status(kpi_key)
        validation_basis = _VALIDATION_BASIS_MAP.get(agg, "unknown")

        rows.append({
            "kpi": kpi_key,
            "label": r.get("label") or "",
            "aggregation_type": agg,
            "comparable_across_grains": bool(r.get("comparable_across_grains")),
            "allowed_for_cross_grain_decision": bool(r.get("allowed_for_cross_grain_decision")),
            "allowed_for_drift_alerts": bool(r.get("allowed_for_drift_alerts")),
            "allowed_for_priority_scoring": bool(r.get("allowed_for_priority_scoring")),
            "validation_basis": validation_basis,
            "decision_status": decision_status,
            "decision_note": r.get("decision_note") or "",
            "comparison_rule": r.get("comparison_rule") or "",
            "diagnostic_note": r.get("diagnostic_note") or "",
            "recommended_ui_note": r.get("recommended_ui_note") or "",
        })
    return rows


def write_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in CSV_COLUMNS})


def print_summary(rows: List[Dict[str, Any]]) -> None:
    by_status: Dict[str, List[str]] = {}
    for r in rows:
        s = r["decision_status"]
        by_status.setdefault(s, []).append(r["kpi"])

    print("[decision-readiness] resumen por status:")
    for status in ("decision_ready", "scope_only", "formula_only", "restricted"):
        kpis = by_status.get(status, [])
        print(f"  {status}: {kpis}")


def main() -> int:
    p = argparse.ArgumentParser(description="FASE_VALIDATION_FIX — Decision Readiness Report")
    p.add_argument("--out", type=str, default=None)
    args = p.parse_args()

    rows = build_decision_readiness_rows()
    print_summary(rows)

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    out_path = Path(args.out) if args.out else (
        _HERE / "outputs" / f"decision_readiness_{ts}.csv"
    )
    write_csv(rows, out_path)
    print(f"[decision-readiness] CSV: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
