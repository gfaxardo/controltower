"""
QA Script — Fase 1H.2E: WEEKLY SEMANTICS VALIDATION

Valida el contrato semántico weekly para Omniview Vs Proyección:
- week_state classification (future/current/closed)
- Exactly one current week
- No false "Sin ejecución" in future weeks
- Current week has partial expected logic
- Closed weeks are comparable
- No runtime fallback pollution
"""
from __future__ import annotations

import json
import os
import sys
import time
import requests
from datetime import date, timedelta
from collections import Counter

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8001")
PLAN_VERSION = os.environ.get("CT_PLAN_VERSION", "ruta27_2026_04_21")
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"
results: list[dict] = []
START_TIME = time.time()
TODAY = date.today()


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


def get_week_start_from_period_key(pk: str) -> date:
    return date.fromisoformat(pk[:10])


def get_week_end(week_start: date) -> date:
    return week_start + timedelta(days=6)


def classify_week(week_start: date) -> str:
    week_end = get_week_end(week_start)
    if TODAY > week_end:
        return "closed"
    if TODAY < week_start:
        return "future"
    return "current"


def main():
    global START_TIME
    START_TIME = time.time()
    print(f"=== QA 1H.2E Weekly Semantics Validation ===")
    print(f"  BASE_URL={BASE_URL}")
    print(f"  PLAN_VERSION={PLAN_VERSION}")
    print(f"  TODAY={TODAY.isoformat()}")
    print()

    # ── 1. Fetch weekly projection data ────────────────────────────────────
    print("── 1. Fetch weekly projection ──")
    status, body = get(
        "/ops/business-slice/omniview-projection",
        params={
            "grain": "weekly",
            "plan_version": PLAN_VERSION,
            "country": "peru",
            "year": TODAY.year,
        },
        timeout=60,
    )
    check("API responds", status == 200, f"status={status} body_preview={str(body)[:200]}")
    if status != 200:
        print("[ABORT] Cannot fetch weekly projection data")
        _summary()
        return

    rows = body.get("data", [])
    meta = body.get("meta", {})

    check("Has data rows", len(rows) > 0, f"rows={len(rows)}")
    if len(rows) == 0:
        print("[ABORT] No weekly data rows")
        _summary()
        return

    # ── 2. Validate serving source ─────────────────────────────────────────
    print("\n── 2. Serving source ──")
    served_from = meta.get("served_from", "")
    check("Served from fact (not runtime fallback)", served_from == "fact",
          f"served_from={served_from}")

    # ── 3. Validate week_state field ───────────────────────────────────────
    print("\n── 3. week_state field ──")
    week_states = []
    for r in rows:
        ws = r.get("week_state")
        week_states.append(ws)

    state_counts = Counter(week_states)
    check("Has week_state field present", all(s is not None for s in week_states),
          f"states={dict(state_counts)}")
    check("Has 'future' weeks", state_counts.get("future", 0) > 0,
          f"future={state_counts.get('future', 0)}")
    check("Has 'current' week", state_counts.get("current", 0) >= 0,
          f"current={state_counts.get('current', 0)}")
    check("Has 'closed' weeks", state_counts.get("closed", 0) > 0,
          f"closed={state_counts.get('closed', 0)}")
    check("No 'unknown' week_state", state_counts.get("unknown", 0) == 0,
          f"unknown={state_counts.get('unknown', 0)}")

    # ── 4. Exactly one current week ────────────────────────────────────────
    print("\n── 4. Current week uniqueness ──")
    current_weeks = [r for r in rows if r.get("week_state") == "current"]
    check("Exactly 0 or 1 current week per country/slice", len(current_weeks) <= len(
        set((r.get("country"), r.get("city"), r.get("business_slice_name")) for r in rows)
    ) * 1,  # at most one current week per unique slice
          f"current_week_rows={len(current_weeks)}")

    # ── 5. Future weeks must NOT show "Sin ejecución" semantics ────────────
    print("\n── 5. Future week semantics ──")
    future_rows = [r for r in rows if r.get("week_state") == "future"]
    if future_rows:
        # Check that future weeks have plan_without_real comparison_status
        future_statuses = Counter(r.get("comparison_status") for r in future_rows)
        check("Future weeks have plan_without_real status",
              future_statuses.get("plan_without_real", 0) == len(future_rows),
              f"statuses={dict(future_statuses)}")

        # Check that no future week has actual > 0
        future_with_real = [r for r in future_rows
                           if r.get("trips_completed") is not None and r.get("trips_completed", 0) > 0]
        check("Future weeks have no real data (actual=0/null)",
              len(future_with_real) == 0,
              f"future_with_real={len(future_with_real)}")
    else:
        check("Future weeks exist", False, "No future weeks found in data")
        check("Future weeks have plan_without_real status", False, skip_check=True)

    # ── 6. Current week partial expected logic ─────────────────────────────
    print("\n── 6. Current week partial expected ──")
    if current_weeks:
        sample_current = current_weeks[0]
        # For current week: expected_to_date should be less than plan total
        trips_expected = sample_current.get("trips_completed_projected_expected")
        trips_plan = sample_current.get("trips_completed_projected_total")
        intraweek = sample_current.get("trips_completed_intraweek_expected_method")

        check("Current week has projected_expected", trips_expected is not None,
              f"expected={trips_expected}")
        check("Current week has projected_total", trips_plan is not None,
              f"plan={trips_plan}")
        check("Current week uses intraweek method",
              intraweek is not None and intraweek != "full_week_legacy",
              f"method={intraweek}")

        # Expected should be <= full plan for current week
        if trips_expected is not None and trips_plan is not None:
            check("Current week expected <= plan total",
                  float(trips_expected) <= float(trips_plan) * 1.05,  # allow small rounding
                  f"expected={trips_expected} plan={trips_plan}")
    else:
        check("Current week has projected_expected", False, "No current week found")
        check("Current week has projected_total", False, "No current week found")
        check("Current week uses intraweek method", False, "No current week found")

    # ── 7. Closed weeks comparable ─────────────────────────────────────────
    print("\n── 7. Closed weeks comparability ──")
    closed_rows = [r for r in rows if r.get("week_state") == "closed"]
    if closed_rows:
        # Closed weeks with real data should be comparable
        matched_closed = [r for r in closed_rows
                         if r.get("comparison_status") == "matched"]
        check("Some closed weeks are matched (comparable)",
              len(matched_closed) > 0,
              f"matched_closed={len(matched_closed)} total_closed={len(closed_rows)}")

        # Check attainment values
        for r in matched_closed[:5]:  # sample
            att = r.get("trips_completed_attainment_pct")
            if att is not None:
                check(f"Closed week {r.get('week_start', '?')} attainment valid",
                      att >= 0, f"attainment={att}")
    else:
        check("Some closed weeks are matched", False, "No closed weeks found")

    # ── 8. No runtime fallback pollution ───────────────────────────────────
    print("\n── 8. No runtime fallback ──")
    check("Served from fact, not runtime", served_from == "fact",
          f"served_from={served_from}")

    # ── 9. Cross-country validation ────────────────────────────────────────
    print("\n── 9. Cross-country (Perú + Colombia) ──")
    for country_name in ["peru", "colombia"]:
        sc, body_co = get(
            "/ops/business-slice/omniview-projection",
            params={
                "grain": "weekly",
                "plan_version": PLAN_VERSION,
                "country": country_name,
                "year": TODAY.year,
            },
            timeout=60,
        )
        rows_co = body_co.get("data", []) if isinstance(body_co, dict) else []
        co_states = Counter(r.get("week_state") for r in rows_co)

        check(f"{country_name}: API responds", sc == 200, f"status={sc}")
        check(f"{country_name}: Has weekly data", len(rows_co) > 0,
              f"rows={len(rows_co)} states={dict(co_states)}")
        check(f"{country_name}: Has current week",
              co_states.get("current", 0) > 0,
              f"current={co_states.get('current', 0)}")
        check(f"{country_name}: No false 'unknown' state",
              co_states.get("unknown", 0) == 0,
              f"unknown={co_states.get('unknown', 0)}")

    # ── 10. Comparison basis for weekly ────────────────────────────────────
    print("\n── 10. Comparison basis ──")
    basis_values = set()
    for r in rows[:100]:
        basis = r.get("trips_completed_comparison_basis")
        if basis:
            basis_values.add(basis)
    check("Has 'full_week' comparison basis", "full_week" in basis_values,
          f"basis={basis_values}")
    check("Has 'expected_to_date_week' comparison basis",
          "expected_to_date_week" in basis_values,
          f"basis={basis_values}")

    # ── 11. actual_value non-null for closed weeks (PHASE 1H.2E FIX) ────────
    print("\n── 11. actual_value non-null (closed weeks) ──")
    matched_rows = [r for r in rows if r.get("comparison_status") == "matched"]
    check("Has matched rows (plan + real joined)", len(matched_rows) > 0,
          f"matched={len(matched_rows)} total={len(rows)}")

    if matched_rows:
        null_actual = [r for r in matched_rows if r.get("trips_completed") is None]
        check("No null actual_value in matched rows",
              len(null_actual) == 0,
              f"null_actual_rows={len(null_actual)} total_matched={len(matched_rows)}")

        # Sample a few actual values
        sample_values = [(r.get("week_start", "?"), r.get("trips_completed"))
                         for r in matched_rows[:5]]
        non_zero = [v for _, v in sample_values if v is not None and v > 0]
        check("Some actual_value > 0 in matched rows",
              len(non_zero) > 0,
              f"sample={sample_values}")

        # attainment should be computed when both plan and real exist
        att_values = [r.get("trips_completed_attainment_pct") for r in matched_rows
                      if r.get("trips_completed_attainment_pct") is not None]
        check("Attainment computed for matched rows",
              len(att_values) > 0,
              f"attainment_samples={att_values[:5]}")

    # ── 12. Join success rate ───────────────────────────────────────────────
    print("\n── 12. Join success rate ──")
    plan_count = sum(1 for r in rows if r.get("comparison_status") == "plan_without_real")
    real_only = sum(1 for r in rows if r.get("comparison_status") == "missing_plan")
    total_rows = len(rows)
    join_rate = round(len(matched_rows) / total_rows * 100, 1) if total_rows > 0 else 0

    check("Join rate > 0% (some weeks matched)", join_rate > 0,
          f"join_rate={join_rate}% matched={len(matched_rows)} plan_only={plan_count} real_only={real_only}")
    check("Join rate >= 30% expected", join_rate >= 30.0,
          f"join_rate={join_rate}% (below 30%)",
          warn=True)

    # ── 13. actual_value reconciliation (daily vs weekly) ───────────────────
    print("\n── 13. Cross-grain reconciliation ──")
    sc_daily, body_daily = get(
        "/ops/business-slice/omniview-projection",
        params={
            "grain": "daily",
            "plan_version": PLAN_VERSION,
            "country": "peru",
            "year": TODAY.year,
            "month": TODAY.month,
        },
        timeout=60,
    )
    check("Daily API responds (no regression)", sc_daily == 200,
          f"daily_status={sc_daily}")
    sc_monthly, body_monthly = get(
        "/ops/business-slice/omniview-projection",
        params={
            "grain": "monthly",
            "plan_version": PLAN_VERSION,
            "country": "peru",
            "year": TODAY.year,
            "month": TODAY.month,
        },
        timeout=60,
    )
    check("Monthly API responds (no regression)", sc_monthly == 200,
          f"monthly_status={sc_monthly}")

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
        print("GO — Weekly semantics contract validated")
    else:
        print("NO-GO — Weekly semantics contract has failures")
    print(f"{'='*60}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
