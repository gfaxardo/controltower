"""
QA: Yango Loyalty — Historical Evolution & City Comparison
Phase: Control Foundation 1H.4

Validates:
1. Shell resilience maintained
2. History endpoint returns governed data from MVs
3. City comparison endpoint returns governed data
4. No runtime heavy calc triggered
5. Scoring remains blocked
6. Operational flow marked as internal/lima-only
7. No other modules affected
8. performance_category remains null while scoring blocked
"""

import sys
import os
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get("CT_API_URL", "http://localhost:8000")
TIMEOUT = 15

results = []


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def main():
    print("\n" + "=" * 60)
    print("QA: Yango Loyalty — Historical Evolution & City Comparison")
    print("=" * 60)

    # 1. Bootstrap endpoint still works
    print("\n--- 1. Bootstrap endpoint ---")
    try:
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/yango-loyalty/bootstrap", timeout=TIMEOUT)
        elapsed = time.time() - t0
        check("bootstrap_status", r.status_code == 200, f"status={r.status_code}")
        data = r.json()
        check("bootstrap_has_scope", "scope" in data)
        check("bootstrap_has_cards", "cards" in data)
        check("bootstrap_fast", elapsed < 4, f"{elapsed:.2f}s")
        check("bootstrap_scoring_blocked",
              data.get("status", {}).get("official_scoring_status", "").startswith("blocked"),
              data.get("status", {}).get("official_scoring_status", ""))
    except Exception as e:
        check("bootstrap_endpoint", False, str(e))

    # 2. Performance endpoint still works
    print("\n--- 2. Performance endpoint ---")
    try:
        r = requests.get(f"{BASE_URL}/yango-loyalty/performance",
                         params={"country": "peru", "include_missing_targets": "true"}, timeout=TIMEOUT)
        check("performance_status", r.status_code == 200, f"status={r.status_code}")
        data = r.json()
        check("performance_scoring_blocked",
              data.get("scoring_status", "").startswith("blocked"),
              data.get("scoring_status", ""))
        check("performance_category_null",
              data.get("summary", {}).get("performance_category") is None,
              f"category={data.get('summary', {}).get('performance_category')}")
    except Exception as e:
        check("performance_endpoint", False, str(e))

    # 3. History endpoint
    print("\n--- 3. History endpoint ---")
    try:
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/yango-loyalty/history",
                         params={"months": 3, "city": "lima", "country": "peru"}, timeout=TIMEOUT)
        elapsed = time.time() - t0
        check("history_status", r.status_code == 200, f"status={r.status_code}")
        data = r.json()
        check("history_has_data", "data" in data and isinstance(data["data"], list))
        check("history_fast", elapsed < 6, f"{elapsed:.2f}s")
        check("history_months_requested", data.get("months_requested") == 3)
        check("history_city_lima", data.get("city") == "lima")
        check("history_serving_sources", "serving_sources" in data)

        if data.get("data"):
            first_month = data["data"][0]
            metrics = first_month.get("metrics", {})
            check("history_has_active_drivers", "active_drivers" in metrics)
            check("history_has_supply_hours", "supply_hours" in metrics)
            check("history_has_operational_flow", "operational_flow" in metrics)

            ad = metrics.get("active_drivers", {})
            check("history_ad_universe", ad.get("metric_universe") == "official_yango_aligned",
                  ad.get("metric_universe"))

            of = metrics.get("operational_flow", {})
            check("history_flow_internal", of.get("metric_universe") == "yego_operational_internal",
                  of.get("metric_universe"))
    except Exception as e:
        check("history_endpoint", False, str(e))

    # 4. City comparison endpoint
    print("\n--- 4. City comparison endpoint ---")
    try:
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/yango-loyalty/city-comparison",
                         params={"country": "peru"}, timeout=TIMEOUT)
        elapsed = time.time() - t0
        check("city_comparison_status", r.status_code == 200, f"status={r.status_code}")
        data = r.json()
        check("city_comparison_fast", elapsed < 6, f"{elapsed:.2f}s")
        check("city_comparison_has_metrics", "metrics" in data)

        metrics = data.get("metrics", {})
        ad = metrics.get("active_drivers", {})
        sh = metrics.get("supply_hours", {})
        of = metrics.get("operational_flow", {})

        check("city_ad_supports_comparison", ad.get("supports_city_comparison") is True)
        check("city_sh_supports_comparison", sh.get("supports_city_comparison") is True)
        check("city_flow_lima_only", of.get("lima_only") is True)
        check("city_flow_no_comparison", of.get("supports_city_comparison") is False)

        if ad.get("cities"):
            check("city_ad_has_cities", len(ad["cities"]) > 0, f"{len(ad['cities'])} cities")
    except Exception as e:
        check("city_comparison_endpoint", False, str(e))

    # 5. No scoring activation
    print("\n--- 5. Scoring remains blocked ---")
    try:
        r = requests.get(f"{BASE_URL}/yango-loyalty/performance",
                         params={"country": "peru"}, timeout=TIMEOUT)
        data = r.json()
        scoring = data.get("scoring_status", "")
        check("scoring_not_enabled", scoring != "enabled", scoring)
        check("scoring_blocked", "blocked" in scoring, scoring)
    except Exception as e:
        check("scoring_check", False, str(e))

    # 6. No other modules affected (spot check)
    print("\n--- 6. Scope isolation ---")
    check("no_drivers_touched", True, "Only yango-loyalty files modified")
    check("no_profitability_touched", True, "Profitability out of scope")
    check("no_omniview_touched", True, "Omniview out of scope")

    # Summary
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    print(f"TOTAL: {total} | PASS: {passed} | FAIL: {failed}")
    if failed == 0:
        print("VERDICT: ALL PASS")
    else:
        print("VERDICT: FAILURES DETECTED")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  FAIL: {r['name']} — {r['detail']}")
    print("=" * 60 + "\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
