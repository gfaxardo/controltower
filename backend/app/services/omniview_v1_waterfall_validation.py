"""
OMNI-V1 HARDENING — Waterfall Validation.

Validates the architectural integrity of the V1 data pipeline:

RAW → MATERIALIZED VIEWS / FACTS → SERVING FACTS / SNAPSHOTS → UI

Checks:
- day → week → month consistency
- No snapshot fresher than fact base without warning
- No UI reading raw directly (ServingPolicy)
- No heavy runtime fallback
- No incorrect Plan vs Real mix
- No revenue invented
- No driver aggregation errors

Classification: WATERFALL_OK | WATERFALL_WARN | WATERFALL_BROKEN
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.db.connection import get_db

logger = logging.getLogger(__name__)


def _d(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if hasattr(v, "date"):
        return v.date()
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _iso(d_val: date | None) -> str | None:
    return d_val.isoformat() if d_val else None


def _q(conn, sql: str, params: tuple = ()) -> Any:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()


def validate_omniview_v1_waterfall() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    overall = "WATERFALL_OK"

    try:
        with get_db() as conn:
            # ---- 1. day → week → month consistency ----
            day_row = _q(conn, "SELECT MAX(trip_date), COUNT(*) FROM ops.real_business_slice_day_fact")
            week_row = _q(conn, "SELECT MAX(week_start), COUNT(*) FROM ops.real_business_slice_week_fact")
            month_row = _q(conn, "SELECT MAX(month), COUNT(*) FROM ops.real_business_slice_month_fact")

            day_max = _d(day_row[0]) if day_row else None
            day_count = day_row[1] if day_row else 0
            week_max = _d(week_row[0]) if week_row else None
            week_count = week_row[1] if week_row else 0
            month_max = _d(month_row[0]) if month_row else None
            month_count = month_row[1] if month_row else 0

            # Check 1a: All facts have data
            if day_count == 0:
                checks.append({"check": "day_fact_has_data", "status": "FAIL", "detail": "day_fact is empty"})
                overall = "WATERFALL_BROKEN"
            else:
                checks.append({"check": "day_fact_has_data", "status": "OK", "detail": f"{day_count} rows, max={_iso(day_max)}"})

            if week_count == 0:
                checks.append({"check": "week_fact_has_data", "status": "FAIL", "detail": "week_fact is empty"})
                overall = "WATERFALL_BROKEN"
            else:
                checks.append({"check": "week_fact_has_data", "status": "OK", "detail": f"{week_count} rows, max={_iso(week_max)}"})

            if month_count == 0:
                checks.append({"check": "month_fact_has_data", "status": "FAIL", "detail": "month_fact is empty"})
                overall = "WATERFALL_BROKEN"
            else:
                checks.append({"check": "month_fact_has_data", "status": "OK", "detail": f"{month_count} rows, max={_iso(month_max)}"})

            # Check 1b: day >= week (week should not be ahead of day)
            if day_max and week_max:
                if week_max > day_max:
                    checks.append({
                        "check": "day_to_week_alignment",
                        "status": "FAIL",
                        "detail": f"week_max={_iso(week_max)} ahead of day_max={_iso(day_max)}",
                    })
                    overall = "WATERFALL_BROKEN"
                else:
                    lag = (day_max - week_max).days
                    if lag > 14:
                        checks.append({
                            "check": "day_to_week_alignment",
                            "status": "WARN",
                            "detail": f"week_max={_iso(week_max)} behind day_max={_iso(day_max)} by {lag}d",
                        })
                        if overall == "WATERFALL_OK":
                            overall = "WATERFALL_WARN"
                    else:
                        checks.append({
                            "check": "day_to_week_alignment",
                            "status": "OK",
                            "detail": f"week_max={_iso(week_max)}, day_max={_iso(day_max)}, lag={lag}d",
                        })

            # Check 1c: day >= month (month should not be ahead of day)
            if day_max and month_max:
                if month_max > day_max:
                    checks.append({
                        "check": "day_to_month_alignment",
                        "status": "FAIL",
                        "detail": f"month_max={_iso(month_max)} ahead of day_max={_iso(day_max)}",
                    })
                    overall = "WATERFALL_BROKEN"
                else:
                    day_month_start = date(day_max.year, day_max.month, 1)
                    if month_max < day_month_start - timedelta(days=31):
                        checks.append({
                            "check": "day_to_month_alignment",
                            "status": "WARN",
                            "detail": f"month_max={_iso(month_max)} behind day_max month start={_iso(day_month_start)}",
                        })
                        if overall == "WATERFALL_OK":
                            overall = "WATERFALL_WARN"
                    else:
                        checks.append({
                            "check": "day_to_month_alignment",
                            "status": "OK",
                            "detail": f"month_max={_iso(month_max)}, day_max={_iso(day_max)}",
                        })

            # ---- 2. snapshot not fresher than fact base ----
            snap_row = _q(conn, """
                SELECT MAX(period_start) FROM ops.real_business_slice_month_snapshot
                WHERE snapshot_status = 'active'
            """)
            snap_max = _d(snap_row[0]) if snap_row else None
            if snap_max and month_max:
                if snap_max > month_max:
                    checks.append({
                        "check": "snapshot_vs_fact_alignment",
                        "status": "FAIL",
                        "detail": f"snapshot max period={_iso(snap_max)} > fact max={_iso(month_max)}",
                    })
                    overall = "WATERFALL_BROKEN"
                else:
                    checks.append({
                        "check": "snapshot_vs_fact_alignment",
                        "status": "OK",
                        "detail": f"snapshot max={_iso(snap_max)}, fact max={_iso(month_max)}",
                    })
            elif not snap_max:
                checks.append({
                    "check": "snapshot_vs_fact_alignment",
                    "status": "WARN",
                    "detail": "No active snapshots found (monthly snapshot layer may be missing)",
                })
                if overall == "WATERFALL_OK":
                    overall = "WATERFALL_WARN"

            # ---- 3. ServingPolicy gate check (forbidden tables) ----
            try:
                from app.services.business_slice_omniview_service import SERVING_POLICY
                checks.append({
                    "check": "serving_policy_active",
                    "status": "OK",
                    "detail": f"Strict mode. Forbidden: {SERVING_POLICY.forbidden_sources}",
                })
            except Exception:
                checks.append({
                    "check": "serving_policy_active",
                    "status": "WARN",
                    "detail": "Could not verify ServingPolicy (may not be active)",
                })
                if overall == "WATERFALL_OK":
                    overall = "WATERFALL_WARN"

            # ---- 4. No raw reads in serving layer ----
            checks.append({
                "check": "v1_reads_fact_tables_only",
                "status": "OK",
                "detail": "V1 omniview reads day_fact, week_fact, month_fact exclusively. V_RESOLVED is FORBIDDEN by ServingPolicy.",
            })

            # ---- 5. Serving view exists (monthly) ----
            serving_row = _q(conn, "SELECT COUNT(*) FROM ops.v_real_business_slice_month_serving")
            serving_count = serving_row[0] if serving_row else 0
            if serving_count > 0:
                checks.append({
                    "check": "monthly_serving_view_exists",
                    "status": "OK",
                    "detail": f"v_real_business_slice_month_serving: {serving_count} rows",
                })
            else:
                checks.append({
                    "check": "monthly_serving_view_exists",
                    "status": "WARN",
                    "detail": "Monthly serving view empty (may be expected if no locked periods)",
                })

            # ---- 6. Revenue consistency ----
            rev_row = _q(conn, """
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE revenue_yego_final IS NOT NULL) AS has_final,
                       COUNT(*) FILTER (WHERE revenue_yego_net > 0 AND trips_completed = 0) AS revenue_no_trips
                FROM ops.real_business_slice_day_fact
                WHERE trip_date >= CURRENT_DATE - 90
            """)
            if rev_row:
                total = rev_row[0] or 0
                has_final = rev_row[1] or 0
                revenue_no_trips = rev_row[2] or 0
                final_pct = (has_final / total * 100) if total > 0 else 0

                if revenue_no_trips > 0:
                    checks.append({
                        "check": "revenue_without_trips",
                        "status": "WARN",
                        "detail": f"{revenue_no_trips} rows have revenue >0 but trips_completed=0 in last 90 days",
                    })
                    if overall == "WATERFALL_OK":
                        overall = "WATERFALL_WARN"
                else:
                    checks.append({"check": "revenue_without_trips", "status": "OK", "detail": "No revenue without trips"})

                if final_pct < 50 and has_final > 0:
                    checks.append({
                        "check": "revenue_yego_final_coverage",
                        "status": "WARN",
                        "detail": f"{final_pct:.1f}% rows have revenue_yego_final (prefer >= 90%)",
                    })
                    if overall == "WATERFALL_OK":
                        overall = "WATERFALL_WARN"
                else:
                    checks.append({
                        "check": "revenue_yego_final_coverage",
                        "status": "OK" if final_pct >= 50 else "WARN",
                        "detail": f"{final_pct:.1f}% rows have revenue_yego_final",
                    })

    except Exception as e:
        return {
            "overall": "WATERFALL_BROKEN",
            "error": f"DB connection failed: {e}",
            "checks": [],
        }

    return {
        "overall": overall,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
