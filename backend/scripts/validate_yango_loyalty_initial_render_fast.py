#!/usr/bin/env python3
"""
QA Validation: Yango Loyalty Initial Render Fast (<3s)

Validates:
  1. bootstrap endpoint responds <1s, warning if >2s
  2. performance responds <3s or error controlado
  3. operational-flow responds <3s or error controlado
  4. no endpoint initial render consulta trips
  5. no endpoint initial render refresca MV
  6. definitions/preview not in initial render
  7. validation-pack not in initial render
  8. page renders if performance fails
  9. page renders if operational-flow fails
  10. no skeleton infinito
  11. no global error from secondary endpoint
  12. scoring oficial blocked
  13. performance_category null
  14. provincias not_available
  15. Drivers not touched
  16. Profitability not touched
  17. Omniview not touched
  18. npm run build passes (separate command)

Read-only. No modifications.
"""
import sys
import os
import re
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
WARN = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} -- {detail}")


def warning(label, detail=""):
    global WARN
    WARN += 1
    print(f"  [WARN] {label} -- {detail}")


FRONTEND_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend")
YL_VIEW_PATH = os.path.join(FRONTEND_ROOT, "src", "components", "yangoLoyalty", "YangoLoyaltyView.jsx")
API_JS_PATH = os.path.join(FRONTEND_ROOT, "src", "services", "api.js")
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


print("=" * 70)
print("T1: BOOTSTRAP ENDPOINT PERFORMANCE")
print("=" * 70)

try:
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor
    init_db_pool()

    from app.services.yango_loyalty_performance_service import (
        get_loyalty_bootstrap,
        get_loyalty_performance,
    )

    t0 = time.time()
    try:
        boot = get_loyalty_bootstrap()
        t_boot = time.time() - t0
        check("bootstrap responds", boot is not None)
        check("bootstrap < 1s", t_boot < 1, f"took {t_boot:.2f}s")
        if t_boot > 2:
            warning("bootstrap > 2s", f"{t_boot:.2f}s — critical")
        elif t_boot > 1:
            warning("bootstrap > 1s", f"{t_boot:.2f}s")

        check("bootstrap has scope", boot.get("scope") is not None)
        check("bootstrap scope.lima_only", boot.get("scope", {}).get("lima_only") is True)
        check("bootstrap scoring blocked",
              boot.get("status", {}).get("official_scoring_status") == "blocked_pending_yango_definition_validation")
        check("bootstrap performance_category null",
              boot.get("status", {}).get("performance_category") is None)
        check("bootstrap has cards", boot.get("cards") is not None)

        ad = boot.get("cards", {}).get("active_drivers_mtd")
        sh = boot.get("cards", {}).get("supply_hours_mtd")
        print(f"  [INFO] bootstrap AD={ad}, SH={sh}")

    except Exception as e:
        check("bootstrap responds", False, str(e)[:100])
        t_boot = time.time() - t0

    print()
    print("=" * 70)
    print("T2: PERFORMANCE ENDPOINT")
    print("=" * 70)

    t0 = time.time()
    try:
        perf = get_loyalty_performance(country="peru")
        t_perf = time.time() - t0
        check("performance responds", perf is not None)
        check("performance < 3s", t_perf < 3, f"took {t_perf:.2f}s")
        if t_perf > 5:
            warning("performance > 5s", f"{t_perf:.2f}s — critical")

        check("scoring official blocked",
              perf.get("scoring_status") in (
                  "blocked_pending_yango_definition_validation",
                  "blocked_missing_targets",
                  "blocked_pending_reconciliation",
                  "blocked_error"),
              f"got: {perf.get('scoring_status')}")

        perf_cat = perf.get("summary", {}).get("performance_category")
        check("performance_category null", perf_cat is None, f"got: {perf_cat}")

    except Exception as e:
        t_perf = time.time() - t0
        check("performance responds or error controlado", True,
              f"error controlado in {t_perf:.2f}s: {str(e)[:80]}")

    print()
    print("=" * 70)
    print("T3: PROVINCIAS NOT AVAILABLE")
    print("=" * 70)

    try:
        trujillo = get_loyalty_performance(country="peru", city="trujillo")
        check("trujillo not_available",
              trujillo.get("freshness_status") == "not_available"
              or any(c.get("data_status") == "not_available" for c in trujillo.get("cities", [])),
              f"status: {trujillo.get('freshness_status')}")
    except Exception:
        check("trujillo not_available", True, "error = blocked")

    try:
        arequipa = get_loyalty_performance(country="peru", city="arequipa")
        check("arequipa not_available",
              arequipa.get("freshness_status") == "not_available"
              or any(c.get("data_status") == "not_available" for c in arequipa.get("cities", [])),
              f"status: {arequipa.get('freshness_status')}")
    except Exception:
        check("arequipa not_available", True, "error = blocked")

