"""
Weekly Serving Guardrails Service — CF-H1J.7 Regression Prevention
Fact vs Serving reconciliation for weekly grain.

Checks:
  A) Serving exists, week_fact missing  → BREACH
  B) Week_fact exists, serving missing → WARNING
  C) Both exist, trips differ           → MISMATCH
  D) Revenue differs                     → MISMATCH
  E) Active drivers differ               → MISMATCH

Scope: last 8 closed ISO weeks.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from app.services.business_slice_service import FACT_WEEKLY

logger = logging.getLogger(__name__)

SEVERITY_BREACH = "breach"
SEVERITY_BLOCKED = "blocked"
SEVERITY_WARNING = "warning"
SEVERITY_OK = "ok"

SERVING_WEEKLY_TABLE = "serving.omniview_projection_daily_fact"

METRICS_TO_COMPARE = [
    ("trips_completed", "trips_completed", "trips"),
    ("revenue_yego_net", "revenue_yego_final", "revenue"),
    ("active_drivers", "active_drivers", "active_drivers"),
]

STATUS_ORDER = {SEVERITY_OK: 0, SEVERITY_WARNING: 1, SEVERITY_BREACH: 2, SEVERITY_BLOCKED: 3}


def _iso_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _closed_iso_weeks(count: int = 8) -> List[date]:
    today = date.today()
    current_monday = _iso_monday(today)
    weeks = []
    for i in range(1, count + 1):
        weeks.append(current_monday - timedelta(weeks=i))
    return weeks


def reconcile_weekly_fact_vs_serving(weeks_count: int = 8) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            closed_weeks = _closed_iso_weeks(weeks_count)

            for ws in closed_weeks:
                ws_str = ws.isoformat()

                cur.execute(
                    f"""
                    SELECT country, city, business_slice_name,
                           SUM(COALESCE(trips_completed, 0)) AS trips,
                           SUM(COALESCE(revenue_yego_net, 0)) AS revenue,
                           SUM(COALESCE(active_drivers, 0)) AS drivers
                    FROM {FACT_WEEKLY}
                    WHERE week_start = %s
                    GROUP BY country, city, business_slice_name
                    """,
                    (ws_str,),
                )
                fact_rows = {f"{r[0]}|{r[1]}|{r[2]}": {"trips": r[3] or 0, "revenue": r[4] or 0, "drivers": r[5] or 0} for r in cur.fetchall()}

                cur.execute(
                    f"""
                    SELECT country, city, business_slice_name,
                           SUM(COALESCE(trips_completed, 0)) AS trips,
                           SUM(COALESCE(revenue_yego_final, 0)) AS revenue,
                           SUM(COALESCE(active_drivers, 0)) AS drivers
                    FROM {SERVING_WEEKLY_TABLE}
                    WHERE grain = 'weekly' AND period_key = %s
                    GROUP BY country, city, business_slice_name
                    """,
                    (ws_str,),
                )
                serving_rows = {f"{r[0]}|{r[1]}|{r[2]}": {"trips": r[3] or 0, "revenue": r[4] or 0, "drivers": r[5] or 0} for r in cur.fetchall()}

                all_keys = set(fact_rows.keys()) | set(serving_rows.keys())

                for key in all_keys:
                    parts = key.split("|")
                    country = parts[0] if len(parts) > 0 else ""
                    city = parts[1] if len(parts) > 1 else ""
                    slice_name = parts[2] if len(parts) > 2 else ""

                    fact = fact_rows.get(key)
                    serving = serving_rows.get(key)

                    if serving and not fact:
                        findings.append({
                            "severity": SEVERITY_BREACH,
                            "affected_week": ws_str,
                            "affected_slice": key,
                            "country": country,
                            "city": city,
                            "business_slice_name": slice_name,
                            "issue": "SERVING_WITHOUT_FACT",
                            "fact_value": None,
                            "serving_value": serving,
                            "remediation": f"Week {ws_str} slice {key}: serving exists but week_fact missing. Re-run incremental weekly refresh.",
                        })
                        continue

                    if fact and not serving:
                        findings.append({
                            "severity": SEVERITY_WARNING,
                            "affected_week": ws_str,
                            "affected_slice": key,
                            "country": country,
                            "city": city,
                            "business_slice_name": slice_name,
                            "issue": "FACT_WITHOUT_SERVING",
                            "fact_value": fact,
                            "serving_value": None,
                            "remediation": f"Week {ws_str} slice {key}: week_fact exists but serving missing. Run projection refresh for weekly grain.",
                        })
                        continue

                    for metric_fact, metric_serving, metric_label in METRICS_TO_COMPARE:
                        fv = fact.get(metric_label, 0) if fact else 0
                        sv = serving.get(metric_label, 0) if serving else 0
                        fv_num = float(fv or 0)
                        sv_num = float(sv or 0)
                        diff = fv_num - sv_num

                        tolerance = 0
                        if metric_label == "revenue":
                            tolerance = max(0.01, abs(fv_num) * 0.005)
                        elif metric_label == "trips":
                            tolerance = 0

                        if abs(diff) > tolerance:
                            severity = SEVERITY_BLOCKED if metric_label == "trips" else SEVERITY_WARNING
                            findings.append({
                                "severity": severity,
                                "affected_week": ws_str,
                                "affected_slice": key,
                                "country": country,
                                "city": city,
                                "business_slice_name": slice_name,
                                "issue": "METRIC_MISMATCH",
                                "metric": metric_label,
                                "fact_value": fv_num,
                                "serving_value": sv_num,
                                "diff": diff,
                                "remediation": (
                                    f"Week {ws_str} slice {key}: {metric_label} mismatch "
                                    f"(fact={fv_num}, serving={sv_num}, diff={diff}). "
                                    "Re-run incremental weekly refresh + projection refresh."
                                ),
                            })

            cur.close()

    except Exception as e:
        logger.exception("weekly_serving_guardrails: fatal error during reconciliation")
        return {
            "status": "error",
            "error": str(e)[:500],
            "weeks_checked": weeks_count,
            "findings": [],
            "breach_count": 0,
            "warning_count": 0,
            "mismatch_count": 0,
        }

    breach_count = sum(1 for f in findings if f["severity"] == SEVERITY_BREACH)
    warning_count = sum(1 for f in findings if f["severity"] == SEVERITY_WARNING)
    mismatch_count = sum(1 for f in findings if f["severity"] == SEVERITY_BLOCKED)

    if breach_count > 0:
        overall = SEVERITY_BREACH
    elif mismatch_count > 0:
        overall = SEVERITY_BLOCKED
    elif warning_count > 0:
        overall = SEVERITY_WARNING
    else:
        overall = SEVERITY_OK

    return {
        "status": overall,
        "weeks_checked": weeks_count,
        "closed_weeks": [w.isoformat() for w in _closed_iso_weeks(weeks_count)],
        "findings": findings,
        "breach_count": breach_count,
        "warning_count": warning_count,
        "mismatch_count": mismatch_count,
        "total_findings": len(findings),
    }
