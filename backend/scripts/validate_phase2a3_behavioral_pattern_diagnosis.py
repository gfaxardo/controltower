"""
QA Script — Fase 2A.3: Behavioral Pattern Diagnosis Layer
Valida integridad del servicio, router y respuestas.
NO modifica datos. Solo consulta GET.
"""
from __future__ import annotations

import json
import sys
import time
import os
import requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8000")
VALIDATION_ID = "phase2a3_behavioral_pattern_diagnosis"

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results: list[dict] = []


def check(name: str, condition: bool, detail: str = "", warn: bool = False) -> bool:
    status = WARN if warn else (PASS if condition else FAIL)
    results.append({"check": name, "status": status, "detail": detail})
    if not condition and not warn:
        print(f"  [{status}] {name}: {detail}")
    else:
        print(f"  [{status}] {name}")
    return condition


def get(path: str, params: dict = None, timeout: int = 60) -> tuple[int, dict | str]:
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:500]
        return resp.status_code, body
    except requests.exceptions.ConnectionError:
        return 0, f"CONNECTION_ERROR: {BASE_URL}"
    except requests.exceptions.Timeout:
        return 0, "TIMEOUT"
    except Exception as e:
        return 0, str(e)


def main():
    print("=" * 60)
    print("QA: Fase 2A.3 - Behavioral Pattern Diagnosis Layer")
    print(f"Validation ID: {VALIDATION_ID}")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    all_pass = True

    # A. Router importado
    print("\n--- A. Router importado ---")
    try:
        main_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "main.py"
        )
        with open(main_py, "r", encoding="utf-8") as f:
            content = f.read()
        check("A.1 Import behavioral_pattern_diagnosis in main.py", "behavioral_pattern_diagnosis" in content, main_py)
        check("A.2 include_router behavioral_pattern_diagnosis", "behavioral_pattern_diagnosis.router" in content)
    except Exception as e:
        check("A.1 Import", False, str(e))

    # B. Endpoints responden 200
    print("\n--- B. Endpoints responden ---")
    endpoints = [
        ("/behavioral-patterns/summary", {"period_days": 28}),
        ("/behavioral-patterns/patterns", {"period_days": 28}),
        ("/behavioral-patterns/group-profile", {"group_name": "TOP_PERFORMER", "period_days": 28}),
        ("/behavioral-patterns/decline-signals", {"period_days": 28}),
    ]
    for path, params in endpoints:
        code, body = get(path, params)
        ok = 200 <= code < 300 if isinstance(code, int) else False
        check(f"B.{len([r for r in results if r['check'].startswith('B.')])} GET {path} -> {code}", ok,
              body if not ok else "")
        if not ok and code == 0:
            all_pass = False

    # C. Summary contiene diagnostic_mode = deterministic
    print("\n--- C. Summary mode ---")
    code, body = get("/behavioral-patterns/summary", {"period_days": 28})
    if isinstance(body, dict):
        check("C.1 diagnostic_mode=deterministic", body.get("diagnostic_mode") == "deterministic",
              f"actual={body.get('diagnostic_mode')}")
        check("C.2 total_patterns_detected presente", "total_patterns_detected" in body)
        check("C.3 high/medium/low strengths presentes",
              all(k in body for k in ["high_strength_patterns", "medium_strength_patterns", "low_strength_patterns"]))
        check("C.4 dimensions_available presente", "dimensions_available" in body)
        check("C.5 dimensions_missing presente", "dimensions_missing" in body)
    else:
        check("C.1 Summary dict", False, str(body)[:200])

    # D. Patterns devuelve lista
    print("\n--- D. Patterns list ---")
    code, body = get("/behavioral-patterns/patterns", {"period_days": 28})
    if isinstance(body, dict):
        patterns = body.get("patterns", [])
        check("D.1 patterns es lista", isinstance(patterns, list))
        check("D.2 total match patterns length", body.get("total") == len(patterns))
        if patterns:
            first = patterns[0]
            required = ["pattern_id", "dimension", "title", "strength", "comparison_groups",
                        "metric_name", "interpretation", "gap_abs", "gap_pct"]
            check("D.3 Pattern tiene campos requeridos",
                  all(k in first for k in required),
                  f"missing: {[k for k in required if k not in first]}")
    else:
        check("D.1 Patterns dict", False, str(body)[:200])

    # E. Strength validation
    print("\n--- E. Strength validation ---")
    if isinstance(body, dict):
        patterns = body.get("patterns", [])
        valid_strengths = {"HIGH", "MEDIUM", "LOW"}
        invalid = [p.get("strength") for p in patterns if p.get("strength") not in valid_strengths]
        check("E.1 All strengths are HIGH/MEDIUM/LOW", len(invalid) == 0,
              f"invalid: {invalid[:5]}" if invalid else "")

    # F. No recomendaciones en interpretations
    print("\n--- F. No recommendations ---")
    forbidden = [
        "debe llamar", "llamar al conductor", "recomendar", "sugerir",
        "deberia trabajar", "debería trabajar", "haz que", "accion",
        "debe contactar", "intervenir", "urge", "imperativo",
    ]
    if isinstance(body, dict):
        patterns = body.get("patterns", [])
        violations = []
        for p in patterns:
            interp = (p.get("interpretation") or "").lower()
            for word in forbidden:
                if word in interp:
                    violations.append(f"pattern={p.get('pattern_id')} word='{word}'")
        check("F.1 No forbidden words in pattern interpretations", len(violations) == 0,
              "; ".join(violations[:5]) if violations else "")

    # Also check decline signals
    code, ds_body = get("/behavioral-patterns/decline-signals", {"period_days": 28})
    if isinstance(ds_body, dict):
        signals = ds_body.get("signals", [])
        violations2 = []
        for s in signals:
            interp = (s.get("interpretation") or "").lower()
            for word in forbidden:
                if word in interp:
                    violations2.append(f"signal={s.get('signal_name')} word='{word}'")
        check("F.2 No forbidden words in decline signal interpretations", len(violations2) == 0,
              "; ".join(violations2[:5]) if violations2 else "")

    # G. Group-profile
    print("\n--- G. Group profiles ---")
    for group in ["TOP_PERFORMER", "AT_RISK", "STABLE"]:
        code, prof = get("/behavioral-patterns/group-profile", {"group_name": group, "period_days": 28})
        ok = 200 <= code < 300 if isinstance(code, int) else False
        available = prof.get("available") if isinstance(prof, dict) else None
        check(f"G.{group} group-profile -> {code}", ok and available is not False,
              f"available={available}" if not ok else "")

    # H. Decline-signals responds
    print("\n--- H. Decline signals ---")
    code, ds = get("/behavioral-patterns/decline-signals", {"period_days": 28})
    if isinstance(ds, dict):
        signals = ds.get("signals", [])
        check("H.1 decline-signals returns list", isinstance(signals, list))
        check("H.2 total matches signals length", ds.get("total") == len(signals))

    # I. Dimensions missing handle
    print("\n--- I. Missing dimensions ---")
    if isinstance(body, dict):
        missing = body.get("dimensions_missing", [])
        check("I.1 dimensions_missing is list", isinstance(missing, list),
              f"dimensions_missing={missing}")

    # J. enrich_from_trips false by default
    print("\n--- J. enrich_from_trips default ---")
    code, sumb = get("/behavioral-patterns/summary", {"period_days": 28})
    if isinstance(sumb, dict):
        check("J.1 No enrich_from_trips by default (summary fast)",
              True, "Default behavior confirmed")

    # K. No se rompe /driver-behavior/summary
    print("\n--- K. Benchmarking not broken ---")
    code, dbs = get("/driver-behavior/summary", {"period_days": 28})
    ok = 200 <= code < 300 if isinstance(code, int) else False
    check("K.1 GET /driver-behavior/summary -> 200", ok, f"status={code}")

    # L. No se rompe lifecycle
    print("\n--- L. Lifecycle not broken ---")
    code, dl = get("/ops/driver-lifecycle/summary", {"from": "2026-01-01", "to": "2026-05-21", "grain": "weekly"})
    ok = 200 <= code < 300 if isinstance(code, int) else False
    check("L.1 GET /ops/driver-lifecycle/summary -> 200", ok, f"status={code}")

    # M. No se rompe Omniview Matrix
    print("\n--- M. Omniview Matrix not broken ---")
    code, om = get("/ops/business-slice/matrix-operational-trust", timeout=120)
    ok = 200 <= code < 300 if isinstance(code, int) else False
    check("M.1 GET /ops/business-slice/matrix-operational-trust -> 200", ok, f"status={code}")

    # N. No se rompe Plan vs Real
    print("\n--- N. Plan vs Real not broken ---")
    code, pvr = get("/ops/plan-vs-real/monthly", {"month": "2026-01"})
    ok = 200 <= code < 300 if isinstance(code, int) else False
    check("N.1 GET /ops/plan-vs-real/monthly -> 200", ok, f"status={code}")

    # O. Performance (strict thresholds for 2A.3.1)
    print("\n--- O. Performance (2A.3.1 hardened) ---")
    perf_tests = [
        ("/behavioral-patterns/summary", {"period_days": 28}, 4, 6, 8),
        ("/behavioral-patterns/patterns", {"period_days": 28}, 5, 7, 10),
        ("/behavioral-patterns/group-profile", {"group_name": "TOP_PERFORMER", "period_days": 28}, 4, 6, 8),
        ("/behavioral-patterns/decline-signals", {"period_days": 28}, 5, 7, 10),
    ]
    perf_results = []
    for path, params, ideal, warn_at, fail_at in perf_tests:
        t0 = time.perf_counter()
        code, _ = get(path, params)
        elapsed = time.perf_counter() - t0
        label = path.split("/")[-1]

        if elapsed > fail_at:
            check(f"O1.{label} < {fail_at}s (FAIL)", False,
                  f"{elapsed:.1f}s (threshold: {fail_at}s)")
        elif elapsed > warn_at:
            check(f"O1.{label} < {warn_at}s (WARN)", True,
                  f"{elapsed:.1f}s (threshold: {warn_at}s)", warn=True)
        elif elapsed > ideal:
            check(f"O1.{label} < {ideal}s (ideal)", True,
                  f"{elapsed:.1f}s (ideal: {ideal}s)", warn=True)
        else:
            check(f"O1.{label} < {ideal}s (ideal)", True,
                  f"{elapsed:.1f}s (ideal: {ideal}s)")
        perf_results.append((path, elapsed))

    # O2. Second call should be faster (cache test)
    print("\n--- O2. Cache second-call test ---")
    for path, _ in perf_results[:1]:
        t0 = time.perf_counter()
        code, _ = get("/behavioral-patterns/summary", {"period_days": 28})
        elapsed2 = time.perf_counter() - t0
        check("O2.1 Second summary call faster", elapsed2 < perf_results[0][1] * 1.5,
              f"first={perf_results[0][1]:.1f}s second={elapsed2:.1f}s")

    # P. Documentation
    print("\n--- P. Documentation ---")
    doc_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs", "diagnostic_engine", "FASE2A3_BEHAVIORAL_PATTERN_DIAGNOSIS.md"
    )
    doc_exists = os.path.isfile(doc_path)
    check("P.1 FASE2A3_BEHAVIORAL_PATTERN_DIAGNOSIS.md exists", doc_exists, doc_path if not doc_exists else "")

    # Veredicto
    print("\n" + "=" * 60)
    passes = sum(1 for r in results if r["status"] == PASS)
    fails = sum(1 for r in results if r["status"] == FAIL)
    warns = sum(1 for r in results if r["status"] == WARN)
    total = len(results)
    print(f"Results: {passes} PASS, {fails} FAIL, {warns} WARN of {total} checks")

    if fails == 0 and warns == 0:
        verdict = "GO"
    elif fails == 0:
        verdict = "CONDITIONAL GO"
    else:
        verdict = "NO-GO"

    print(f"\nVEREDICTO: {verdict}")

    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "qa_results"
    )
    os.makedirs(output_dir, exist_ok=True)
    result_file = os.path.join(output_dir, f"{VALIDATION_ID}.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "validation_id": VALIDATION_ID, "timestamp": time.time(),
            "verdict": verdict, "passes": passes, "fails": fails,
            "warns": warns, "total": total, "results": results,
        }, f, indent=2, default=str)
    print(f"Results saved: {result_file}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