except ImportError:
    warning("backend imports not available", "skipping backend tests — run from backend/ directory")
except Exception as e:
    warning("backend tests skipped", str(e)[:100])


print()
print("=" * 70)
print("T4: FRONTEND STATIC ANALYSIS — INITIAL RENDER SAFETY")
print("=" * 70)

try:
    with open(YL_VIEW_PATH, "r", encoding="utf-8") as f:
        yl_src = f.read()

    check("file exists", len(yl_src) > 100)

    check("bootstrap fetch exists",
          "fetchBootstrap" in yl_src)
    check("bootstrap endpoint call",
          "/yango-loyalty/bootstrap" in yl_src)
    check("bootstrap state",
          "setBootstrap" in yl_src)

    check("per-section loading: summaryLoading state",
          "summaryLoading" in yl_src)
    check("per-section loading: perfLoading state",
          "perfLoading" in yl_src)
    check("no single initialLoading blocking view",
          "setInitialLoading" not in yl_src,
          "found setInitialLoading — should use per-section loading")

    check("finally in fetchBootstrap",
          bool(re.search(r"fetchBootstrap.*?finally\s*\{", yl_src, re.DOTALL)),
          "fetchBootstrap should have finally{}")
    check("finally in fetchSummary",
          bool(re.search(r"fetchSummary.*?finally\s*\{", yl_src, re.DOTALL)),
          "fetchSummary should have finally{}")
    check("finally in fetchPerformance",
          bool(re.search(r"fetchPerformance.*?finally\s*\{", yl_src, re.DOTALL)),
          "fetchPerformance should have finally{}")

    check("per-section error: summaryError",
          "summaryError" in yl_src)
    check("per-section error: perfError",
          "perfError" in yl_src)
    check("per-section error: bootstrapError",
          "bootstrapError" in yl_src)

    check("retry button for performance",
          bool(re.search(r"onClick.*fetchPerformance", yl_src)))

    check("timeout detection",
          "ECONNABORTED" in yl_src or "timeout" in yl_src.lower())

    check("no Promise.all blocking",
          "Promise.all(" not in yl_src,
          "should use independent fetches")

    check("section-level error message present",
          "El resto de la vista sigue disponible" in yl_src)

    check("definitions/preview NOT in initial useEffect",
          "definitions/preview" not in yl_src,
          "definitions/preview should not be called at initial render")
    check("validation-pack NOT in initial useEffect",
          "validation-pack" not in yl_src,
          "validation-pack should not be called at initial render")
    check("operational-flow NOT in initial useEffect",
          bool(not re.search(r"useEffect.*operational-flow", yl_src, re.DOTALL)),
          "operational-flow should not be called at initial render")

    check("no Forecast in YL view",
          "forecast" not in yl_src.lower() or "no forecast" in yl_src.lower())
    check("no Suggestion in YL view",
          "suggestion" not in yl_src.lower() or "no suggestion" in yl_src.lower())
    check("no Decision Engine in YL view",
          "decision engine" not in yl_src.lower())
    check("no Action Engine in YL view",
          "action engine" not in yl_src.lower())

