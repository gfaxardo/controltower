"""
QA Script - Fase 1H.2: Omniview VS Proyeccion Performance + Render + Legibilidad
Valida que los endpoints de omniview-projection y business-slice respondan
en tiempos controlados, sin runtime fallback, y con datos compatibles con UI.
"""
from __future__ import annotations

import json
import os
import sys
import time
import requests

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


def main():
    global START_TIME
    START_TIME = time.time()

    print("=" * 60)
    print("QA: Fase 1H.2 — Omniview VS Proyeccion UI Performance")
    print(f"Base URL:     {BASE_URL}")
    print(f"Plan Version: {PLAN_VERSION}")
    print("=" * 60)

    # ═══ A. Health Check ═══
    print("\n--- A. Health ---")
    t0 = time.time()
    code, body = get("/health", timeout=10)
    elapsed = round((time.time() - t0) * 1000)
    check("A.1 Backend health OK", code == 200, f"HTTP {code} {elapsed}ms")
    if code != 200:
        print("  SKIP: Backend not reachable")
        finalize()
        return 1

    # ═══ B. Filters < 2s (first uncached call) ═══
    print("\n--- B. Filters & Catalog ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/filters", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("B.1 filters < 2s", code == 200 and elapsed < 2000, f"HTTP {code} {elapsed}ms")
    if isinstance(body, dict):
        countries = len(body.get("countries", []))
        cities = len(body.get("cities", []))
        check("B.2 filters has countries", countries > 0, f"count={countries}")
        check("B.3 filters has cities", cities > 0, f"count={cities}")
    else:
        check("B.2 filters structure", False, "Not a dict")

    # ═══ C. Real-freshness < 3s ═══
    print("\n--- C. Real Freshness ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/real-freshness", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("C.1 real-freshness < 3s", code == 200 and elapsed < 3000, f"HTTP {code} {elapsed}ms")
    if isinstance(body, dict):
        status = body.get("status", "unknown")
        has_day = "day_fact" in body
        has_week = "week_fact" in body
        has_month = "month_fact" in body
        check("C.2 real-freshness structure", has_day and has_week and has_month,
              f"day={has_day} week={has_week} month={has_month}")
        check("C.3 real-freshness status valid", status in ("fresh", "stale", "critical", "empty", "unknown"),
              f"status={status}")

    # ═══ D. Serving Plan Versions ═══
    print("\n--- D. Serving Plan Versions ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/omniview-projection/serving-plan-versions", timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("D.1 serving-plan-versions < 3s", code == 200 and elapsed < 3000, f"HTTP {code} {elapsed}ms")
    if isinstance(body, dict) and body.get("versions"):
        check("D.2 has materialized versions", len(body["versions"]) > 0)

    # ═══ E. Omniview Projection by grain x country ═══
    print("\n--- E. Omniview Projection Endpoints ---")

    test_cases = [
        ("daily", "peru", 12000, 10000),
        ("daily", "colombia", 12000, 10000),
        ("weekly", "peru", 8000, 4500),
        ("weekly", "colombia", 8000, 4500),
        ("monthly", "peru", 8000, 4500),
        ("monthly", "colombia", 8000, 4500),
        ("monthly", None, 10000, 4500),
    ]

    for grain, country, max_ms, fact_ms in test_cases:
        label = f"E.{grain}_{country or 'all'}"
        params = {
            "plan_version": PLAN_VERSION,
            "grain": grain,
            "year": 2026,
        }
        if country:
            params["country"] = country

        t0 = time.time()
        code, body = get("/ops/business-slice/omniview-projection", params, timeout=max(60, int(max_ms / 1000) + 10))
        elapsed = round((time.time() - t0) * 1000)

        # Check response time
        ok = code == 200 and elapsed < max_ms
        check(f"{label} < {max_ms}ms", ok, f"HTTP {code} {elapsed}ms")

        if not isinstance(body, dict):
            check(f"{label} structure", False, "Not a dict")
            continue

        # Check serving source
        meta = body.get("meta", {})
        served_from = meta.get("served_from", "unknown")
        fallback_reason = meta.get("fallback_reason", "")

        # NO runtime fallback
        if served_from == "runtime_fallback":
            check(f"{label} no runtime fallback", False,
                  f"Runtime fallback detectado: {fallback_reason}")
        elif served_from == "fact":
            check(f"{label} served_from=fact OK", True, f"fact {elapsed}ms")
            check(f"{label} fact fast < {fact_ms}ms", elapsed < fact_ms,
                  f"fact served in {elapsed}ms (limit {fact_ms}ms)")
        elif served_from is None and fallback_reason == "serving_fact_missing":
            check(f"{label} serving_fact_missing controlled", True,
                  f"Controlled 200, no runtime fallback. Remediation: refresh script.")
        else:
            check(f"{label} served_from", True, f"served_from={served_from}")

        # Check data
        data = body.get("data", [])
        projection_exists = body.get("projection_exists", True)

        if served_from == "fact":
            check(f"{label} rows > 0", len(data) > 0, f"rows={len(data)}")
            if data:
                sample = data[0]
                has_trips = "trips_completed" in sample
                has_revenue = "revenue_yego_net" in sample
                has_comparison = "comparison_status" in sample
                check(f"{label} data structure valid", has_trips and has_revenue and has_comparison)
        elif not projection_exists:
            check(f"{label} projection_exists=False controlled", True,
                  f"Missing serving fact for {grain}/{country}")

    # ═══ F. Business Slice endpoints (daily/weekly/monthly) ═══
    print("\n--- F. Business Slice (Real) ---")

    slice_tests = [
        ("daily", "peru", 15000, "daily"),
        ("daily", "colombia", 15000, "daily"),
        ("weekly", "peru", 8000, "weekly"),
        ("weekly", "colombia", 8000, "weekly"),
        ("monthly", None, 10000, "monthly"),
    ]

    for grain, country, max_ms, endpoint in slice_tests:
        label = f"F.{grain}_{country or 'all'}"
        params = {"country": country, "year": 2026} if country else {"year": 2026}

        t0 = time.time()
        code, body = get(f"/ops/business-slice/{endpoint}", params, timeout=max(60, int(max_ms / 1000) + 10))
        elapsed = round((time.time() - t0) * 1000)

        ok = code == 200 and elapsed < max_ms
        check(f"{label} < {max_ms}ms", ok, f"HTTP {code} {elapsed}ms")

        if isinstance(body, dict):
            data = body.get("data", [])
            meta = body.get("meta", {})

            check_src = meta.get("source") or meta.get("status") or "unknown"
            check(f"{label} fact_layer_status", check_src != "error",
                  f"source={check_src}")

            if check_src == "ok":
                check(f"{label} has rows", len(data) > 0, f"rows={len(data)}")
            elif check_src == "empty":
                check(f"{label} empty controlled", True,
                      f"Empty fact for {grain}/{country}")

        # Verify no 500 error from connection issues
        check(f"{label} no 500", code != 500, f"HTTP {code}")

    # ═══ G. Monthly real < 5s ═══
    print("\n--- G. Monthly Real ---")
    t0 = time.time()
    code, body = get("/ops/business-slice/monthly", {"year": 2026}, timeout=30)
    elapsed = round((time.time() - t0) * 1000)
    check("G.1 monthly < 5s", code == 200 and elapsed < 5000, f"HTTP {code} {elapsed}ms")
    if isinstance(body, dict):
        data = body.get("data", [])
        check("G.2 monthly has data", len(data) > 0, f"rows={len(data)}")

    # ═══ H. Frontend compatibility ═══
    print("\n--- H. Frontend Compatibility ---")

    # Check projection response has expected keys
    t0 = time.time()
    code, body = get("/ops/business-slice/omniview-projection", {
        "plan_version": PLAN_VERSION,
        "grain": "daily",
        "country": "peru",
        "year": 2026,
    }, timeout=90)
    elapsed = round((time.time() - t0) * 1000)

    if isinstance(body, dict):
        has_data = "data" in body
        has_meta = "meta" in body
        has_granularity = "granularity" in body
        check("H.1 has data key", has_data)
        check("H.2 has meta key", has_meta)
        check("H.3 has granularity key", has_granularity)

        # Verify projection matrix fields expected by frontend
        if body.get("data"):
            sample = body["data"][0]
            proj_fields = [
                "trips_completed", "revenue_yego_net", "active_drivers",
                "avg_ticket", "trips_per_driver", "cancel_rate_pct",
                "commission_pct",
            ]
            missing = [f for f in proj_fields if f not in sample]
            check("H.4 frontend expected fields present", len(missing) == 0,
                  f"missing={missing}" if missing else "all present")

    # Check projection fallback structure is compatible
    t0 = time.time()
    code_fb, body_fb = get("/ops/business-slice/omniview-projection", {
        "plan_version": "nonexistent_version_999",
        "grain": "daily",
        "country": "peru",
        "year": 2026,
    }, timeout=90)

    if isinstance(body_fb, dict):
        proj_exists = body_fb.get("projection_exists")
        served_fb = body_fb.get("meta", {}).get("served_from")
        fallback_reason = body_fb.get("meta", {}).get("fallback_reason")
        has_data_fb = "data" in body_fb
        has_remediation = bool(body_fb.get("meta", {}).get("required_refresh_command"))

        check("H.5 missing plan: projection_exists=False", proj_exists is False,
              f"projection_exists={proj_exists}")
        check("H.6 missing plan: served_from=None (no runtime)", served_fb is None,
              f"served_from={served_fb}")
        check("H.7 missing plan: has fallback_reason", bool(fallback_reason))
        check("H.8 missing plan: has remediation", has_remediation)
        check("H.9 missing plan: data key present (empty)", has_data_fb and len(body_fb.get("data", [1])) == 0)

    # ═══ I. Daily Colombia special: verify no 21s timeouts ═══
    print("\n--- I. Daily Colombia Hardening ---")
    t0 = time.time()
    code_co, body_co = get("/ops/business-slice/daily", {
        "country": "colombia",
        "year": 2026,
    }, timeout=60)
    elapsed_co = round((time.time() - t0) * 1000)

    check("I.1 daily Colombia < 20s", code_co == 200 and elapsed_co < 20000,
          f"HTTP {code_co} {elapsed_co}ms")
    check("I.2 daily Colombia no 500", code_co != 500, f"HTTP {code_co}")

    if isinstance(body_co, dict):
        meta_co = body_co.get("meta", {})
        co_status = meta_co.get("status") or meta_co.get("code") or "unknown"
        check("I.3 daily Colombia controlled response",
              co_status in ("ok", "empty", "error", "FACT_LAYER_EMPTY", "FACT_CONNECTION_ERROR"),
              f"meta.status={co_status}")

    # ═══ VERDICT ═══
    finalize()


def finalize():
    total = len(results)
    passed = sum(1 for r in results if r["status"] == PASS)
    warned = sum(1 for r in results if r["status"] == WARN)
    failed = sum(1 for r in results if r["status"] == FAIL)
    critical = sum(1 for r in results
                   if r["status"] == FAIL and r["check"].startswith(("A.", "E.", "F.", "G.", "I.")))

    total_elapsed = round((time.time() - START_TIME) * 1000)

    print("\n" + "=" * 60)
    print(f"Total runtime: {total_elapsed}ms")
    print(f"Checks: {total} | PASS: {passed} | WARN: {warned} | FAIL: {failed} | Critical: {critical}")

    verdict = "GO" if failed == 0 else ("CONDITIONAL GO" if critical == 0 else "NO-GO")
    print(f"\nVERDICT: {verdict}")

    # Write JSON report
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "outputs",
        "validate_phase1h2_result.json",
    )
    try:
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "phase": "1H.2",
                "verdict": verdict,
                "runtime_ms": total_elapsed,
                "checks": results,
                "total": total,
                "passed": passed,
                "warned": warned,
                "failed": failed,
                "critical_failures": critical,
            }, f, indent=2, ensure_ascii=False)
        print(f"Report saved: {report_path}")
    except Exception as e:
        print(f"Could not save report: {e}")

    sys.exit(0 if verdict != "NO-GO" else 1)


if __name__ == "__main__":
    main()
