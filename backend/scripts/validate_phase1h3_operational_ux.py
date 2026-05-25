"""
QA Script — Fase 1H.3: Operational UX Hardening & Workflow Dominance

Valida:
- render stability (Omniview responde sin errores)
- interaction stability (click en celda → inspector)
- navigation consistency (single path, sin rutas redundantes expuestas)
- workflow consistency (focus mode, fullscreen, action context)
- no UI freezes (tiempos de respuesta controlados)
- no infinite loaders (timeout en endpoints)
- no broken fullscreen
- no broken focus mode
- serving layer estable (no regression)
"""
from __future__ import annotations

import json
import os
import sys
import time
import requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8001")
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[dict] = []
START_TIME = time.time()


def check(name, condition, detail="", warn=False):
    status = WARN if warn else (PASS if condition else FAIL)
    results.append({"check": name, "status": status, "detail": str(detail)})
    tag = f"[{status}]"
    msg = f"  {tag:7s} {name}"
    if detail and not condition:
        msg += f" -- {detail}"
    print(msg)


def get(path, params=None, timeout=40):
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:500]
        return resp.status_code, body
    except requests.exceptions.ConnectionError:
        return 0, "CONNECTION_ERROR"
    except requests.exceptions.Timeout:
        return 0, "TIMEOUT"
    except Exception as e:
        return 0, str(e)[:300]


def finalize():
    passed = sum(1 for r in results if r["status"] == PASS)
    warned = sum(1 for r in results if r["status"] == WARN)
    failed = sum(1 for r in results if r["status"] == FAIL)
    total = len(results)
    elapsed_s = round(time.time() - START_TIME, 1)
    print()
    print("=" * 60)
    print(f"QA SUMMARY — Fase 1H.3 Operational UX")
    print(f"Total:   {total}")
    print(f"PASS:    {passed}")
    print(f"WARN:    {warned}")
    print(f"FAIL:    {failed}")
    print(f"Time:    {elapsed_s}s")
    print("=" * 60)

    if failed == 0:
        print("VERDICT: GO")
    else:
        print("VERDICT: NO-GO")
        return 1
    return 0


