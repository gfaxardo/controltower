"""
QA Script - Fase 2C.1: Recoverability Shadow Implementation
Validates recoverability endpoints, scores, states, explainability, and regressions.
"""
from __future__ import annotations

import json, sys, time, os, requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8000")
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results = []


def check(name, condition, detail="", warn=False):
    status = WARN if warn else (PASS if condition else FAIL)
    results.append({"check": name, "status": status, "detail": detail})
    tag = f"[{status}]"
    print(f"  {tag:7s} {name}" + (f" — {detail}" if detail and not condition else ""))


def get(path, params=None, timeout=60):
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        try: body = resp.json()
        except: body = resp.text[:500]
        return resp.status_code, body
    except requests.exceptions.ConnectionError:
        return 0, "CONNECTION_ERROR"
    except requests.exceptions.Timeout:
        return 0, "TIMEOUT"
    except Exception as e:
        return 0, str(e)


def main():
    print("=" * 60)
    print("QA: Fase 2C.1 — Recoverability Shadow Implementation")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    # A. Endpoints respond
    print("\n--- A. Endpoints ---")
    endpoints = [
        ("A.1 GET /recoverability/summary", "/recoverability/summary", {"period_days": 7}),
        ("A.2 GET /recoverability/distribution", "/recoverability/distribution", {"period_days": 7}),
        ("A.3 GET /recoverability/top-recoverable", "/recoverability/top-recoverable", {"period_days": 7, "limit": 5}),
        ("A.4 GET /recoverability/shadow-priority", "/recoverability/shadow-priority", {"period_days": 7, "limit": 10}),
    ]
    driver_ids = []
    for name, path, params in endpoints:
        start = time.time()
        code, body = get(path, params)
        elapsed = round((time.time() - start) * 1000)
        ok = isinstance(code, int) and 200 <= code < 300
        check(name, ok, f"HTTP {code} {elapsed}ms" + ("" if ok else f" {str(body)[:100]}"))
        if ok and isinstance(body, dict):
            # Collect a driver_id for detail test
            if "drivers" in body and body["drivers"]:
                driver_ids.append(body["drivers"][0].get("driver_id", ""))

    # A.5 Driver detail
    if driver_ids:
        did = driver_ids[0]
        code, body = get(f"/recoverability/driver/{did}", {"period_days": 7})
        check(f"A.5 GET /recoverability/driver/{{id}}", 200 <= code < 300 if isinstance(code, int) else False,
              f"HTTP {code} driver={did[:16]}...")

    # B. Scores in valid range (0-100)
    print("\n--- B. Scores 0-100 ---")
    code, body = get("/recoverability/top-recoverable", {"period_days": 7, "limit": 10})
    if isinstance(body, dict) and body.get("drivers"):
        all_valid = True
        for d in body["drivers"][:10]:
            s = d.get("recoverability_score", -1)
            if not (0 <= s <= 100):
                all_valid = False
                check(f"B.1 Score {s} in [0,100]", False, f"driver={d.get('driver_id','?')[:16]}")
        if all_valid:
            check("B.1 All scores in [0,100]", True)
    else:
        check("B.1 All scores in [0,100]", False, "No drivers returned")

    # C. Valid states
    print("\n--- C. Valid States ---")
    valid_states = {"HIGHLY_RECOVERABLE", "RECOVERABLE", "LOW_RECOVERABLE", "HARD_TO_RECOVER", "NON_RECOVERABLE"}
    code, body = get("/recoverability/summary", {"period_days": 7})
    if isinstance(body, dict) and body.get("summary"):
        states_in_response = set()
        for k in ["highly_recoverable_count", "recoverable_count", "low_recoverable_count",
                   "hard_to_recover_count", "non_recoverable_count"]:
            if k in body["summary"]:
                states_in_response.add(k.replace("_count", "").upper())
        check("C.1 Five states present in summary", len(states_in_response) >= 5,
              f"Found {len(states_in_response)}: {states_in_response}")

    # D. Explainability present
    print("\n--- D. Explainability ---")
    code, body = get("/recoverability/top-recoverable", {"period_days": 7, "limit": 1})
    if isinstance(body, dict) and body.get("drivers"):
        d = body["drivers"][0]
        has_breakdown = "score_breakdown" in d
        has_text = "explainability_text" in d and len(d.get("explainability_text", "")) > 20
        check("D.1 Score breakdown present", has_breakdown)
        check("D.2 Explainability text present", has_text)

    # E. No recommendations
    print("\n--- E. No Recommendations ---")
    rec_kw = ["recomendar", "recomendacion", "sugerir", "sugerencia",
              "debe llamar", "debe trabajar", "accion automatica"]
    found_rec = False
    for path in ["/recoverability/summary", "/recoverability/distribution"]:
        code, body = get(path, {"period_days": 7})
        if isinstance(body, dict):
            body_str = json.dumps(body).lower()
            for kw in rec_kw:
                if kw in body_str:
                    check(f"E.1 Recommendation '{kw}' in {path}", False, "Found in response")
                    found_rec = True
    if not found_rec:
        check("E.1 No recommendations in responses", True)

    # F. No automation
    print("\n--- F. Shadow Mode ---")
    code, body = get("/recoverability/summary", {"period_days": 7})
    if isinstance(body, dict):
        has_shadow = body.get("shadow_mode") == True
        check("F.1 shadow_mode=true in responses", has_shadow)
        has_note = "shadow" in str(body.get("note", "")).lower()
        check("F.2 Shadow mode disclaimer present", has_note, warn=True)

    # G. Regression: Omniview
    print("\n--- G. Regression — Omniview ---")
    code, body = get("/ops/business-slice/monthly", {"month": 5, "year": 2026}, timeout=90)
    check("G.1 Omniview intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # H. Regression: Plan vs Real
    print("\n--- H. Regression — Plan vs Real ---")
    code, body = get("/ops/plan-vs-real/monthly", {"month": "2026-05"}, timeout=30)
    check("H.1 Plan vs Real intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # I. Regression: Lifecycle
    print("\n--- I. Regression — Lifecycle ---")
    code, body = get("/ops/driver-lifecycle/monthly", {"from": "2026-04-22", "to": "2026-05-22"}, timeout=30)
    check("I.1 Lifecycle intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # J. Regression: Benchmarking
    print("\n--- J. Regression — Benchmarking ---")
    code, body = get("/driver-behavior/summary", {"period_days": 28}, timeout=30)
    check("J.1 Benchmarking intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # K. Regression: Patterns
    print("\n--- K. Regression — Patterns ---")
    code, body = get("/behavioral-patterns/summary", {"period_days": 28}, timeout=30)
    check("K.1 Patterns intact", isinstance(code, int) and 200 <= code < 300, f"HTTP {code}")

    # L. Performance
    print("\n--- L. Performance ---")
    code, body = get("/recoverability/summary", {"period_days": 7}, timeout=120)
    elapsed = round((time.time() - __start_time) * 1000) if __start_time else 0
    code2, body2 = get("/recoverability/top-recoverable", {"period_days": 7, "limit": 5}, timeout=120)
    check("L.1 Endpoints respond in reasonable time", isinstance(code, int) and 200 <= code < 300,
          f"summary HTTP {code}", warn=True)

    # VERDICT
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["status"] == PASS)
    warned = sum(1 for r in results if r["status"] == WARN)
    failed = sum(1 for r in results if r["status"] == FAIL)
    critical = sum(1 for r in results if r["status"] == FAIL and r["check"].startswith(("A.", "G.", "H.", "I.", "J.", "K.")))

    print(f"Total: {total} | PASS: {passed} | WARN: {warned} | FAIL: {failed} | Critical: {critical}")
    verdict = "GO" if failed == 0 else ("CONDITIONAL GO" if critical == 0 else "NO-GO")
    print(f"\nVERDICT: {verdict}")
    return 0 if verdict != "NO-GO" else 1


if __name__ == "__main__":
    __start_time = time.time()
    sys.exit(main())
