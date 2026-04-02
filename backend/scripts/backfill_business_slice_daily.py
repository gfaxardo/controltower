#!/usr/bin/env python3
"""
Backfill controlado de day_fact + week_fact para Business Slice.

Pobla ops.real_business_slice_day_fact y ops.real_business_slice_week_fact
para un rango de meses. Usa la misma estrategia de materialización enriched
que el loader mensual.

Uso:
  cd backend

  # Un solo mes:
  python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-01

  # Rango:
  python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-03

  # Solo Peru:
  python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-03 --country peru

  # Dry-run (no escribe, solo muestra qué haría):
  python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-03 --dry-run

  # Sin week (solo day_fact):
  python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-03 --no-week

  # También refresca month_fact:
  python -m scripts.backfill_business_slice_daily --from-date 2026-01 --to-date 2026-03 --with-month
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db_audit
from app.services.business_slice_incremental_load import (
    load_business_slice_day_for_month,
    load_business_slice_month,
    load_business_slice_week_for_month,
    month_first_day,
)

_LOAD_TIMEOUT_MS = 7_200_000


def _parse_month(s: str) -> date:
    s = s.strip()
    if len(s) == 7 and s[4] == "-":
        y, m = int(s[:4]), int(s[5:7])
        return month_first_day(y, m)
    try:
        d = date.fromisoformat(s[:10])
        return month_first_day(d.year, d.month)
    except ValueError:
        pass
    raise ValueError(f"Formato invalido: {s!r} -- use YYYY-MM o YYYY-MM-DD")


def _iter_months(start: date, end: date):
    if start > end:
        start, end = end, start
    y, m = start.year, start.month
    ey, em = end.year, end.month
    while (y, m) <= (ey, em):
        yield month_first_day(y, m)
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Backfill controlado de day_fact + week_fact Business Slice"
    )
    ap.add_argument("--from-date", required=True, help="Mes inicio YYYY-MM")
    ap.add_argument("--to-date", required=True, help="Mes fin YYYY-MM (inclusive)")
    ap.add_argument("--country", default=None, help="Filtrar por país (futuro, no implementado aún)")
    ap.add_argument("--dry-run", action="store_true", help="No escribir, solo mostrar plan")
    ap.add_argument("--no-week", action="store_true", help="No calcular week_fact")
    ap.add_argument("--with-month", action="store_true", help="También recalcular month_fact")
    ap.add_argument(
        "--chunk-grain",
        choices=("country", "city"),
        default=None,
        help="Grano de chunks para el loader",
    )
    args = ap.parse_args()

    start = _parse_month(args.from_date)
    end = _parse_month(args.to_date)
    months = list(_iter_months(start, end))

    print(f"\n{'='*60}")
    print(f"  BACKFILL BUSINESS SLICE DAY/WEEK FACT")
    print(f"  Rango: {start} -> {end} ({len(months)} meses)")
    print(f"  Week: {'NO' if args.no_week else 'SI'}")
    print(f"  Month: {'SI' if args.with_month else 'NO'}")
    print(f"  Dry-run: {'SI' if args.dry_run else 'NO'}")
    print(f"{'='*60}\n")

    if args.dry_run:
        for mo in months:
            print(f"  [DRY-RUN] Procesaría mes: {mo}")
            if args.with_month:
                print(f"    -> month_fact DELETE + INSERT")
            print(f"    -> day_fact DELETE + INSERT")
            if not args.no_week:
                print(f"    -> week_fact rollup desde day_fact")
        print(f"\n  Total: {len(months)} meses. Ningún cambio realizado.")
        return 0

    t_global = time.perf_counter()
    total_day = 0
    total_week = 0
    total_month = 0
    errors = []

    with get_db_audit(timeout_ms=_LOAD_TIMEOUT_MS) as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = %s", (_LOAD_TIMEOUT_MS,))

        for i, mo in enumerate(months):
            print(f"\n--- [{i+1}/{len(months)}] Mes: {mo} ---")
            t_mo = time.perf_counter()

            try:
                if args.with_month:
                    nm = load_business_slice_month(cur, mo, conn, chunk_grain=args.chunk_grain)
                    total_month += nm
                    conn.commit()

                nd = load_business_slice_day_for_month(cur, mo, conn, chunk_grain=args.chunk_grain)
                total_day += nd
                conn.commit()

                nw = 0
                if not args.no_week:
                    nw = load_business_slice_week_for_month(cur, mo, conn)
                    total_week += nw
                    conn.commit()

                dt = time.perf_counter() - t_mo
                print(f"  OK: day={nd} week={nw} duration={dt:.1f}s")

            except Exception as e:
                errors.append((mo, str(e)))
                print(f"  ERROR en {mo}: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass

        cur.close()

    dt_global = time.perf_counter() - t_global
    print(f"\n{'='*60}")
    print(f"  RESUMEN BACKFILL")
    print(f"  Meses procesados: {len(months)}")
    if args.with_month:
        print(f"  month_fact total filas: {total_month}")
    print(f"  day_fact total filas: {total_day}")
    print(f"  week_fact total filas: {total_week}")
    print(f"  Errores: {len(errors)}")
    print(f"  Duración total: {dt_global:.1f}s")
    print(f"{'='*60}")

    if errors:
        print("\n  MESES CON ERROR:")
        for mo, err in errors:
            print(f"    {mo}: {err[:200]}")
        return 1

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR FATAL: {e}")
        raise SystemExit(2)
