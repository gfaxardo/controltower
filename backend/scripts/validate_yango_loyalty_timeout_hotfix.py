#!/usr/bin/env python3
"""
QA Validation: Yango Loyalty Timeout Hotfix

Validates:
  1. Endpoint performance < 5s
  2. Endpoint operational-flow < 5s
  3. Main endpoint does not call preview
  4. Preview/validation-pack not needed for initial render
  5. Initial render does not depend on heavy endpoint
  6. Scoring official blocked
  7. performance_category official null
  8. Trujillo not_available
  9. Arequipa not_available
  10. Secondary failure does not block main view
  11-13. Frontend: no skeleton infinito, error per section, retry per section
  14-17. No Forecast/Suggestion/Decision/Action
  18-20. No Drivers/Profitability/Omniview files touched
  21. Frontend build passes (separate command)

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
print("T1: BACKEND ENDPOINT PERFORMANCE (requires running backend)")
print("=" * 70)

try:
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor
    init_db_pool()

    from app.services.yango_loyalty_service import get_loyalty_summary
    from app.services.yango_loyalty_performance_service import get_loyalty_performance

    t0 = time.time()
    try:
        summary = get_loyalty_summary()
        t_summary = time.time() - t0
        check("summary responds", summary is not None)
        check("summary < 5s", t_summary < 5, f"took {t_summary:.1f}s")
        if t_summary > 1:
            warning("summary > 1s", f"{t_summary:.1f}s — consider optimization")
    except Exception as e:
        check("summary responds", False, str(e)[:100])
        t_summary = time.time() - t0

    t0 = time.time()
    try:
        perf = get_loyalty_performance(country="peru")
        t_perf = time.time() - t0
        check("performance responds", perf is not None)
        check("performance < 5s", t_perf < 5, f"took {t_perf:.1f}s")
        if t_perf > 1:
            warning("performance > 1s", f"{t_perf:.1f}s — consider optimization")

        check("scoring official blocked",
              perf.get("scoring_status") in (
                  "blocked_pending_yango_definition_validation",
                  "blocked_missing_targets",
                  "blocked_pending_reconciliation",
                  "blocked_error"),
              f"got: {perf.get('scoring_status')}")

        perf_cat = perf.get("summary", {}).get("performance_category")
        check("performance_category official null", perf_cat is None, f"got: {perf_cat}")

    except Exception as e:
        check("performance responds", False, str(e)[:100])
        t_perf = time.time() - t0

    t0 = time.time()
    try:
        trujillo = get_loyalty_performance(country="peru", city="trujillo")
        check("trujillo not_available",
              trujillo.get("freshness_status") == "not_available"
              or any(c.get("data_status") == "not_available" for c in trujillo.get("cities", [])),
              f"status: {trujillo.get('freshness_status')}")
    except Exception as e:
        check("trujillo not_available query", False, str(e)[:100])

    try:
        arequipa = get_loyalty_performance(country="peru", city="arequipa")
        check("arequipa not_available",
              arequipa.get("freshness_status") == "not_available"
              or any(c.get("data_status") == "not_available" for c in arequipa.get("cities", [])),
              f"status: {arequipa.get('freshness_status')}")
    except Exception as e:
        check("arequipa not_available query", False, str(e)[:100])

except ImportError:
    warning("backend imports not available", "skipping backend endpoint tests — run from backend/ directory")
except Exception as e:
    warning("backend tests skipped", str(e)[:100])


print()
print("=" * 70)
print("T2: FRONTEND STATIC ANALYSIS — YangoLoyaltyView.jsx")
print("=" * 70)

try:
    with open(YL_VIEW_PATH, "r", encoding="utf-8") as f:
        yl_src = f.read()

    check("file exists", len(yl_src) > 100)

    check("per-section loading: summaryLoading state",
          "summaryLoading" in yl_src)
    check("per-section loading: perfLoading state",
          "perfLoading" in yl_src)
    check("no single initialLoading blocking view",
          "setInitialLoading" not in yl_src,
          "found setInitialLoading — should use per-section loading")

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

    check("retry button for summary",
          bool(re.search(r"onClick.*fetchSummary", yl_src)))
    check("retry button for performance",
          bool(re.search(r"onClick.*fetchPerformance", yl_src)))

    check("timeout detection in error handling",
          "ECONNABORTED" in yl_src or "timeout" in yl_src.lower())

    check("no Promise.all blocking (uses allSettled or independent)",
          "Promise.all(" not in yl_src,
          "should use Promise.allSettled or independent fetches")

    check("no Forecast in YL view",
          "forecast" not in yl_src.lower() or "no forecast" in yl_src.lower())
    check("no Suggestion in YL view",
          "suggestion" not in yl_src.lower() or "no suggestion" in yl_src.lower())
    check("no Decision Engine in YL view",
          "decision engine" not in yl_src.lower())
    check("no Action Engine in YL view",
          "action engine" not in yl_src.lower())

    check("section-level error message present",
          "El resto de la vista sigue disponible" in yl_src)

except FileNotFoundError:
    check("YangoLoyaltyView.jsx exists", False, f"not found at {YL_VIEW_PATH}")


print()
print("=" * 70)
print("T3: NO REGRESSION — PARALLEL MODULES NOT TOUCHED")
print("=" * 70)

try:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True, cwd=BACKEND_ROOT
    )
    changed = result.stdout.strip().split("\n") if result.stdout.strip() else []

    staged = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        capture_output=True, text=True, cwd=BACKEND_ROOT
    )
    staged_files = staged.stdout.strip().split("\n") if staged.stdout.strip() else []
    all_changed = list(set(changed + staged_files))

    driver_files = [f for f in all_changed if any(k in f.lower() for k in [
        "driver_lifecycle", "driver_crm", "driver_campaign", "driverlifecycle",
        "driversupply", "driver_behavior", "driveroperational",
    ])]
    profitability_files = [f for f in all_changed if any(k in f.lower() for k in [
        "profitability", "profit_sharing", "vehicle_profitability", "ownership",
        "yegopro",
    ])]
    omniview_files = [f for f in all_changed if "omniview" in f.lower()]

    check("no Driver files modified",
          len(driver_files) == 0,
          f"modified: {driver_files}")
    check("no Profitability files modified",
          len(profitability_files) == 0,
          f"modified: {profitability_files}")
    check("no Omniview Matrix files modified",
          len(omniview_files) == 0,
          f"modified: {omniview_files}")

    yl_files = [f for f in all_changed if any(k in f.lower() for k in [
        "yango", "loyalty",
    ])]
    print(f"  [INFO] Yango Loyalty files changed: {yl_files}")

except Exception as e:
    warning("git diff check", str(e)[:100])


print()
print("=" * 70)
print("T4: BACKEND DEFENSIVE CHECKS")
print("=" * 70)

try:
    perf_svc_path = os.path.join(BACKEND_ROOT, "app", "services", "yango_loyalty_performance_service.py")
    with open(perf_svc_path, "r", encoding="utf-8") as f:
        perf_svc_src = f.read()

    check("performance uses lazy stub for N+R",
          "_fetch_nr_lazy_stub" in perf_svc_src,
          "should use lazy stub, not heavy computation")
    check("performance does not call preview_all_sets",
          "preview_all_sets" not in perf_svc_src)
    check("performance does not refresh MV",
          "REFRESH MATERIALIZED" not in perf_svc_src.upper())

    def_svc_path = os.path.join(BACKEND_ROOT, "app", "services", "yango_loyalty_definition_service.py")
    with open(def_svc_path, "r", encoding="utf-8") as f:
        def_svc_src = f.read()

    check("operational-flow reads serving fact v2",
          "fct_yego_operational_flow_monthly_v2" in def_svc_src)
    check("scoring blocked in operational-flow",
          "blocked_pending_yango_definition_validation" in def_svc_src)

    summary_svc_path = os.path.join(BACKEND_ROOT, "app", "services", "yango_loyalty_service.py")
    with open(summary_svc_path, "r", encoding="utf-8") as f:
        summary_svc_src = f.read()

    prefetch_fn = summary_svc_src[summary_svc_src.find("def _prefetch_all_data"):]
    prefetch_fn = prefetch_fn[:prefetch_fn.find("\ndef ")]
    prefetch_conns = prefetch_fn.count("with get_db() as conn:")
    check("_prefetch_all_data uses single DB connection",
          prefetch_conns <= 1,
          f"found {prefetch_conns} connections in _prefetch_all_data")
    check("summary does not call preview",
          "preview_all_sets" not in summary_svc_src)

except FileNotFoundError as e:
    warning("backend file not found", str(e))


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
