"""
CF-H1L.3 — Freshness Pipeline Resilience Audit

Read-only QA script that audits the freshness pipeline end-to-end:
  coverage_by_grain, latest_date_by_grain, missing_periods, serving_vs_fact,
  freshness_endpoint_consistency, startup_guard_output, remediation_presence,
  stale_detection, blocked_detection, dependency_graph_completeness.

Exit codes: 0 = PASS (no blocking FAIL), 1 = FAIL (blocking issue detected)

Usage: cd backend && python -m scripts.audit_freshness_pipeline_resilience
       cd backend && python -m scripts.audit_freshness_pipeline_resilience --json
       cd backend && python -m scripts.audit_freshness_pipeline_resilience --quiet
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db
from app.services.business_slice_service import FACT_DAILY, FACT_WEEKLY, FACT_MONTHLY
from psycopg2.extras import RealDictCursor

RESULTS: List[Dict[str, Any]] = []
FAIL_COUNT = 0
WARN_COUNT = 0
PASS_COUNT = 0
QUIET = False


def r(label: str, status: str, detail: str = ""):
    global FAIL_COUNT, WARN_COUNT, PASS_COUNT
    s = status.upper()
    if s == "FAIL":
        FAIL_COUNT += 1
    elif s == "WARNING":
        WARN_COUNT += 1
    elif s == "PASS":
        PASS_COUNT += 1
    RESULTS.append({"label": label, "status": s, "detail": detail})
    if not QUIET:
        icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARNING": "[WARN]"}[s]
        print(f"  {icon} {label}")
        if detail:
            print(f"       {detail}")


def fmt(v):
    if v is None:
        return 'NULL'
    if isinstance(v, float) and math.isfinite(v):
        return f"{v:,.2f}"
    return f"{int(v):,}"


def _iso_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _closed_months(count: int = 2) -> List[date]:
    today = date.today()
    months = []
    cursor = date(today.year, today.month, 1)
    for _ in range(count):
        if cursor.month == 1:
            cursor = date(cursor.year - 1, 12, 1)
        else:
            cursor = date(cursor.year, cursor.month - 1, 1)
        months.append(cursor)
    return sorted(months)


def _closed_iso_weeks(count: int = 5) -> List[date]:
    today = date.today()
    current_monday = _iso_monday(today)
    weeks = []
    for i in range(1, count + 1):
        weeks.append(current_monday - timedelta(weeks=i))
    return sorted(weeks)


def _month_first(d: date) -> date:
    return date(d.year, d.month, 1)


def _check_coverage_by_grain(cur, months: List[date]):
    lowest = months[0]
    highest_month = months[-1]
    if highest_month.month == 12:
        next_after = date(highest_month.year + 1, 1, 1)
    else:
        next_after = date(highest_month.year, highest_month.month + 1, 1)

    month_strs = [m.isoformat() for m in months]

    # day_fact
    try:
        cur.execute(
            f"""
            SELECT COUNT(*)::bigint AS rows,
                   MIN(trip_date) AS min_d, MAX(trip_date) AS max_d,
                   COALESCE(SUM(trips_completed), 0)::bigint AS trips
            FROM {FACT_DAILY}
            WHERE trip_date >= %s::date AND trip_date < %s::date
            """,
            (lowest.isoformat(), next_after.isoformat()),
        )
        row = dict(cur.fetchone() or {})
        rows_n = row.get("rows") or 0
        min_d = row.get("min_d")
        max_d = row.get("max_d")
        trips_n = row.get("trips") or 0
        r("1.1 day_fact coverage (last 2 closed months)",
          "PASS" if rows_n > 0 else "FAIL",
          f"rows={fmt(rows_n)} min={min_d} max={max_d} trips={fmt(trips_n)}")
    except Exception as e:
        r("1.1 day_fact coverage", "FAIL", f"Query error: {e}")

    # week_fact
    try:
        cur.execute(
            f"""
            SELECT COUNT(*)::bigint AS rows,
                   MIN(week_start) AS min_w, MAX(week_start) AS max_w,
                   COALESCE(SUM(trips_completed), 0)::bigint AS trips
            FROM {FACT_WEEKLY}
            WHERE week_start >= %s::date AND week_start < %s::date
            """,
            (lowest.isoformat(), next_after.isoformat()),
        )
        row = dict(cur.fetchone() or {})
        rows_n = row.get("rows") or 0
        min_w = row.get("min_w")
        max_w = row.get("max_w")
        trips_n = row.get("trips") or 0
        r("1.2 week_fact coverage (last 2 closed months)",
          "PASS" if rows_n > 0 else "FAIL",
          f"rows={fmt(rows_n)} min={min_w} max={max_w} trips={fmt(trips_n)}")
    except Exception as e:
        r("1.2 week_fact coverage", "FAIL", f"Query error: {e}")

    # month_fact
    try:
        placeholders = ", ".join(["%s"] * len(month_strs))
        cur.execute(
            f"""
            SELECT COUNT(*)::bigint AS rows,
                   MIN(month) AS min_m, MAX(month) AS max_m,
                   COALESCE(SUM(trips_completed), 0)::bigint AS trips
            FROM {FACT_MONTHLY}
            WHERE month::date IN ({placeholders})
            """,
            month_strs,
        )
        row = dict(cur.fetchone() or {})
        rows_n = row.get("rows") or 0
        min_m = row.get("min_m")
        max_m = row.get("max_m")
        trips_n = row.get("trips") or 0
        r("1.3 month_fact coverage (last 2 closed months)",
          "PASS" if rows_n > 0 else "FAIL",
          f"rows={fmt(rows_n)} min={min_m} max={max_m} trips={fmt(trips_n)}")
    except Exception as e:
        r("1.3 month_fact coverage", "FAIL", f"Query error: {e}")


def _check_latest_date_by_grain(cur):
    today = date.today()

    # day_fact
    try:
        cur.execute(f"SELECT MAX(trip_date) AS mx FROM {FACT_DAILY}")
        row = dict(cur.fetchone() or {})
        max_d = row.get("mx")
        if max_d and hasattr(max_d, "isoformat"):
            max_d_str = max_d.isoformat()
        elif max_d:
            max_d_str = str(max_d)[:10]
        else:
            max_d_str = None
        lag = (today - date.fromisoformat(max_d_str)).days if max_d_str else None
        status = "FAIL" if lag is None or lag > 3 else ("WARNING" if lag > 1 else "PASS")
        r("2.1 day_fact max date", status,
          f"max={max_d_str} lag_days={lag}")
    except Exception as e:
        r("2.1 day_fact max date", "FAIL", f"Query error: {e}")

    # week_fact
    try:
        cur.execute(f"SELECT MAX(week_start) AS mx FROM {FACT_WEEKLY}")
        row = dict(cur.fetchone() or {})
        max_w = row.get("mx")
        if max_w and hasattr(max_w, "isoformat"):
            max_w_str = max_w.isoformat()
        elif max_w:
            max_w_str = str(max_w)[:10]
        else:
            max_w_str = None
        current_monday = _iso_monday(today)
        weeks_behind = ((current_monday - date.fromisoformat(max_w_str)).days // 7) if max_w_str else None
        status = "FAIL" if weeks_behind is None or weeks_behind > 2 else ("WARNING" if weeks_behind > 1 else "PASS")
        r("2.2 week_fact max week_start", status,
          f"max={max_w_str} weeks_behind={weeks_behind}")
    except Exception as e:
        r("2.2 week_fact max week_start", "FAIL", f"Query error: {e}")

    # month_fact
    try:
        cur.execute(f"SELECT MAX(month) AS mx FROM {FACT_MONTHLY}")
        row = dict(cur.fetchone() or {})
        max_m = row.get("mx")
        if max_m and hasattr(max_m, "isoformat"):
            max_m_str = max_m.isoformat()
        elif max_m:
            max_m_str = str(max_m)[:10]
        else:
            max_m_str = None
        if max_m_str:
            max_md = date.fromisoformat(max_m_str + "-01" if len(max_m_str) == 7 else max_m_str)
            month_behind = (today.year - max_md.year) * 12 + (today.month - max_md.month)
        else:
            month_behind = None
        status = "FAIL" if month_behind is None or month_behind > 1 else ("WARNING" if month_behind == 1 else "PASS")
        r("2.3 month_fact max month", status,
          f"max={max_m_str} months_behind={month_behind}")
    except Exception as e:
        r("2.3 month_fact max month", "FAIL", f"Query error: {e}")


def _check_missing_periods(integrity_result: Dict[str, Any]):
    try:
        missing = integrity_result.get("missing_periods", [])
        if not missing:
            r("3.1 missing_periods", "PASS", "No missing periods detected")
        else:
            count = len(missing)
            grains = sorted(set(p.get("grain", "?") for p in missing))
            r("3.1 missing_periods", "FAIL",
              f"{count} missing period(s) across grains: {', '.join(grains)}")
            for mp in missing[:5]:
                r("3.2 missing_period detail", "FAIL",
                  f"grain={mp.get('grain')} period={mp.get('period')} "
                  f"day={mp.get('day_fact_rows', 'N/A')} "
                  f"month={mp.get('month_fact_rows', 'N/A')} "
                  f"week={mp.get('week_fact_rows', 'N/A')} "
                  f"serving={mp.get('serving_rows', 'N/A')}")
    except Exception as e:
        r("3.1 missing_periods", "FAIL", f"Error reading missing_periods: {e}")


def _check_serving_vs_fact(cur, weeks: List[date]):
    SERVING_TABLE = "serving.omniview_projection_daily_fact"
    has_issues = False
    for ws in weeks:
        ws_str = ws.isoformat()
        try:
            cur.execute(
                f"""
                SELECT COALESCE(SUM(trips_completed), 0)::bigint AS trips
                FROM {FACT_WEEKLY}
                WHERE week_start = %s::date
                """,
                (ws_str,),
            )
            fact_trips = int(dict(cur.fetchone() or {}).get("trips") or 0)

            cur.execute(
                f"""
                SELECT COALESCE(SUM(trips_completed), 0)::bigint AS trips
                FROM {SERVING_TABLE}
                WHERE grain = 'weekly' AND period_key = %s
                """,
                (ws_str,),
            )
            sv_trips = int(dict(cur.fetchone() or {}).get("trips") or 0)

            if fact_trips == 0 and sv_trips > 0:
                r(f"4.x week {ws_str} serving-without-fact",
                  "FAIL",
                  f"serving={fmt(sv_trips)} fact=0")
                has_issues = True
            elif fact_trips > 0 and sv_trips == 0:
                r(f"4.x week {ws_str} fact-without-serving",
                  "WARNING",
                  f"fact={fmt(fact_trips)} serving=0")
                has_issues = True
            elif fact_trips > 0 and sv_trips > 0:
                denom = max(fact_trips, sv_trips)
                diff = abs(fact_trips - sv_trips)
                diff_pct = (diff / denom * 100) if denom > 0 else 0
                if diff_pct > 1:
                    r(f"4.x week {ws_str} trips mismatch",
                      "WARNING",
                      f"fact={fmt(fact_trips)} serving={fmt(sv_trips)} diff={diff_pct:.2f}%")
                    has_issues = True
        except Exception as e:
            r(f"4.x week {ws_str} serving_vs_fact", "WARNING", f"Query error: {e}")

    if not has_issues:
        r("4.5 serving_vs_fact (last 5 ISO weeks)", "PASS",
          f"All {len(weeks)} weeks reconciled")


def _check_freshness_endpoint_consistency(freshness_result: Dict[str, Any]):
    expected_keys = {"status", "raw", "facts", "serving", "cross_validation", "message", "remediation"}
    actual_keys = set(freshness_result.keys())
    missing_keys = expected_keys - actual_keys
    if not missing_keys:
        r("5.1 freshness_endpoint_consistency", "PASS",
          f"All {len(expected_keys)} expected keys present")
    else:
        r("5.1 freshness_endpoint_consistency", "FAIL",
          f"Missing keys: {', '.join(sorted(missing_keys))}")

    status = freshness_result.get("status", "error")
    if status == "error":
        r("5.2 freshness governance status", "FAIL",
          f"Governance returned status=error: {freshness_result.get('message', '')[:120]}")
    else:
        r("5.2 freshness governance status", "PASS",
          f"Overall status: {status}")


def _check_startup_guard_output(integrity_result: Dict[str, Any]):
    try:
        status = integrity_result.get("status", "error")
        if status == "error":
            r("6.1 startup_guard status", "FAIL",
              f"Integrity guard returned error: {integrity_result.get('message', '')[:120]}")
            return
        r("6.1 startup_guard status", "PASS",
          f"Returned status={status}, checks={len(integrity_result.get('checks', []))}")

        remediation = integrity_result.get("remediation")
        if status in ("blocked", "warning"):
            if remediation:
                r("6.2 startup_guard remediation", "PASS",
                  "Remediation text present")
            else:
                r("6.2 startup_guard remediation", "FAIL",
                  f"Status={status} but no remediation text")
        else:
            r("6.2 startup_guard remediation", "PASS",
              "No remediation needed (status ok)")
    except Exception as e:
        r("6.1 startup_guard output", "FAIL", f"Error: {e}")


def _check_remediation_presence(integrity_result: Dict[str, Any]):
    try:
        status = integrity_result.get("status", "error")
        remediation = integrity_result.get("remediation")
        if status == "blocked":
            if remediation and isinstance(remediation, str) and len(remediation.strip()) > 10:
                r("7.1 remediation_presence (blocked)", "PASS",
                  f"Remediation: {remediation[:100]}...")
            else:
                r("7.1 remediation_presence (blocked)", "FAIL",
                  "BLOCKED status but missing or empty remediation text")
        else:
            r("7.1 remediation_presence", "PASS",
              f"Not blocked (status={status}), no remediation required")
    except Exception as e:
        r("7.1 remediation_presence", "FAIL", f"Error: {e}")


def _check_stale_detection(cur):
    SERVING_TABLE = "serving.omniview_projection_daily_fact"
    today = date.today()
    try:
        cur.execute(f"SELECT MAX(trip_date) AS mx FROM {FACT_DAILY}")
        row = dict(cur.fetchone() or {})
        day_max = row.get("mx")
        if day_max and hasattr(day_max, "isoformat"):
            day_max_str = day_max.isoformat()
        elif day_max:
            day_max_str = str(day_max)[:10]
        else:
            day_max_str = None
    except Exception as e:
        day_max_str = None
        r("8.1 stale_detection", "FAIL", f"Cannot query day_fact: {e}")
        return

    try:
        cur.execute(
            f"SELECT MAX(period_key::date) AS mx FROM {SERVING_TABLE} "
            f"WHERE grain = 'daily' AND period_key::date <= CURRENT_DATE"
        )
        row = dict(cur.fetchone() or {})
        sv_max = row.get("mx")
        if sv_max and hasattr(sv_max, "isoformat"):
            sv_max_str = sv_max.isoformat()
        elif sv_max:
            sv_max_str = str(sv_max)[:10]
        else:
            sv_max_str = None
    except Exception as e:
        sv_max_str = None
        r("8.1 stale_detection", "FAIL", f"Cannot query serving: {e}")
        return

    if not day_max_str or not sv_max_str:
        r("8.1 stale_detection", "WARNING",
          f"day_fact max={day_max_str} serving max={sv_max_str}")
        return

    try:
        dd = date.fromisoformat(day_max_str)
        sd = date.fromisoformat(sv_max_str)
        diff = (dd - sd).days
        threshold = 2
        if abs(diff) > threshold:
            r("8.1 stale_detection", "FAIL",
              f"day_fact max={day_max_str} serving max={sv_max_str} diff={diff}d > {threshold}d threshold")
        else:
            r("8.1 stale_detection", "PASS",
              f"day_fact={day_max_str} serving={sv_max_str} diff={diff}d (threshold={threshold}d)")
    except Exception as e:
        r("8.1 stale_detection", "FAIL", f"Date parse error: {e}")


def _check_blocked_detection(integrity_result: Dict[str, Any]):
    try:
        status = integrity_result.get("status", "error")
        if status == "blocked":
            r("9.1 blocked_detection", "FAIL",
              f"Serving integrity is BLOCKED: {integrity_result.get('message', '')[:120]}")
        elif status == "error":
            r("9.1 blocked_detection", "FAIL",
              f"Integrity guard returned error: {integrity_result.get('message', '')[:120]}")
        else:
            r("9.1 blocked_detection", "PASS",
              f"Serving integrity status: {status}")
    except Exception as e:
        r("9.1 blocked_detection", "FAIL", f"Error: {e}")


def _check_dependency_graph_completeness():
    try:
        from app.config.source_of_truth_registry import SOURCE_OF_TRUTH, REGISTERED_VIEWS
        sot_count = len(SOURCE_OF_TRUTH)
        registered_count = len(REGISTERED_VIEWS)
        source_modes = set(e.get("source_mode", "unknown") for e in SOURCE_OF_TRUTH.values())
        canonical_count = sum(1 for e in SOURCE_OF_TRUTH.values() if e.get("source_mode") == "canonical")
        r("10.1 dependency_graph_completeness", "PASS",
          f"{sot_count} source-of-truth entries ({registered_count} registered views), "
          f"{canonical_count} canonical, modes={sorted(source_modes)}")
    except Exception as e:
        r("10.1 dependency_graph_completeness", "FAIL", f"Error: {e}")


def _to_json_safe(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (date,)):
        return v.isoformat()
    if isinstance(v, (int, float, str, bool)):
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return v
    if isinstance(v, dict):
        return {str(k): _to_json_safe(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_to_json_safe(x) for x in v]
    return str(v)


def main():
    global QUIET

    ap = argparse.ArgumentParser(description="Freshness Pipeline Resilience Audit")
    ap.add_argument("--json", action="store_true", help="Output results as JSON")
    ap.add_argument("--quiet", action="store_true", help="Suppress non-error output")
    args = ap.parse_args()
    QUIET = args.quiet

    if not args.json and not QUIET:
        print("=" * 65)
        print("  FRESHNESS PIPELINE RESILIENCE AUDIT")
        print(f"  {date.today().isoformat()}")
        print("=" * 65)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        months = _closed_months(2)
        weeks = _closed_iso_weeks(5)

        # 1. Coverage by grain
        if not QUIET:
            print("\n-- 1. Coverage by Grain --")
        _check_coverage_by_grain(cur, months)

        # 2. Latest date by grain
        if not QUIET:
            print("\n-- 2. Latest Date by Grain --")
        _check_latest_date_by_grain(cur)

        cur.close()

    # 3. Missing periods (uses its own connection)
    if not QUIET:
        print("\n-- 3. Missing Periods (Serving Integrity Guard) --")
    try:
        from app.services.omniview_serving_integrity_guard import validate_omniview_serving_integrity
        integrity_result = validate_omniview_serving_integrity()
    except Exception as e:
        integrity_result = {"status": "error", "message": str(e), "missing_periods": [], "checks": [], "remediation": None}
        r("3.0 integrity guard invocation", "FAIL", f"Call failed: {e}")
    _check_missing_periods(integrity_result)

    # 4. Serving vs Fact (needs connection)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if not QUIET:
            print("\n-- 4. Serving vs Fact (last 5 ISO weeks) --")
        _check_serving_vs_fact(cur, weeks)
        cur.close()

    # 5. Freshness endpoint consistency
    if not QUIET:
        print("\n-- 5. Freshness Endpoint Consistency --")
    try:
        from app.services.omniview_freshness_governance_service import get_omniview_freshness_governance
        freshness_result = get_omniview_freshness_governance()
    except Exception as e:
        freshness_result = {"status": "error", "message": str(e), "raw": {}, "facts": {}, "serving": {}, "cross_validation": {}, "remediation": None}
        r("5.0 freshness governance invocation", "FAIL", f"Call failed: {e}")
    _check_freshness_endpoint_consistency(freshness_result)

    # 6. Startup guard output
    if not QUIET:
        print("\n-- 6. Startup Guard Output --")
    _check_startup_guard_output(integrity_result)

    # 7. Remediation presence
    if not QUIET:
        print("\n-- 7. Remediation Presence --")
    _check_remediation_presence(integrity_result)

    # 8. Stale detection
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if not QUIET:
            print("\n-- 8. Stale Detection --")
        _check_stale_detection(cur)
        cur.close()

    # 9. Blocked detection
    if not QUIET:
        print("\n-- 9. Blocked Detection --")
    _check_blocked_detection(integrity_result)

    # 10. Dependency graph completeness
    if not QUIET:
        print("\n-- 10. Dependency Graph Completeness --")
    _check_dependency_graph_completeness()

    # Summary
    if not QUIET:
        print("\n" + "=" * 65)
        print("  AUDIT SUMMARY")
        print("=" * 65)
        for item in RESULTS:
            icon = {"PASS": "PASS", "FAIL": "FAIL", "WARNING": "WARN"}[item["status"]]
            print(f"  {icon:6s} {item['label']}")
            if item["detail"]:
                print(f"         {item['detail']}")

        print(f"\n  PASS: {PASS_COUNT}  WARNING: {WARN_COUNT}  FAIL: {FAIL_COUNT}")

        if FAIL_COUNT > 0:
            print(f"\n  VERDICT: FAIL — {FAIL_COUNT} blocking issue(s)")
            for b in [i for i in RESULTS if i["status"] == "FAIL"]:
                print(f"    - {b['label']}")
        elif WARN_COUNT > 0:
            print(f"\n  VERDICT: CONDITIONAL PASS — {WARN_COUNT} warning(s)")
        else:
            print(f"\n  VERDICT: PASS — All checks passed")

    if args.json:
        json_output = {
            "audit": "freshness_pipeline_resilience",
            "date": date.today().isoformat(),
            "summary": {"pass": PASS_COUNT, "warning": WARN_COUNT, "fail": FAIL_COUNT},
            "results": RESULTS,
        }
        print(json.dumps(_to_json_safe(json_output), indent=2, ensure_ascii=False))

    return 1 if FAIL_COUNT > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
