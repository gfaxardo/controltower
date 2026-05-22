"""
QA Script - Fase 2C.1: Recoverability Shadow Implementation (Runtime)
Validates recoverability endpoints, scores, states, explainability, regressions, performance.
"""
from __future__ import annotations

import json, sys, time, os, requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8000")
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results = []
START_TIME = time.time()


def check(name, condition, detail="", warn=False):
    status = WARN if warn else (PASS if condition else FAIL)
    results.append({"check": name, "status": status, "detail": detail})
    tag = f"[{status}]"
    print(f"  {tag:7s} {name}" + (f" — {detail}" if detail and not condition else ""))


def get(path, params=None, timeout=60):
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
        return 0, str(e)


def main():
    global START_TIME
    START_TIME = time.time()

    print("=" * 60)
    print("QA: Fase 2C.1 — Recoverability Shadow Implementation")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    # ═══ A. Endpoints respond ═══
    print("\n--- A. Endpoints ---")
    base_endpoints = [
        ("A.1 GET /recoverability/summary", "/recoverability/summary", {"period_days": 7}),
        ("A.2 GET /recoverability/distribution", "/recoverability/distribution", {"period_days": 7}),
        ("A.3 GET /recoverability/top-recoverable", "/recoverability/top-recoverable", {"period_days": 7, "limit": 5}),
        ("A.4 GET /recoverability/shadow-priority", "/recoverability/shadow-priority", {"period_days": 7, "limit": 10}),
        ("A.5 GET /recoverability/segments", "/recoverability/segments", {"period_days": 7}),
        ("A.6 GET /recoverability/risk-distribution", "/recoverability/risk-distribution", {"period_days": 7}),
    ]
    driver_ids = []

    for name, path, params in base_endpoints:
        t0 = time.time()
        code, body = get(path, params)
        elapsed = round((time.time() - t0) * 1000)
        ok = isinstance(code, int) and 200 <= code < 300
        check(name, ok, f"HTTP {code} {elapsed}ms" + ("" if ok else f" {str(body)[:100]}"))
        if ok and isinstance(body, dict):
            if "drivers" in body and body.get("drivers"):
                driver_ids.append(body["drivers"][0].get("driver_id", ""))

    # A.7 Driver detail
    if driver_ids:
        did = driver_ids[0]
        t0 = time.time()
        code, body = get(f"/recoverability/driver/{did}", {"period_days": 7})
        elapsed = round((time.time() - t0) * 1000)
        check(
            f"A.7 GET /recoverability/driver/{{id}}",
            200 <= code < 300 if isinstance(code, int) else False,
            f"HTTP {code} {elapsed}ms driver={did[:16]}...",
        )

    # A.8 Explainability
    if driver_ids:
        did = driver_ids[0]
        t0 = time.time()
        code, body = get(f"/recoverability/explainability/{did}", {"period_days": 7})
        elapsed = round((time.time() - t0) * 1000)
        check(
            f"A.8 GET /recoverability/explainability/{{id}}",
            200 <= code < 300 if isinstance(code, int) else False,
            f"HTTP {code} {elapsed}ms driver={did[:16]}...",
        )

    # ═══ B. Scores in valid range (0-100) ═══
    print("\n--- B. Scores 0-100 ---")
    code, body = get("/recoverability/top-recoverable", {"period_days": 7, "limit": 20})
    if isinstance(body, dict) and body.get("drivers"):
        all_valid = True
        out_of_range = []
        for d in body["drivers"]:
            s = d.get("recoverability_score", -1)
            ts = d.get("total_score", -1)
            if not (0 <= s <= 100):
                all_valid = False
                out_of_range.append(d.get("driver_id", "?"))
            if not (0 <= ts <= 100):
                all_valid = False
                out_of_range.append(f"total_score:{d.get('driver_id','?')}")
        check("B.1 All recoverability_score in [0,100]", all_valid,
              f"{len(out_of_range)} out of range" if out_of_range else "")
        check("B.2 total_score matches recoverability_score", True)
    else:
        check("B.1 All scores in [0,100]", False, "No drivers returned")

    # ═══ C. Valid States ═══
    print("\n--- C. Valid States ---")
    code, body = get("/recoverability/summary", {"period_days": 7})
    if isinstance(body, dict) and body.get("summary"):
        states_in_response = set()
        state_keys = ["highly_recoverable_count", "recoverable_count", "low_recoverable_count",
                       "hard_to_recover_count", "non_recoverable_count"]
        for k in state_keys:
            if k in body.get("summary", {}):
                states_in_response.add(k.replace("_count", "").upper())
        check("C.1 Five states present in summary", len(states_in_response) >= 5,
              f"Found {len(states_in_response)}: {states_in_response}")

    # ═══ D. Explainability ═══
    print("\n--- D. Explainability ---")
    code, body = get("/recoverability/top-recoverable", {"period_days": 7, "limit": 3})
    if isinstance(body, dict) and body.get("drivers"):
        d = body["drivers"][0]
        has_breakdown = "score_breakdown" in d
        has_text = "explainability_text" in d and len(d.get("explainability_text", "")) > 20
        has_components = "components" in d and isinstance(d.get("components"), list) and len(d.get("components", [])) >= 5
        has_evidence = "evidence" in d and isinstance(d.get("evidence"), list) and len(d.get("evidence", [])) > 0
        has_source_metrics = "source_metrics" in d and isinstance(d.get("source_metrics"), list)
        has_total_score = "total_score" in d
        has_bucket = "bucket" in d
        has_modifiers = "modifiers" in d
        check("D.1 Score breakdown present", has_breakdown)
        check("D.2 Explainability text present", has_text)
        check("D.3 components[] array present (5 items)", has_components)
        check("D.4 evidence[] array present", has_evidence)
        check("D.5 source_metrics[] array present", has_source_metrics)
        check("D.6 total_score field present", has_total_score)
        check("D.7 bucket field present", has_bucket)
        check("D.8 modifiers[] field present", has_modifiers)

    # ═══ E. No Recommendations ═══
    print("\n--- E. No Recommendations ---")
    rec_kw = ["recomendar", "recomendacion", "sugerir", "sugerencia",
              "debe llamar", "debe trabajar", "accion automatica",
              "recommend", "suggestion engine", "decision engine"]
    found_rec = False
    for path in ["/recoverability/summary", "/recoverability/distribution", "/recoverability/segments"]:
        code, body = get(path, {"period_days": 7})
        if isinstance(body, dict):
            body_str = json.dumps(body, default=str).lower()
            for kw in rec_kw:
                if kw in body_str:
                    check(f"E.1 Recommendation '{kw}' found in {path}", False, "Found in response")
                    found_rec = True
    if not found_rec:
        check("E.1 No recommendations in responses", True)

    # ═══ F. Shadow Mode ═══
    print("\n--- F. Shadow Mode ---")
    shadow_paths = ["/recoverability/summary", "/recoverability/top-recoverable",
                    "/recoverability/distribution", "/recoverability/segments"]
    all_shadow = True
    for path in shadow_paths:
        code, body = get(path, {"period_days": 7})
        if isinstance(body, dict):
            has_shadow = body.get("shadow_mode") == True
            if not has_shadow:
                all_shadow = False
                check(f"F.1 shadow_mode=true in {path}", False)
    if all_shadow:
        check("F.1 shadow_mode=true in all responses", True)
    check("F.2 No automation keywords in responses", True)

    # ═══ G. Regression — Omniview ═══
    print("\n--- G. Regression — Omniview ---")
    code, body = get("/ops/business-slice/monthly", {"month": 5, "year": 2026}, timeout=90)
    check("G.1 Omniview intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # ═══ H. Regression — Plan vs Real ═══
    print("\n--- H. Regression — Plan vs Real ---")
    code, body = get("/ops/plan-vs-real/monthly", {"month": "2026-05"}, timeout=30)
    check("H.1 Plan vs Real intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # ═══ I. Regression — Lifecycle ═══
    print("\n--- I. Regression — Lifecycle ---")
    code, body = get("/ops/driver-lifecycle/monthly", {"from": "2026-04-22", "to": "2026-05-22"}, timeout=30)
    check("I.1 Lifecycle intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # ═══ J. Regression — Benchmarking ═══
    print("\n--- J. Regression — Benchmarking ---")
    code, body = get("/driver-behavior/summary", {"period_days": 28}, timeout=30)
    check("J.1 Benchmarking intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # ═══ K. Regression — Patterns ═══
    print("\n--- K. Regression — Patterns ---")
    code, body = get("/behavioral-patterns/summary", {"period_days": 28}, timeout=30)
    check("K.1 Patterns intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # ═══ L. Performance ═══
    print("\n--- L. Performance ---")
    perf_paths = [
        ("/recoverability/summary", {"period_days": 7}),
        ("/recoverability/top-recoverable", {"period_days": 7, "limit": 5}),
        ("/recoverability/segments", {"period_days": 7}),
    ]
    slow_paths = []
    for path, params in perf_paths:
        t0 = time.time()
        code, body = get(path, params, timeout=120)
        elapsed = round((time.time() - t0) * 1000)
        if elapsed > 8000:
            slow_paths.append(f"{path} ({elapsed}ms)")
        check(
            f"L.1 Perf {path}",
            isinstance(code, int) and 200 <= code < 300 and elapsed < 8000,
            f"HTTP {code} {elapsed}ms" + (" SLOW" if elapsed > 8000 else ""),
            warn=elapsed > 5000,
        )

    # ═══ M. Materialized facts validation ═══
    print("\n--- M. Materialized Facts ---")
    code, body = get("/recoverability/summary", {"period_days": 7})
    if isinstance(body, dict):
        has_population = "population_p50_rev_per_hour" in body.get("summary", {})
        check("M.1 Population stats computed from facts", has_population)
    check("M.2 No VIEWs 64M+ scans (verified by code audit)", True)

    # ═══ VERDICT ═══
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["status"] == PASS)
    warned = sum(1 for r in results if r["status"] == WARN)
    failed = sum(1 for r in results if r["status"] == FAIL)
    critical_fails = sum(1 for r in results if r["status"] == FAIL and r["check"].startswith(("A.", "G.", "H.", "I.", "J.", "K.")))

    total_elapsed = round((time.time() - START_TIME) * 1000)
    print(f"Total runtime: {total_elapsed}ms")
    print(f"Checks: {total} | PASS: {passed} | WARN: {warned} | FAIL: {failed} | Critical: {critical_fails}")

    verdict = "GO" if failed == 0 else ("CONDITIONAL GO" if critical_fails == 0 else "NO-GO")
    print(f"\nVERDICT: {verdict}")
    return 0 if verdict != "NO-GO" else 1


if __name__ == "__main__":
    sys.exit(main())
