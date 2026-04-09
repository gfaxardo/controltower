#!/usr/bin/env python3
"""
Test de performance: mide tiempos de respuesta de los endpoints daily/weekly
usando fact vs fallback.

cd backend && python -m scripts._test_endpoint_performance
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import init_db_pool
from app.services.business_slice_service import (
    get_business_slice_daily,
    get_business_slice_weekly,
    _fact_table_has_data,
    FACT_DAILY, FACT_WEEKLY,
)
from app.db.connection import get_db


def measure(label, fn, **kwargs):
    t0 = time.perf_counter()
    try:
        result = fn(**kwargs)
        if isinstance(result, tuple) and len(result) >= 1 and isinstance(result[0], list):
            result = result[0]
        dt = time.perf_counter() - t0
        n = len(result) if isinstance(result, list) else "?"
        rev_ok = sum(1 for r in result if r.get("revenue_yego_net") is not None) if isinstance(result, list) else "?"
        print(f"  {label}: {dt:.2f}s | {n} filas | rev_ok={rev_ok}", flush=True)
        return result, dt
    except Exception as e:
        dt = time.perf_counter() - t0
        print(f"  {label}: ERROR en {dt:.2f}s | {e}", flush=True)
        return None, dt


def main():
    init_db_pool()
    
    print("\n=== FACT TABLE STATUS ===", flush=True)
    with get_db() as conn:
        for table, col in [(FACT_DAILY, "trip_date"), (FACT_WEEKLY, "week_start")]:
            has_any = _fact_table_has_data(conn, table, col)
            has_2026 = _fact_table_has_data(conn, table, col, year=2026)
            has_2026_03 = _fact_table_has_data(conn, table, col, year=2026, month=3) if "trip_date" in col else None
            print(f"  {table}: any={has_any} | 2026={has_2026} | 2026-03={has_2026_03}", flush=True)

    print("\n=== DAILY PERFORMANCE (fact path only) ===", flush=True)
    measure("daily(year=2026, month=3)", get_business_slice_daily, year=2026, month=3)
    measure("daily(year=2026, month=3, country=peru)", get_business_slice_daily, year=2026, month=3, country="peru")

    print("\n=== WEEKLY PERFORMANCE (fact path only) ===", flush=True)
    measure("weekly(year=2026)", get_business_slice_weekly, year=2026)
    measure("weekly(year=2026, country=colombia)", get_business_slice_weekly, year=2026, country="colombia")

    print("\n=== NOTA: weekly/daily solo usan facts; no hay fallback a resolved ===", flush=True)
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