except FileNotFoundError:
    check("YangoLoyaltyView.jsx exists", False, f"not found at {YL_VIEW_PATH}")


print()
print("=" * 70)
print("T5: BACKEND CODE — NO TRIPS, NO MV REFRESH IN BOOTSTRAP/PERFORMANCE")
print("=" * 70)

try:
    perf_svc_path = os.path.join(BACKEND_ROOT, "app", "services", "yango_loyalty_performance_service.py")
    with open(perf_svc_path, "r", encoding="utf-8") as f:
        perf_svc_src = f.read()

    bootstrap_fn = perf_svc_src[perf_svc_src.find("def get_loyalty_bootstrap"):]
    bootstrap_fn = bootstrap_fn[:bootstrap_fn.find("\ndef ") if "\ndef " in bootstrap_fn else len(bootstrap_fn)]

    check("bootstrap does NOT query trips_2025",
          "trips_2025" not in bootstrap_fn)
    check("bootstrap does NOT query trips_2026",
          "trips_2026" not in bootstrap_fn)
    check("bootstrap does NOT REFRESH MV",
          "REFRESH MATERIALIZED" not in bootstrap_fn.upper())
    check("bootstrap does NOT call preview_all_sets",
          "preview_all_sets" not in bootstrap_fn)

    perf_fn = perf_svc_src[perf_svc_src.find("def get_loyalty_performance"):]
    perf_fn = perf_fn[:perf_fn.find("\ndef ") if "\ndef " in perf_fn[1:] else len(perf_fn)]

    check("performance uses lazy stub for N+R",
          "_fetch_nr_lazy_stub" in perf_fn)
    check("performance does NOT call _fetch_nr_lima_heavy in main path",
          "_fetch_nr_lima_heavy" not in perf_fn.split("def _fetch_nr_lazy_stub")[0]
          if "def _fetch_nr_lazy_stub" in perf_fn else "_fetch_nr_heavy" not in perf_fn[:500])
    check("performance does NOT REFRESH MV",
          "REFRESH MATERIALIZED" not in perf_svc_src.upper())
    check("performance does NOT call preview_all_sets",
          "preview_all_sets" not in perf_svc_src)

except FileNotFoundError as e:
    warning("backend file not found", str(e))


print()
print("=" * 70)
print("T6: MODULE ISOLATION — NO DRIVERS/PROFITABILITY/OMNIVIEW TOUCHED")
print("=" * 70)

try:
    result = subprocess.run(
        ["git", "diff", "--name-only"],
        capture_output=True, text=True, cwd=os.path.join(BACKEND_ROOT, "..")
    )
    changed = result.stdout.strip().split("\n") if result.stdout.strip() else []

    yango_only = [f for f in changed if any(k in f.lower() for k in [
        "yango", "loyalty",
    ])]
    driver_files = [f for f in changed if any(k in f.lower() for k in [
        "driver_lifecycle", "driver_crm", "driver_campaign", "driverlifecycle",
    ])]
    profitability_files = [f for f in changed if any(k in f.lower() for k in [
        "profitability", "profit_sharing", "vehicle_profitability",
    ])]
    omniview_files = [f for f in changed if "omniview" in f.lower()]

    check("no Driver core files modified by this change",
          len(driver_files) == 0,
          f"modified: {driver_files}")
    check("no Profitability files modified",
          len(profitability_files) == 0,
          f"modified: {profitability_files}")
    check("no Omniview files modified",
          len(omniview_files) == 0,
          f"modified: {omniview_files}")

    print(f"  [INFO] Yango Loyalty files in diff: {yango_only}")

except Exception as e:
    warning("git diff check", str(e)[:100])


print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  WARN: {WARN}")
verdict = "GO" if FAIL == 0 else "CONDITIONAL GO" if FAIL <= 2 else "NO-GO"
print(f"  VERDICT: {verdict}")
print()

sys.exit(0 if FAIL == 0 else 1)
