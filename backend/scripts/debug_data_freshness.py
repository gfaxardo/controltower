#!/usr/bin/env python3
"""
PARTE 3 - Debug de freshness de datos operativos.

Imprime la fecha maxima en cada tabla/fact table relevante.
Identifica el cuello de botella: tabla base vs fact tables.

Uso:
  cd backend
  python scripts/debug_data_freshness.py
"""
from __future__ import annotations
import os
import sys
from datetime import date

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db.connection import get_db  # noqa: E402

TODAY = date.today()
results: list[dict] = []


def _q(sql: str, label: str) -> None:
    with get_db() as conn:
        try:
            cur = conn.cursor()
            cur.execute(sql)
            row = cur.fetchone()
            val = row[0] if row else None
            cur.close()
        except Exception as e:
            conn.rollback()
            print(f"  [ERR] {label:<52} ERROR: {e}")
            results.append({"label": label, "val": None, "lag": None, "flag": "ERR"})
            return

    if val is None:
        lag_str = "? (sin datos)"
        flag = "[!]"
        lag_days = None
    else:
        try:
            d = val.date() if hasattr(val, "date") else val
            lag_days = (TODAY - d).days
            lag_str = f"{lag_days}d lag"
            flag = "[OK]" if lag_days <= 1 else "[!!]"
        except Exception:
            lag_str = f"raw={val}"
            flag = "[?]"
            lag_days = None

    print(f"  {flag}  {label:<52} max={val}  ({lag_str})")
    results.append({"label": label, "val": str(val), "lag": lag_days, "flag": flag})


def main() -> int:
    print()
    print("=" * 70)
    print("  Data Freshness Debug")
    print(f"  today = {TODAY}")
    print("=" * 70)

    print()
    print("-- TABLA BASE DE VIAJES 2026 --------------------------------")
    _q("SELECT MAX(fecha_finalizacion)::date FROM public.trips_2026",
       "trips_2026.fecha_finalizacion")
    _q("SELECT MAX(fecha_finalizacion)::date FROM public.trips_2026 WHERE EXTRACT(YEAR FROM fecha_finalizacion)=2026",
       "trips_2026 (solo 2026)")

    print()
    print("-- FACTS real_business_slice --------------------------------")
    _q("SELECT MAX(trip_date)::date FROM ops.real_business_slice_day_fact",
       "real_business_slice_day_fact.trip_date")
    _q("SELECT MAX(week_start)::date FROM ops.real_business_slice_week_fact",
       "real_business_slice_week_fact.week_start")
    _q("SELECT MAX(month)::date FROM ops.real_business_slice_month_fact",
       "real_business_slice_month_fact.month")

    print()
    print("-- STAGING MVs LOB ------------------------------------------")
    _q("SELECT MAX(week_start)::date FROM ops.staging_bootstrap_mv_real_lob_week_v2",
       "staging_mv_real_lob_week_v2.week_start")
    _q("SELECT MAX(month)::date FROM ops.staging_bootstrap_mv_real_lob_month_v2",
       "staging_mv_real_lob_month_v2.month")

    print()
    print("-- S1-2026: SEMANA QUE CRUZA DIC2025 -> ENE2026 ------------")
    _q("""SELECT MAX(trip_date)::date FROM ops.real_business_slice_day_fact
          WHERE trip_date BETWEEN '2025-12-29' AND '2026-01-10'""",
       "bsn_day_fact (dic25-ene26 range)")
    _q("""SELECT COUNT(DISTINCT week_start)::text FROM ops.real_business_slice_week_fact
          WHERE week_start BETWEEN '2025-12-28' AND '2026-01-06'""",
       "bsn_week_fact distinct week_starts (S1-2026)")
    _q("""SELECT MIN(week_start)::date FROM ops.real_business_slice_week_fact
          WHERE EXTRACT(YEAR FROM week_start)=2025 AND EXTRACT(MONTH FROM week_start)=12""",
       "bsn_week_fact min_week_start dic2025")
    _q("""SELECT MIN(week_start)::date FROM ops.staging_bootstrap_mv_real_lob_week_v2
          WHERE EXTRACT(YEAR FROM week_start)=2025 AND EXTRACT(MONTH FROM week_start)=12""",
       "staging_lob_week min_week_start dic2025")
    _q("""SELECT COUNT(*)::text FROM public.trips_2026
          WHERE fecha_finalizacion BETWEEN '2025-12-29' AND '2026-01-10'""",
       "trips_2026 rows (dec25-jan10)")

    print()
    print("-- REAL FACTS solo 2026 ------------------------------------")
    _q("SELECT MAX(trip_date)::date FROM ops.real_business_slice_day_fact WHERE EXTRACT(YEAR FROM trip_date)=2026",
       "bsn_day_fact (solo 2026)")
    _q("SELECT MAX(week_start)::date FROM ops.real_business_slice_week_fact WHERE EXTRACT(YEAR FROM week_start)=2026",
       "bsn_week_fact (solo 2026)")

    # Detectar cuello de botella
    lags = {r["label"]: r["lag"] for r in results if r["lag"] is not None}
    print()
    print("=" * 70)
    print("  DIAGNOSTICO DE CUELLO DE BOTELLA:")

    trips_lag = lags.get("trips_2026.fecha_finalizacion", None)
    day_lag   = lags.get("real_business_slice_day_fact.trip_date", None)
    week_lag  = lags.get("real_business_slice_week_fact.week_start", None)

    if trips_lag is not None and day_lag is not None and trips_lag < day_lag:
        gap = day_lag - trips_lag
        print(f"  [!!] CUELLO DE BOTELLA: fact tables desactualizadas.")
        print(f"       trips_2026 tiene datos hasta hace {trips_lag}d,")
        print(f"       real_business_slice_day_fact solo hasta hace {day_lag}d.")
        print(f"       GAP = {gap} dias -> necesitas correr refresh de facts.")
        bottleneck = "FACT_TABLES"
    elif day_lag is not None and day_lag <= 1:
        print(f"  [OK] day_fact esta actualizada ({day_lag}d lag). Freshness OK.")
        bottleneck = "OK"
    else:
        print(f"  [?]  No se pudo determinar cuello de botella.")
        bottleneck = "UNKNOWN"

    s1_ok = any(r["label"] == "bsn_week_fact distinct week_starts (S1-2026)"
                and r["val"] not in (None, "", "0") for r in results)
    print()
    print(f"  S1-2026 en bsn_week_fact: {'[OK] SI hay data' if s1_ok else '[!!] NO hay data (bug iso-week)'}")
    print()
    print(f"  max lag trips_2026     : {trips_lag if trips_lag is not None else '?'}d")
    print(f"  max lag day_fact       : {day_lag if day_lag is not None else '?'}d")
    print(f"  max lag week_fact      : {week_lag if week_lag is not None else '?'}d")
    print(f"  bottleneck             : {bottleneck}")
    print("=" * 70)
    print()

    # Guardar en outputs
    out_dir = os.path.join(_BACKEND_ROOT, "scripts", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "freshness_debug.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Data Freshness Debug  today={TODAY}\n")
        f.write(f"bottleneck={bottleneck}  s1_ok={s1_ok}\n")
        for r in results:
            f.write(f"{r['flag']}  {r['label']}  max={r['val']}  lag={r['lag']}d\n")
    print(f"[OK] freshness log: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
