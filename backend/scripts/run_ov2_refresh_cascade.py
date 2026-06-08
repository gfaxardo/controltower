"""OV2-F.4 — Automatic waterfall cascade orchestrator
Runs the full chain: bridge → day → week → month → snapshot → certify
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

def run_step(name, cmd, timeout=300):
    t0 = time.time()
    result = subprocess.run(cmd, cwd=BACKEND, capture_output=True, text=True, timeout=timeout)
    elapsed = round((time.time() - t0) * 1000)
    ok = result.returncode == 0
    output = (result.stdout or "")[:500] + (result.stderr or "")[:500]
    return {"name": name, "ok": ok, "ms": elapsed, "output": output, "returncode": result.returncode}

def max_date(cur, query, params=()):
    cur.execute(query, params)
    r = cur.fetchone()
    if r and r[0]:
        return str(r[0])[:10] if hasattr(r[0], "isoformat") else str(r[0])[:10]
    return None

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.confirm:
        print("Use --dry-run or --confirm"); return 1

    mode = "DRY-RUN" if args.dry_run else "CONFIRMED"
    print(f"OV2-F.4 REFRESH CASCADE ({mode})")
    print(f"  D-1={D1}  D-2={D2}")

    log = []
    precheck = {"raw_ok": False, "bridge_ok": False, "db_ok": False}

    with get_db() as conn:
        cur = conn.cursor()
        try:
            # ── PRECHECK ──
            cur.execute("SELECT 1")
            precheck["db_ok"] = True
            raw_max = max_date(cur, "SELECT MAX(fecha_inicio_viaje) FROM public.trips_2026")
            precheck["raw_ok"] = raw_max and raw_max >= D2
            precheck["raw_max"] = raw_max
            bridge_max = max_date(cur, "SELECT MAX(activity_date) FROM ops.driver_day_slice_fact WHERE country=%s AND city=%s", ("peru", "lima"))
            precheck["bridge_ok"] = bridge_max and bridge_max >= D2
            precheck["bridge_max"] = bridge_max
            print(f"  PRECHECK: raw={raw_max} bridge={bridge_max} db={'OK' if precheck['db_ok'] else 'FAIL'}")
            log.append({"name": "precheck", "ok": precheck["db_ok"], "raw_max": raw_max, "bridge_max": bridge_max})
        finally:
            cur.close()

    if not precheck["db_ok"]:
        print("ABORT: DB not available")
        return 2

    python = sys.executable
    results = []

    # ── Step 1: Bridge incremental ──
    if precheck["raw_ok"] and D2 > (bridge_max or "2020-01-01"):
        r = run_step("bridge_update",
            [python, "-m", "scripts.build_driver_bridge_direct",
             "--date-from", D2, "--date-to", D1, "--batch-days", "1",
             "--dry-run" if args.dry_run else "--confirm"], timeout=180)
        results.append(r)
        print(f"  Bridge: {'OK' if r['ok'] else 'FAIL'} ({r['ms']}ms)")

    # ── Step 2: Week rebuild ──
    before_week = max_date if max_date else None
    r = run_step("week_rebuild",
        [python, "-m", "scripts.rebuild_week_from_day_and_bridge",
         "--date-from", D2, "--date-to", D1,
         "--dry-run" if args.dry_run else "--confirm"], timeout=120)
    results.append(r)
    print(f"  Week: {'OK' if r['ok'] else 'FAIL'} ({r['ms']}ms)")

    # ── Step 3: Month rebuild ──
    month_from = f"{int(D1[:4])}-{int(D1[5:7]):02d}-01"
    r = run_step("month_rebuild",
        [python, "-m", "scripts.rebuild_month_from_day_and_bridge",
         "--date-from", month_from, "--date-to", D1,
         "--dry-run" if args.dry_run else "--confirm"], timeout=120)
    results.append(r)
    print(f"  Month: {'OK' if r['ok'] else 'FAIL'} ({r['ms']}ms)")

    # ── Step 4: Snapshot refresh ──
    r = run_step("snapshot_refresh",
        [python, "-m", "scripts.refresh_omniview_v2_snapshots",
         "--use-latest-closed-date",
         "--dry-run" if args.dry_run else "--confirm"], timeout=300)
    results.append(r)
    print(f"  Snapshot: {'OK' if r['ok'] else 'FAIL'} ({r['ms']}ms)")

    # ── Step 5: Certification ──
    r = run_step("certification",
        [python, "-m", "scripts.certify_ov2_refresh_chain"], timeout=60)
    results.append(r)
    print(f"  Certify: {'OK' if r['ok'] else 'FAIL'} ({r['ms']}ms)")

    # ── Step 6: Waterfall ──
    r = run_step("waterfall",
        [python, "-m", "scripts.validate_refresh_waterfall"], timeout=60)
    results.append(r)
    print(f"  Waterfall: {'OK' if r['ok'] else 'FAIL'} ({r['ms']}ms)")

    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    print(f"\nCASCADE COMPLETE: {passed}/{total} steps passed ({mode})")
    return 0 if passed == total else 1

if __name__ == "__main__":
    raise SystemExit(main())
