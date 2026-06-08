"""OV2-F.2 — Refresh Failure Explainer: per-layer diagnosis"""
import sys, os
from datetime import date as dt_date, datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

TODAY = dt_date.today()
TIMESTAMP = datetime.now(timezone.utc).isoformat()

LAYERS = [
    {"layer": "RAW_TRIPS", "query": "SELECT MAX(fecha_inicio_viaje) FROM public.trips_2026",
     "grain": "day", "depends_on": None},
    {"layer": "DAY_FACT", "query": "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
     "grain": "day", "depends_on": "RAW_TRIPS"},
    {"layer": "WEEK_FACT", "query": "SELECT MAX(week_start) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
     "grain": "week", "depends_on": "DAY_FACT"},
    {"layer": "MONTH_FACT", "query": "SELECT MAX(month) FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
     "grain": "month", "depends_on": "WEEK_FACT"},
    {"layer": "SNAPSHOT", "query": "SELECT MAX(operating_date) FROM ops.omniview_v2_serving_snapshot WHERE status='READY'",
     "grain": "day", "depends_on": "DAY_FACT"},
    {"layer": "OPERATING_DATE", "query": None, "grain": "day", "depends_on": "DAY_FACT",
     "note": "Derives from DAY_FACT MAX(trip_date)"},
]

REMEDIATION = {
    "RAW_TRIPS": "Check trips_2026 upstream ingestion pipeline",
    "DAY_FACT": "Run: python -m scripts.refresh_omniview_real_slice_incremental --start-date Y-m-d --end-date Y-m-d --grain all --force",
    "WEEK_FACT": "Run week_fact refresh after day_fact is current. Consider staging in 30-day batches to avoid DB saturation.",
    "MONTH_FACT": "Run month_fact refresh after week_fact is current",
    "SNAPSHOT": "Run: python -m scripts.refresh_omniview_v2_snapshots --use-latest-closed-date --confirm",
    "OPERATING_DATE": "Auto-derives from DAY_FACT. Fix DAY_FACT first.",
}

print("=" * 70)
print("OV2-F.2 REFRESH FAILURE EXPLAINER")
print(f"Generated: {TIMESTAMP}")
print("=" * 70)

with get_db() as conn:
    previous_max = None
    for i, l in enumerate(LAYERS):
        print(f"\n--- Layer: {l['layer']} ({l['grain']}) ---")

        max_val = None
        if l["query"]:
            try:
                cur = conn.cursor()
                cur.execute(l["query"])
                r = cur.fetchone()
                cur.close()
                if r and r[0]:
                    max_val = str(r[0])[:10] if hasattr(r[0], "isoformat") else str(r[0])[:10]
            except Exception as e:
                print(f"  ERROR: {e}")
                max_val = None

        gap = None
        if max_val:
            try:
                gap = (TODAY - dt_date.fromisoformat(max_val[:10])).days
            except:
                pass

        stale = gap is not None and gap > 1
        status = "FRESH" if not stale else "STALE"

        print(f"  Last refresh: {max_val or 'MISSING'}")
        print(f"  Gap: {gap} days" if gap is not None else "  Gap: N/A")
        print(f"  Status: {status}")
        print(f"  Depends on: {l['depends_on'] or '(none)'}")
        print(f"  Remediation: {REMEDIATION.get(l['layer'], 'N/A')}")

        # Check if upstream is newer (waterfall)
        if previous_max and max_val:
            try:
                prev_d = dt_date.fromisoformat(previous_max[:10])
                curr_d = dt_date.fromisoformat(max_val[:10])
                if prev_d > curr_d:
                    print(f"  WATERFALL_BROKEN: {LAYERS[i-1]['layer']}={previous_max} > {l['layer']}={max_val}")
                elif prev_d == curr_d:
                    print(f"  WATERFALL: OK (equal)")
                else:
                    print(f"  WATERFALL: OK ({LAYERS[i-1]['layer']} > {l['layer']})")
            except:
                pass

        previous_max = max_val

print(f"\n{'=' * 70}")
print("Done.")
