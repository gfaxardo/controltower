#!/usr/bin/env python3
"""
CLI: refresh incremental Omniview (day_fact + week_fact + month_fact)
para un rango de fechas.

CF-H1L.9: Modo atomico (default) — staging → validate → atomic swap.
El modo legacy (--legacy) ejecuta el refresh secuencial antiguo
y requiere flag explicito.

Uso:
  cd backend

  # Refrescar ultimo dia (atomico, default)
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-30 --end-date 2026-05-31

  # Refrescar mayo completo (atomico)
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-01 --end-date 2026-06-01

  # Solo day_fact (atomico)
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-30 --end-date 2026-05-31 --grain day

  # Modo legacy (no atomico, solo debug)
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-06-01 --end-date 2026-06-02 --legacy

  # Forzar rango largo (>45 dias, atomico)
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-01-01 --end-date 2026-06-01 --force

  # Dry-run (valida staging sin escribir produccion)
  python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-30 --end-date 2026-05-31 --dry-run

Salida: JSON con resultados por grain, duration, rows, run_id.
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
    refresh_omniview_real_slice_family_atomic,
)


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="CF-H1I/CF-H1L.9 Atomic Omniview Refresh"
    )
    ap.add_argument("--start-date", required=True, help="Fecha inicio (inclusive). YYYY-MM-DD.")
    ap.add_argument("--end-date", required=True, help="Fecha fin (exclusive). YYYY-MM-DD.")
    ap.add_argument("--grain", default="all", choices=["day", "week", "month", "all"],
                    help="Grains a refrescar (default: all)")
    ap.add_argument("--force", action="store_true",
                    help="Permite rangos > 45 dias.")
    ap.add_argument("--legacy", action="store_true",
                    help="Usar refresh secuencial antiguo (no atomico). SOLO DEBUG.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validar staging sin escribir produccion.")
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
        print(f"Error: rango de {days} dias excede el limite de seguridad (45). Use --force.")
        return 1

    grains = ["day", "week", "month"] if args.grain == "all" else [args.grain]

    if args.legacy:
        print(f"WARNING: usando refresh SECUENCIAL legacy (NO atomico). Para debug solamente.",
              flush=True)
        if args.dry_run:
            print("Error: --dry-run no soportado en modo legacy.")
            return 1
        try:
            with get_db() as conn:
                cur = conn.cursor()
                out = refresh_omniview_incremental(start_date, end_date, cur, conn, grains)
                cur.close()
            print(json.dumps(out, indent=2, default=str))
            if out.get("error"):
                return 1
            all_ok = all(out.get(g, {}).get("ok", True) for g in grains)
            return 0 if all_ok else 1
        except Exception as e:
            print(f"Error: {e}")
            return 1

    # ── Modo atomico (default) ──
    mode_label = "DRY-RUN" if args.dry_run else "ATOMIC"
    print(f"CF-H1L.9 {mode_label} Refresh: {start_date} -> {end_date} grains={grains}", flush=True)

    try:
        with get_db() as conn:
            if args.dry_run:
                from app.services.business_slice_incremental_load import (
                    _ensure_staging_tables, _ensure_audit_table,
                    _populate_staging_day, _populate_staging_week, _populate_staging_month,
                    _validate_staging_family, _cleanup_staging,
                )
                cur = conn.cursor()
                _ensure_staging_tables(cur)
                _ensure_audit_table(cur)
                conn.commit()
                staging = {}
                if "day" in grains:
                    staging["day"] = _populate_staging_day(cur, start_date, end_date)
                if "week" in grains:
                    staging["week"] = _populate_staging_week(cur, start_date, end_date)
                if "month" in grains:
                    staging["month"] = _populate_staging_month(cur, start_date, end_date)
                val_errors = _validate_staging_family(cur, staging, start_date, end_date)
                _cleanup_staging(cur)
                conn.commit()
                cur.close()
                out = {
                    "ok": len(val_errors) == 0,
                    "mode": "dry_run",
                    "start_date": str(start_date), "end_date": str(end_date),
                    "days": days,
                    "staging": staging,
                    "validation_errors": val_errors,
                }
                print(json.dumps(out, indent=2, default=str))
                return 0 if out["ok"] else 1
            else:
                out = refresh_omniview_real_slice_family_atomic(conn, start_date, end_date, grains)
                print(json.dumps(out, indent=2, default=str))
                return 0 if out.get("ok") else 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
