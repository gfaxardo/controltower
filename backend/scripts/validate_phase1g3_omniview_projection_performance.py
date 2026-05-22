"""
QA Script - Fase 1G.3: Omniview Projection Performance Serving Layer
Valida que los endpoints críticos respondan en tiempos aceptables
y que el serving layer funcione correctamente.
"""
from __future__ import annotations

import json, sys, time, os, requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8001")
PLAN_VERSION = os.environ.get("CT_PLAN_VERSION", "ruta27_2026_04_21")
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[dict] = []
START_TIME = time.time()


def check(name, condition, detail="", warn=False):
    status = WARN if warn else (PASS if condition else FAIL)
    results.append({"check": name, "status": status, "detail": str(detail)})
    tag = f"[{status}]"
    msg = f"  {tag:7s} {name}"
    if detail and not condition:
        msg += f" — {detail}"
    print(msg)


def get(path, params=None, timeout=30):
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


def main():
    global START_TIME
    START_TIME = time.time()

    print("=" * 60)
    print("QA: Fase 1G.3 — Omniview Projection Performance Serving Layer")
    print(f"Base URL:     {BASE_URL}")
    print(f"Plan Version: {PLAN_VERSION}")
    print("=" * 60)

    # ═══ A. Health check ═══
    print("\n--- A. Health ---")
    t0 = time.time()
    code, body = get("/health", timeout=10)
    elapsed = round((time.time() - t0) * 1000)
    check("A.1 Backend health OK", code == 200, f"HTTP {code} {elapsed}ms")

    # ═══ B. /plan/versions < 2s ═══
    print("\n--- B. Plan Versions ---")
    t0 = time.time()
    code, body = get("/plan/versions", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    ok = code == 200 and elapsed < 2000
    check("B.1 /plan/versions < 2s", ok, f"HTTP {code} {elapsed}ms")

    # ═══ C. /ops/business-slice/filters < 2s ═══
    print("\n--- C. Filters ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/filters", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    ok = code == 200 and elapsed < 2000
    check("C.1 /ops/business-slice/filters < 2s", ok, f"HTTP {code} {elapsed}ms")
    if isinstance(body, dict):
        has_countries = len(body.get("countries", [])) > 0
        has_cities = len(body.get("cities", [])) > 0
        check("C.2 Filters have countries", has_countries)
        check("C.3 Filters have cities", has_cities)

    # ═══ D. Omniview Projection daily < 5s ═══
    print("\n--- D. Omniview Projection (daily) ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/omniview-projection", {
        "plan_version": PLAN_VERSION,
        "grain": "daily",
        "country": "peru",
        "year": 2026,
    }, timeout=90)
    elapsed = round((time.time() - t0) * 1000)
    ok = code == 200 and elapsed < 5000
    check("D.1 Omniview daily < 5s", ok, f"HTTP {code} {elapsed}ms")

    if isinstance(body, dict):
        served_from = body.get("meta", {}).get("served_from", "unknown")
        duration = body.get("meta", {}).get("query_duration_ms", "N/A")
        fact_at = body.get("meta", {}).get("fact_generated_at")
        check("D.2 served_from field present", served_from != "unknown",
              f"served_from={served_from} duration={duration}ms")

        data_rows = body.get("data", [])
        total = len(data_rows)
        check("D.3 Has data rows", total > 0, f"rows={total}")

        if data_rows:
            sample = data_rows[0]
            has_trips = "trips_completed" in sample
            has_revenue = "revenue_yego_net" in sample
            has_comparison = "comparison_status" in sample
            check("D.4 Data structure valid", has_trips and has_revenue and has_comparison)

        # If served from fact, fact_generated_at should exist
        if served_from == "fact":
            check("D.5 fact_generated_at present", bool(fact_at), f"fact_at={fact_at}")
        elif served_from == "runtime_fallback":
            check("D.5 Runtime fallback (no serving fact yet)", True, warn=True)

    # ═══ E. No duplication critical ═══
    print("\n--- E. Data Integrity ---")
    if isinstance(body, dict) and body.get("data"):
        rows = body["data"]
        seen_keys = set()
        dups = 0
        for r in rows:
            key = (r.get("trip_date") or r.get("week_start") or r.get("month"), r.get("country"), r.get("city"), r.get("business_slice_name"))
            if key in seen_keys:
                dups += 1
            seen_keys.add(key)
        check("E.1 No duplicate rows", dups == 0, f"duplicates={dups}" if dups else "")

    # ═══ F. Frontend skeleton check (indirect) ═══
    print("\n--- F. Frontend Integration ---")
    check("F.1 Projection response has 'data' key", isinstance(body, dict) and "data" in body)
    check("F.2 Projection response has 'meta' key", isinstance(body, dict) and "meta" in body)

    # ═══ G. Regressions ═══
    print("\n--- G. Regressions ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/monthly", {"month": 5, "year": 2026}, timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("G.1 Omniview Matrix intact", code == 200, f"HTTP {code} {elapsed}ms")

    t0 = time.time()
    code, body = get("/ops/plan-vs-real/monthly", {"month": "2026-05"}, timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("G.2 Plan vs Real intact", code == 200, f"HTTP {code} {elapsed}ms")

    # ═══ VERDICT ═══
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["status"] == PASS)
    warned = sum(1 for r in results if r["status"] == WARN)
    failed = sum(1 for r in results if r["status"] == FAIL)
    critical = sum(1 for r in results if r["status"] == FAIL and r["check"].startswith(("A.", "D.", "G.")))

    total_elapsed = round((time.time() - START_TIME) * 1000)
    print(f"Total runtime: {total_elapsed}ms")
    print(f"Checks: {total} | PASS: {passed} | WARN: {warned} | FAIL: {failed} | Critical: {critical}")

    verdict = "GO" if failed == 0 else ("CONDITIONAL GO" if critical == 0 else "NO-GO")
    print(f"\nVERDICT: {verdict}")

    return 0 if verdict != "NO-GO" else 1


if __name__ == "__main__":
    sys.exit(main())
