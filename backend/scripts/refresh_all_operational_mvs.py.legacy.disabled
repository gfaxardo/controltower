#!/usr/bin/env python3
"""
PARTE 3.3 — Refresh maestro de todas las MVs / fact-tables operativas.

Actualiza (en orden):
  1. ops.real_business_slice_day_fact     (via load_business_slice_day_for_month)
  2. ops.real_business_slice_week_fact    (via load_business_slice_week_for_month)
  3. ops.real_business_slice_month_fact   (via load_business_slice_month_for_month)

Para el mes anterior y el mes actual (ventana operativa standard).

Uso:
  cd backend
  python scripts/refresh_all_operational_mvs.py

Automatizacion:
  # Opcion A — cron (Linux/Mac):
  # 0 * * * * cd /path/to/backend && python scripts/refresh_all_operational_mvs.py >> /var/log/yego_refresh.log 2>&1
  #
  # Opcion B — FastAPI background task (ver app/routers/ops.py endpoint /ops/real/refresh)
"""
from __future__ import annotations
import os
import sys
import time
from datetime import date

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.services.business_slice_real_refresh_job import run_business_slice_real_refresh_job  # noqa: E402


def main() -> int:
    print()
    print("=" * 60)
    print("  Refresh All Operational MVs / Fact Tables")
    print(f"  timestamp = {date.today()}")
    print("=" * 60)

    t0 = time.perf_counter()

    print("\n[->] Iniciando refresh day_fact + week_fact (meses anterior y actual)...")
    result = run_business_slice_real_refresh_job(force=True)
    elapsed = time.perf_counter() - t0

    ok = result.get("ok", False)
    skipped = result.get("skipped", False)
    errors = result.get("errors") or []
    months = result.get("months") or []
    log_lines = result.get("log") or []
    freshness = result.get("freshness_after") or {}

    print(f"\n  status     : {'OK' if ok else 'FAIL'}")
    print(f"  skipped    : {skipped}")
    print(f"  months     : {months}")
    print(f"  duration_s : {result.get('duration_seconds', elapsed):.1f}")

    if log_lines:
        print(f"\n  Detalle por mes:")
        for line in log_lines:
            print(f"    {line}")

    if errors:
        print(f"\n  Errores ({len(errors)}):")
        for e in errors:
            print(f"    {e.get('month')}: {e.get('error')}")

    if freshness:
        day_f  = (freshness.get("day_fact") or {}).get("max_trip_date", "?")
        week_f = (freshness.get("week_fact") or {}).get("max_week_start", "?")
        month_f= (freshness.get("month_fact") or {}).get("max_month", "?")
        print(f"\n  Freshness after refresh:")
        print(f"    day_fact   max_trip_date : {day_f}")
        print(f"    week_fact  max_week_start: {week_f}")
        print(f"    month_fact max_month     : {month_f}")

        upstream_max = (result.get("upstream_preflight") or {}).get("max_event_date", "?")
        before_max   = result.get("before_max_trip_date", "?")
        print(f"\n  upstream max_event_date   : {upstream_max}")
        print(f"  day_fact before refresh   : {before_max}")

    print()
    print("=" * 60)
    print(f"  RESULTADO : {'OK - fact tables actualizadas' if ok else 'FAIL - revisar errores'}")
    print("=" * 60)
    print()
    print("  INSTRUCCIONES DE AUTOMATIZACION:")
    print()
    print("  Opcion A — Cron (Linux/Mac):")
    print("    0 * * * * cd /backend && python scripts/refresh_all_operational_mvs.py >> /var/log/yego_refresh.log 2>&1")
    print()
    print("  Opcion B — FastAPI background task (ya existe):")
    print("    POST /ops/real/refresh")
    print()
    print("  El refresh via API esta disponible en el endpoint /ops/real/refresh.")
    print("  APScheduler en app/main.py puede correrlo automaticamente cada 1h.")
    print()

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
