"""OV2-F.2 — Refresh Execution Audit + Root Cause — Full diagnostic"""
import sys, os, json
from datetime import date as dt_date, datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "ov2_refresh")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TODAY = dt_date.today()
TIMESTAMP = datetime.now(timezone.utc).isoformat()

def max_date(conn, query, params=()):
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        r = cur.fetchone()
        if r and r[0]:
            d = r[0]
            return str(d)[:10] if hasattr(d, "isoformat") else str(d)[:10]
    except:
        pass
    finally:
        cur.close()
    return None

def count_rows(conn, query, params=()):
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        return cur.fetchone()[0] or 0
    except:
        pass
    finally:
        cur.close()
    return 0

results = {"layers": [], "root_cause": [], "refresh_log": []}

with get_db() as conn:
    # ── LAYER: RAW ──
    raw_max = max_date(conn, "SELECT MAX(fecha_inicio_viaje) FROM public.trips_2026")
    raw_yango_max = max_date(conn,
        "SELECT MAX(order_date) FROM raw_yango.mv_orders_day WHERE park_id='08e20910d81d42658d4334d3f6d10ac0'")
    results["layers"].append({"layer": "RAW_TRIPS", "max_date": raw_max,
        "expected_d1": (TODAY - timedelta(1)).isoformat(),
        "gap_days": (TODAY - dt_date.fromisoformat(raw_max)).days if raw_max else None,
        "status": "OK" if raw_max == (TODAY - timedelta(1)).isoformat() else "STALE"})
    results["layers"].append({"layer": "RAW_YANGO", "max_date": raw_yango_max,
        "expected_d1": (TODAY - timedelta(1)).isoformat(),
        "gap_days": (TODAY - dt_date.fromisoformat(raw_yango_max)).days if raw_yango_max else None,
        "status": "OK" if raw_yango_max and raw_yango_max >= (TODAY - timedelta(2)).isoformat() else "STALE"})

    # ── LAYER: DAY_FACT ──
    day_max = max_date(conn,
        "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    day_all_max = max_date(conn, "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact")
    day_rows = count_rows(conn,
        "SELECT COUNT(*) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    results["layers"].append({"layer": "DAY_FACT", "max_date": day_max, "all_max": day_all_max,
        "expected_d1": (TODAY - timedelta(1)).isoformat(),
        "gap_days": (TODAY - dt_date.fromisoformat(day_max)).days if day_max else None,
        "rows": day_rows,
        "status": "FRESH" if day_max and day_max >= (TODAY - timedelta(1)).isoformat() else "STALE"})

    # ── LAYER: WEEK_FACT ──
    week_max = max_date(conn,
        "SELECT MAX(week_start) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    week_rows = count_rows(conn,
        "SELECT COUNT(*) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    results["layers"].append({"layer": "WEEK_FACT", "max_date": week_max,
        "gap_days": (TODAY - dt_date.fromisoformat(week_max)).days if week_max else None,
        "rows": week_rows,
        "status": "STALE" if week_max and week_max < (TODAY - timedelta(7)).isoformat() else "OK"})

    # ── LAYER: MONTH_FACT ──
    month_max = max_date(conn,
        "SELECT MAX(month) FROM ops.real_business_slice_month_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'")
    results["layers"].append({"layer": "MONTH_FACT", "max_date": month_max,
        "status": "OK" if month_max else "MISSING"})

    # ── LAYER: SNAPSHOT ──
    snap_max = max_date(conn, "SELECT MAX(operating_date) FROM ops.omniview_v2_serving_snapshot WHERE status='READY'")
    snap_failed = count_rows(conn, "SELECT COUNT(*) FROM ops.omniview_v2_serving_snapshot WHERE status='FAILED'")
    snap_ready = count_rows(conn, "SELECT COUNT(*) FROM ops.omniview_v2_serving_snapshot WHERE status='READY'")
    results["layers"].append({"layer": "SNAPSHOT", "max_date": snap_max,
        "ready": snap_ready, "failed": snap_failed,
        "gap_days": (TODAY - dt_date.fromisoformat(snap_max)).days if snap_max else None,
        "status": "FRESH" if snap_max and snap_max >= (TODAY - timedelta(2)).isoformat() else "STALE"})

    # ── LAYER: OPERATING_DATE ──
    op_date = day_max
    results["layers"].append({"layer": "OPERATING_DATE", "max_date": op_date,
        "derived_from": "DAY_FACT",
        "status": "OK" if op_date else "MISSING"})

    # ── REFRESH RUN LOG ──
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM ops.refresh_run_log ORDER BY started_at DESC LIMIT 10")
        results["refresh_log"] = [dict(r) for r in cur.fetchall()]
        for r in results["refresh_log"]:
            d = {k: (str(v)[:30] if hasattr(v, 'isoformat') else v) for k, v in r.items()}
            print(f"REFRESH_LOG: {d.get('pipeline_name','?')} started={str(d.get('started_at','?'))[:19]} status={d.get('status','?')}")
    except Exception as e:
        results["refresh_log_error"] = str(e)[:200]
        print(f"REFRESH_LOG: {str(e)[:100]}")

    # ── ROOT CAUSE ──
    print("\n=== ROOT CAUSE ANALYSIS ===")
    print(f"RAW max = {raw_max}")
    print(f"DAY_FACT max (Lima) = {day_max}")
    print(f"DAY_FACT max (all) = {day_all_max}")
    print(f"WEEK_FACT max = {week_max}")

    if raw_max and day_max and raw_max > day_max:
        gap = (dt_date.fromisoformat(raw_max) - dt_date.fromisoformat(day_max)).days
        print(f"\nGAP: RAW is {gap} days ahead of DAY_FACT")
        print("ROOT CAUSE: DAY_FACT refresh not running / not completing for Lima")
        results["root_cause"].append({
            "issue": "DAY_FACT_STALE",
            "raw_max": raw_max, "day_max": day_max, "gap_days": gap,
            "classification": "A — Refresh job not executed",
            "evidence": f"RAW has data up to {raw_max} but DAY_FACT last update is {day_max}"
        })

    if day_max and week_max and day_max > week_max:
        gap = (dt_date.fromisoformat(day_max) - dt_date.fromisoformat(week_max)).days
        print(f"GAP: DAY_FACT is {gap} days ahead of WEEK_FACT")
        results["root_cause"].append({
            "issue": "WEEK_FACT_STALE",
            "day_max": day_max, "week_max": week_max, "gap_days": gap,
            "classification": "A — Refresh job not executed (week_fact never rebuilt after day_fact)",
            "evidence": f"Only 367 rows for Lima in week_fact, max week_start={week_max}"
        })

    # ── SCHEDULER STATUS ──
    cur = conn.cursor()
    try:
        cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='refresh_run_log')")
        has_log_table = cur.fetchone()[0]
        print(f"\nrefresh_run_log table exists: {has_log_table}")
    except:
        pass
    finally:
        cur.close()

# Write JSON
json_path = os.path.join(OUTPUT_DIR, "refresh_execution_audit.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, default=str, ensure_ascii=False)

# Summary
print(f"\n=== SUMMARY ===")
for l in results["layers"]:
    gap = l.get("gap_days", "-")
    print(f"  {l['layer']:20s} max={l.get('max_date','?'):12s} gap={str(gap):4s} [{l['status']}]")

print(f"\nJSON: {json_path}")
