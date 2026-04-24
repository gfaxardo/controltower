"""
build_decision_readiness.py — FASE DECISION READINESS

Genera el CSV canónico de decision readiness por KPI.

Columnas:
  kpi              Nombre semántico (ej. "trips_completed", "active_drivers")
  type             Naturaleza: additive | distinct | ratio
  decision_role    Rol: decision_ready | context_only | formula_only
  usable_for_alerts  True solo para KPIs decision_ready
  db_column        Columna real en las fact tables
  note             Nota operativa

Uso:
  python -m scripts.build_decision_readiness
  python -m scripts.build_decision_readiness --out /ruta/custom.csv

Salida:
  scripts/outputs/decision_readiness.csv
  (también genera decision_readiness.csv en el directorio de trabajo para
   compatibilidad con la spec del prompt)
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config.kpi_semantics import KPI_SEMANTICS  # noqa: E402

CSV_COLUMNS = [
    "kpi",
    "type",
    "decision_role",
    "usable_for_alerts",
    "db_column",
    "note",
]


def build_decision_readiness() -> list[dict]:
    rows = []
    for kpi, meta in KPI_SEMANTICS.items():
        rows.append({
            "kpi": kpi,
            "type": meta.get("type", ""),
            "decision_role": meta.get("decision_role", ""),
            "usable_for_alerts": meta.get("decision_role") == "decision_ready",
            "db_column": meta.get("db_column") or "",
            "note": meta.get("note") or "",
        })
    return rows


def write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in CSV_COLUMNS})


def main() -> int:
    p = argparse.ArgumentParser(description="Build decision_readiness.csv")
    p.add_argument("--out", type=str, default=None)
    args = p.parse_args()

    rows = build_decision_readiness()

    print("[decision-readiness] KPIs por rol:")
    by_role: dict[str, list[str]] = {}
    for r in rows:
        by_role.setdefault(r["decision_role"], []).append(r["kpi"])
    for role, kpis in by_role.items():
        print(f"  {role}: {kpis}")

    # Salida primaria: scripts/outputs/decision_readiness.csv
    primary = _HERE / "outputs" / "decision_readiness.csv"
    write_csv(rows, primary)
    print(f"[decision-readiness] CSV: {primary}")

    # Salida secundaria: argumento --out o directorio de trabajo
    if args.out:
        secondary = Path(args.out)
        write_csv(rows, secondary)
        print(f"[decision-readiness] CSV (custom): {secondary}")
    else:
        # cwd para compatibilidad con spec del prompt
        cwd_out = Path.cwd() / "decision_readiness.csv"
        write_csv(rows, cwd_out)
        print(f"[decision-readiness] CSV (cwd): {cwd_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