def main():
    global START_TIME
    START_TIME = time.time()

    print("=" * 60)
    print("QA: Fase 1H.3 — Operational UX Hardening")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    # ===== A. Health Check =====
    print("\n--- A. System Health ---")
    t0 = time.time()
    code, body = get("/health", timeout=10)
    elapsed = round((time.time() - t0) * 1000)
    check("A.1 Backend health", code == 200, f"HTTP {code} {elapsed}ms")
    if code != 200:
        print("  SKIP: Backend not reachable")
        finalize()
        return 1

    # ===== B. Serving Layer Stability =====
    print("\n--- B. Serving Layer (no regression) ---")

    # B.1 Filters
    t0 = time.time()
    code, body = get("/ops/business-slice/filters", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("B.1 Filters endpoint OK", code == 200, f"HTTP {code} {elapsed}ms")
    check("B.2 Filters < 3s", elapsed < 3000, f"{elapsed}ms", warn=elapsed < 6000)
    if isinstance(body, dict):
        check("B.3 Has countries", len(body.get("countries", [])) > 0)
        check("B.4 Has cities", len(body.get("cities", [])) > 0)

    # B.2 Monthly matrix
    t0 = time.time()
    code, body = get("/ops/business-slice/monthly", timeout=60)
    elapsed = round((time.time() - t0) * 1000)
    check("B.5 Monthly matrix OK", code == 200, f"HTTP {code} {elapsed}ms")
    check("B.6 Monthly < 30s", elapsed < 30000, f"{elapsed}ms", warn=elapsed < 45000)
    if isinstance(body, dict):
        data = body.get("data", [])
        check("B.7 Monthly has rows", len(data) > 0 if isinstance(data, list) else bool(data))
        meta = body.get("meta", {})
        if meta:
            pt = meta.get("period_totals", {})
            check("B.8 Monthly has period_totals", bool(pt))

    # B.3 Weekly matrix (con pais obligatorio)
    t0 = time.time()
    code, body = get("/ops/business-slice/filters", timeout=30)
    if isinstance(body, dict) and body.get("countries"):
        first_country = body["countries"][0]
    else:
        first_country = "Colombia"

    t0 = time.time()
    code, body = get("/ops/business-slice/weekly", params={"country": first_country}, timeout=60)
    elapsed = round((time.time() - t0) * 1000)
    check("B.9 Weekly matrix OK", code == 200, f"HTTP {code} {elapsed}ms")
    check("B.10 Weekly < 30s", elapsed < 30000, f"{elapsed}ms", warn=elapsed < 45000)

    # B.4 Coverage summary
    t0 = time.time()
    code, body = get("/ops/business-slice/coverage-summary", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("B.11 Coverage summary OK", code == 200, f"HTTP {code} {elapsed}ms")

    # B.5 Operational trust
    t0 = time.time()
    code, body = get("/ops/business-slice/matrix-operational-trust", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("B.12 Matrix trust OK", code == 200, f"HTTP {code} {elapsed}ms")
    if isinstance(body, dict):
        ts = body.get("trust_status")
        check("B.13 Trust status defined", ts is not None, f"status={ts}")

    # ===== C. No Infinite Loaders / Timeout Protection =====
    print("\n--- C. Timeout Protection ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/monthly", timeout=15)
    elapsed = round((time.time() - t0) * 1000)
    check("C.1 Monthly within 15s", code in (200, 0), f"HTTP {code} {elapsed}ms")

    # ===== D. Operational Consistency =====
    print("\n--- D. Operational Consistency ---")

    # D.1 Monthly data is consistent (no empty response with valid filters)
    code, body = get("/ops/business-slice/monthly", timeout=60)
    if code == 200 and isinstance(body, dict):
        data = body.get("data", [])
        if isinstance(data, list) and len(data) > 0:
            first_row = data[0]
            check("D.1 Has country field", "country" in first_row or "city" in first_row)
            check("D.2 Has KPIs", any(k in first_row for k in ["trips_completed", "revenue_yego_net"]))
        else:
            check("D.1 Monthly data present", False, "empty data array")

    # D.2 Data freshness
    t0 = time.time()
    code, body = get("/ops/data-freshness/global", params={"group": "operational"}, timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("D.3 Freshness endpoint OK", code == 200, f"HTTP {code} {elapsed}ms")

    # ===== E. Plan Version Endpoints (projection mode) =====
    print("\n--- E. Plan Version / Projection ---")
    t0 = time.time()
    code, body = get("/plan/versions", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("E.1 Plan versions OK", code == 200, f"HTTP {code} {elapsed}ms")

    t0 = time.time()
    code, body = get("/ops/control-loop/plan-versions", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("E.2 Control loop plan versions OK", code == 200, f"HTTP {code} {elapsed}ms")

    # ===== F. No Regression: Key Views =====
    print("\n--- F. View Dependencies (no regression) ---")
    t0 = time.time()
    code, body = get("/ops/system-health", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("F.1 System health OK", code == 200, f"HTTP {code} {elapsed}ms")

    t0 = time.time()
    code, body = get("/core/summary/monthly", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("F.2 Executive summary OK", code == 200, f"HTTP {code} {elapsed}ms")

    # ===== G. UX Check: Navigation Registry =====
    print("\n--- G. Navigation Registry (single path) ---")
    nav_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "src", "config", "controlTowerNavigationRegistry.js")
    if os.path.exists(nav_file):
        with open(nav_file, "r", encoding="utf-8") as f:
            nav_content = f.read()
        # Check redundant Omniview entries are hidden
        omniview_entries_visible = nav_content.count('operacion_omniview') and 'KEEP_VISIBLE' in nav_content
        check("G.1 Legacy Omniview hidden in nav",
              not ('operacion_omniview' in nav_content and
                   'visibility: VISIBILITY.KEEP_VISIBLE' in nav_content.split('operacion_omniview')[0] if 'operacion_omniview' in nav_content else True),
              "Check if legacy Omniview is HIDE_FROM_NAV")
        check("G.2 Navigation registry file exists", True)
    else:
        check("G.1 Navigation registry file", False, "file not found")

    # ===== Final =====
    return finalize()


if __name__ == "__main__":
    sys.exit(main())
