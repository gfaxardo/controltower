"""
QA Script — Fase 1H.2G: COUNTRY FILTER CONTRACT VALIDATION

Valida que el filtro de país funcione end-to-end:
- endpoint all countries devuelve más de un país
- endpoint peru solo peru
- endpoint colombia solo colombia
- no fallback runtime
- fact coverage por país
"""
from __future__ import annotations

import os
import sys
import time
import requests
from collections import Counter

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8000")
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
    try:
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=timeout)
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
    print(f"=== QA 1H.2G Country Filter Contract Validation ===")
    print(f"  BASE_URL={BASE_URL}")
    print(f"  PLAN_VERSION={PLAN_VERSION}")
    print()

    grains = ["weekly", "daily", "monthly"]
    year = 2026
    country_cases = [
        ("ALL (no country)", None),
        ("Peru", "peru"),
        ("Colombia", "colombia"),
    ]

    for grain in grains:
        print(f"\n── {grain.upper()} ──")
        grain_params = {"plan_version": PLAN_VERSION, "grain": grain, "year": year}
        if grain == "daily":
            grain_params["month"] = 5

        for case_label, country_val in country_cases:
            params = dict(grain_params)
            if country_val:
                params["country"] = country_val

            status, body = get(
                "/ops/business-slice/omniview-projection",
                params=params,
                timeout=60,
            )
            check(
                f"{grain} {case_label}: API responds",
                status == 200,
                f"status={status}",
            )
            if status != 200:
                continue

            rows = body.get("data", [])
            meta = body.get("meta", {})

            check(
                f"{grain} {case_label}: served_from=fact",
                meta.get("served_from") == "fact",
                f"served_from={meta.get('served_from')}",
            )

            check(
                f"{grain} {case_label}: has rows",
                len(rows) > 0,
                f"rows={len(rows)}",
            )

            # Country specificity check
            countries_in_data = set(r.get("country", "") for r in rows)

            if country_val is None:
                # ALL — should have more than one country
                check(
                    f"{grain} {case_label}: multiple countries",
                    len(countries_in_data) >= 2,
                    f"countries={countries_in_data}",
                )
            else:
                # Specific country — should ONLY have that country
                check(
                    f"{grain} {case_label}: only {country_val}",
                    countries_in_data == {country_val},
                    f"countries={countries_in_data}",
                )

            # Actual values check
            matched = [r for r in rows if r.get("comparison_status") == "matched"]
            with_actual = [r for r in matched if r.get("trips_completed") is not None and r.get("trips_completed") > 0]
            check(
                f"{grain} {case_label}: has matched rows",
                len(matched) > 0,
                f"matched={len(matched)}",
            )
            check(
                f"{grain} {case_label}: has actual_value > 0",
                len(with_actual) > 0,
                f"with_actual={len(with_actual)}",
            )

            # Comparison basis
            bases = set(r.get("trips_completed_comparison_basis") for r in matched[:50] if r.get("trips_completed_comparison_basis"))
            check(
                f"{grain} {case_label}: comparison_basis present",
                len(bases) > 0,
                f"bases={bases}",
            )

    _summary()


def _summary():
    elapsed = time.time() - START_TIME
    passed = sum(1 for r in results if r["status"] == PASS)
    failed = sum(1 for r in results if r["status"] == FAIL)
    warned = sum(1 for r in results if r["status"] == WARN)
    total = len(results)

    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} PASS, {failed} FAIL, {warned} WARN ({elapsed:.1f}s)")
    if failed == 0:
        print("GO — Country filter contract validated")
    else:
        print("NO-GO — Country filter contract has failures")
    print(f"{'='*60}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
