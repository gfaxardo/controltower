#!/usr/bin/env python3
"""
CLI: refresh incremental Omniview (day_fact + week_fact + month_fact)
para un rango de fechas, usando consulta directa a RAW (sin vista enriquecida).

Uso:
  cd backend

  # Refrescar ultimo dia
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-30 --end-date 2026-05-31 --grain all

  # Refrescar mayo completo
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-01 --end-date 2026-06-01 --grain all

  # Solo day_fact
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-30 --end-date 2026-05-31 --grain day

  # Forzar rango largo (>45 dias)
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-01-01 --end-date 2026-06-01 --force

Salida: JSON con resultados por grain, duration, rows.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from app.services.business_slice_incremental_load import (
    refresh_omniview_incremental,
)


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="CF-H1I Incremental Omniview Refresh — bypass enriched view, direct RAW query"
    )
    ap.add_argument(
        "--start-date",
        required=True,
        help="Fecha inicio (inclusive). Formato YYYY-MM-DD.",
    )
    ap.add_argument(
        "--end-date",
        required=True,
        help="Fecha fin (exclusive). Formato YYYY-MM-DD.",
    )
    ap.add_argument(
        "--grain",
        default="all",
        choices=["day", "week", "month", "all"],
        help="Grains a refrescar (default: all)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Permite rangos > 45 dias (usa con precaucion).",
    )
    args = ap.parse_args()

    try:
        start_date = _parse_date(args.start_date)
        end_date = _parse_date(args.end_date)
    except ValueError as e:
        print(f"Error: formato de fecha invalido. Use YYYY-MM-DD. ({e})")
        return 1

    days = (end_date - start_date).days
    if days <= 0:
        print("Error: --end-date debe ser posterior a --start-date")
        return 1

    if days > 45 and not args.force:
        print(
            f"Error: rango de {days} dias excede el limite de seguridad (45). "
            "Use --force para continuar, o reduzca el rango."
        )
        return 1

    grains = ["day", "week", "month"] if args.grain == "all" else [args.grain]

    if args.force and days > 45:
        print(
            f"WARNING: refresh forzado de {days} dias. "
            f"Esto puede tardar varios minutos ({days} * ~5s/dia = ~{days * 5}s).",
            flush=True,
        )

    print(f"CF-H1I Incremental Refresh: {start_date} -> {end_date} grains={grains}")
    try:
        with get_db() as conn:
            cur = conn.cursor()
            out = refresh_omniview_incremental(start_date, end_date, cur, conn, grains)
            cur.close()
        print(json.dumps(out, indent=2, default=str))
        if out.get("error"):
            return 1
        all_ok = all(
            out.get(g, {}).get("ok", True)
            for g in grains
        )
        return 0 if all_ok else 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
