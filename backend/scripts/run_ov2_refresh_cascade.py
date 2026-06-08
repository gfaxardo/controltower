"""OV2-G.2 — Automatic waterfall cascade with OUTCOME-BASED monitoring
Tracks before/after advancement per layer. Logs to ops.refresh_advancement_log.
Usage:
  python -m scripts.run_ov2_refresh_cascade --dry-run
  python -m scripts.run_ov2_refresh_cascade --confirm
"""
import sys, os, subprocess, json, time
from datetime import date as dt_date, datetime, timezone, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = dt_date.today()
D1 = (TODAY - timedelta(days=1)).isoformat()
D2 = (TODAY - timedelta(days=2)).isoformat()
TIMESTAMP = datetime.now(timezone.utc).isoformat()
GIT_HASH = None
try:
    import subprocess as sp
    GIT_HASH = sp.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=BACKEND, stderr=sp.DEVNULL, text=True).strip()
except: pass

LAYERS = [
    {"name": "driver_bridge", "pipeline": "bridge_update", "table": "ops.driver_day_slice_fact", "col": "activity_date", "filter": "WHERE country='peru' AND city='lima'"},
    {"name": "week_fact", "pipeline": "week_rebuild", "table": "ops.real_business_slice_week_fact", "col": "week_start", "filter": "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"},
    {"name": "month_fact", "pipeline": "month_rebuild", "table": "ops.real_business_slice_month_fact", "col": "month", "filter": "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"},
    {"name": "day_fact", "pipeline": "day_rebuild", "table": "ops.real_business_slice_day_fact", "col": "trip_date", "filter": "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"},
]

def measure_before(cur, layer):
    cur.execute(f"SELECT MAX({layer['col']}) FROM {layer['table']} {layer['filter']}")
    mx = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM {layer['table']} {layer['filter']}")
    rows = cur.fetchone()[0]
    return str(mx)[:10] if mx else None, rows

def measure_after(cur, layer):
    return measure_before(cur, layer)

def log_advancement(cur, pipeline, layer_name, before_max, after_max, before_rows, after_rows, status, error=None):
    advanced = 1 if after_max and before_max != after_max else 0
    row_delta = (after_rows or 0) - (before_rows or 0)
    cur.execute("""
        INSERT INTO ops.refresh_advancement_log
            (pipeline_name, layer_name, started_at, finished_at,
             before_max_period, after_max_period, before_row_count, after_row_count,
             advanced_periods, advanced_rows, status, git_hash, error_message)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (pipeline, layer_name, TIMESTAMP, datetime.now(timezone.utc).isoformat(),
          before_max, after_max, before_rows, after_rows, advanced, row_delta,
          status, GIT_HASH, error))

def run_step(name, cmd, timeout=300):
    t0 = time.time()
    result = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True, timeout=timeout)
    elapsed = round((time.time() - t0) * 1000)
    ok = result.returncode == 0
    output = (result.stdout or "")[:300] + (result.stderr or "")[:300]
    return {"name": name, "ok": ok, "ms": elapsed, "output": output}

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.confirm:
        print("Use --dry-run or --confirm"); return 1

    mode = "DRY-RUN" if args.dry_run else "CONFIRMED"
    print(f"OV2-G.2 REFRESH CASCADE WITH ADVANCEMENT TRACKING ({mode})")

    python = sys.executable
    results = []

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
            db_ok = True
        except:
            db_ok = False
        finally:
            cur.close()

    if not db_ok:
        print("ABORT: DB not available"); return 2

    for layer in LAYERS:
        with get_db() as conn:
            cur = conn.cursor()
            try:
                before_max, before_rows = measure_before(cur, layer)

                if args.dry_run:
                    after_max, after_rows = before_max, before_rows
                    status = "SUCCESS_NO_CHANGE"
                    print(f"  {layer['name']:20s} before={before_max} rows={before_rows} [DRY-RUN]")
                else:
                    # Execute rebuild
                    if layer['name'] == 'driver_bridge':
                        r = run_step("bridge_update",
                            [python, "-m", "scripts.build_driver_bridge_direct",
                             "--date-from", D2, "--date-to", D1, "--batch-days", "1", "--confirm"], timeout=180)
                    elif layer['name'] == 'week_fact':
                        r = run_step("week_rebuild",
                            [python, "-m", "scripts.rebuild_week_from_day_and_bridge",
                             "--date-from", "2026-04-01", "--date-to", D1, "--confirm"], timeout=120)
                    elif layer['name'] == 'month_fact':
                        r = run_step("month_rebuild",
                            [python, "-m", "scripts.rebuild_month_from_day_and_bridge",
                             "--date-from", "2026-06-01", "--date-to", D1, "--confirm"], timeout=120)
                    elif layer['name'] == 'day_fact':
                        r = run_step("day_rebuild",
                            [python, "-m", "scripts.rebuild_day_from_bridge",
                             "--date-from", D2, "--date-to", D1, "--confirm"], timeout=120)

                    after_max, after_rows = measure_after(cur, layer)
                    advanced = after_max and before_max != after_max
                    status = "SUCCESS_WITH_ADVANCEMENT" if advanced else "SUCCESS_NO_CHANGE"
                    if not r["ok"]:
                        status = "FAIL"
                    log_advancement(cur, layer['pipeline'], layer['name'],
                                    before_max, after_max, before_rows, after_rows, status,
                                    r.get("output") if not r["ok"] else None)
                    conn.commit()
                    print(f"  {layer['name']:20s} {status:30s} before={before_max} after={after_max} rows={before_rows}->{after_rows}")

                results.append({"layer": layer['name'], "before": before_max, "after": after_max,
                                "rows_before": before_rows, "rows_after": after_rows, "status": status})
            except Exception as e:
                print(f"  {layer['name']:20s} ERROR: {str(e)[:100]}")
                results.append({"layer": layer['name'], "status": "FAIL", "error": str(e)[:200]})
            finally:
                cur.close()

    advanced = sum(1 for r in results if r.get("status") == "SUCCESS_WITH_ADVANCEMENT")
    total = len(results)
    print(f"\nCASCADE COMPLETE: {advanced}/{total} layers advanced ({mode})")
    return 0 if advanced > 0 or args.dry_run else 1

if __name__ == "__main__":
    raise SystemExit(main())
