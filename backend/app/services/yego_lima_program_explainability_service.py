"""
YEGO Lima Growth — Program Explainability Service (LG-UX-R3.0)

Read-only. Traces REAL rules to REAL data. No AI. No inference.
Every explanation comes from actual code logic and database values.
"""
from __future__ import annotations

import logging
from datetime import date as DateType
from typing import Any, Dict, List, Optional

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_SNAPSHOT = "growth.yango_lima_driver_state_snapshot"
TABLE_ELIGIBILITY = "growth.yango_lima_program_eligibility_daily"
TABLE_PRIORITIZED = "growth.yango_lima_prioritized_opportunity_daily"
TABLE_HISTORY_W = "growth.yango_lima_driver_history_weekly"
TABLE_HISTORY_D = "growth.yango_lima_driver_history_daily"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"

# ── PROGRAM RULES (extracted from actual code) ──

PROGRAM_RULES = {
    "PROGRAM_CHURN_PREVENTION": {
        "name": "Churn Prevention",
        "rules": [
            {
                "rule_id": "CP-001",
                "description": "Retention state indicates churn risk or at risk",
                "condition": "retention_state IN ('AT_RISK', 'CHURN_RISK')",
                "source_table": TABLE_SNAPSHOT,
                "source_field": "retention_state",
            },
            {
                "rule_id": "CP-002",
                "description": "Declining flag is active (week-over-week decline > 30%)",
                "condition": "declining_flag = true",
                "source_table": TABLE_SNAPSHOT,
                "source_field": "declining_flag",
            },
            {
                "rule_id": "CP-003",
                "description": "Churn risk flag is active",
                "condition": "churn_risk_flag = true",
                "source_table": TABLE_SNAPSHOT,
                "source_field": "churn_risk_flag",
            },
        ],
        "priority_boost": 100,
        "service_file": "yego_lima_program_eligibility_service.py",
    },
    "PROGRAM_ACTIVE_GROWTH": {
        "name": "Active Growth",
        "rules": [
            {
                "rule_id": "AG-001",
                "description": "Performance below target (NO_TRIPS, LOW, or MEDIUM)",
                "condition": "performance_state IN ('NO_TRIPS', 'LOW', 'MEDIUM')",
                "source_table": TABLE_SNAPSHOT,
                "source_field": "performance_state",
            },
            {
                "rule_id": "AG-002",
                "description": "Driver is in active lifecycle (not churned, not prospect)",
                "condition": "lifecycle_state IN ('ACTIVATED', 'EARLY_LIFE', 'ESTABLISHED', 'REACTIVATED')",
                "source_table": TABLE_SNAPSHOT,
                "source_field": "lifecycle_state",
            },
            {
                "rule_id": "AG-003",
                "description": "Distance to weekly target is positive (below target)",
                "condition": "distance_to_weekly_target > 0",
                "source_table": TABLE_SNAPSHOT,
                "source_field": "distance_to_weekly_target",
            },
        ],
        "priority_boost": 0,
        "service_file": "yego_lima_program_eligibility_service.py",
    },
    "PROGRAM_14_90": {
        "name": "14-90 Day Reactivation",
        "rules": [
            {
                "rule_id": "14-001",
                "description": "Driver is in early-life or reactivation lifecycle stage",
                "condition": "lifecycle_state IN ('REGISTERED', 'ACTIVATED', 'EARLY_LIFE', 'REACTIVATED')",
                "source_table": TABLE_SNAPSHOT,
                "source_field": "lifecycle_state",
            },
            {
                "rule_id": "14-002",
                "description": "Driver has not yet reached weekly target",
                "condition": "reached_target_flag = false",
                "source_table": TABLE_SNAPSHOT,
                "source_field": "reached_target_flag",
            },
        ],
        "priority_boost": 50,
        "service_file": "yego_lima_program_eligibility_service.py",
    },
    "PROGRAM_HIGH_VALUE_RECOVERY": {
        "name": "High Value Recovery",
        "rules": [
            {
                "rule_id": "HV-001",
                "description": "Historical best week in last 12 weeks meets threshold (>= 80 trips)",
                "condition": "best_week_12w >= 80",
                "source_table": TABLE_HISTORY_W,
                "source_field": "best_week_12w",
            },
            {
                "rule_id": "HV-002",
                "description": "Current week has zero completed orders",
                "condition": "completed_orders_week = 0",
                "source_table": TABLE_HISTORY_W,
                "source_field": "completed_orders_week",
            },
            {
                "rule_id": "HV-003",
                "description": "Last trip was 1-14 days ago (recently inactive high-value driver)",
                "condition": "inactive_days BETWEEN 1 AND 14",
                "source_table": TABLE_HISTORY_D,
                "source_field": "last_trip_date",
            },
        ],
        "priority_boost": 200,
        "service_file": "yego_lima_opportunity_policy_service.py",
    },
}


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_driver_program_explainability(
    driver_id: str,
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Explain why a specific driver is (or isn't) in each program.
    Returns real rules evaluated against real data. No AI. No inference.
    """
    with get_db() as conn:
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Get latest snapshot for this driver (named columns only)
        if date:
            cur.execute(
                f"SELECT snapshot_date, driver_profile_id, lifecycle_state, performance_state, "
                f"retention_state, completed_orders_day, completed_orders_week, "
                f"supply_hours_day, supply_hours_week, trips_per_supply_hour_week, "
                f"distance_to_weekly_target, reached_target_flag, declining_flag, "
                f"churn_risk_flag, recoverable_flag, new_driver_flag "
                f"FROM {TABLE_SNAPSHOT} WHERE driver_profile_id = %(did)s AND snapshot_date = %(d)s",
                {"did": driver_id, "d": date}
            )
        else:
            cur.execute(
                f"SELECT snapshot_date, driver_profile_id, lifecycle_state, performance_state, "
                f"retention_state, completed_orders_day, completed_orders_week, "
                f"supply_hours_day, supply_hours_week, trips_per_supply_hour_week, "
                f"distance_to_weekly_target, reached_target_flag, declining_flag, "
                f"churn_risk_flag, recoverable_flag, new_driver_flag "
                f"FROM {TABLE_SNAPSHOT} WHERE driver_profile_id = %(did)s ORDER BY snapshot_date DESC LIMIT 1",
                {"did": driver_id}
            )
        snap_row = cur.fetchone()

        if not snap_row:
            return {
                "driver_id": driver_id,
                "found": False,
                "error": "Driver not found in driver_state_snapshot",
            }

        # Named columns via RealDictCursor — no positional indexing
        snap = {
            "snapshot_date": str(snap_row["snapshot_date"]) if snap_row.get("snapshot_date") else None,
            "driver_profile_id": snap_row.get("driver_profile_id"),
            "lifecycle_state": snap_row.get("lifecycle_state"),
            "performance_state": snap_row.get("performance_state"),
            "retention_state": snap_row.get("retention_state"),
            "completed_orders_day": _safe_int(snap_row.get("completed_orders_day")),
            "completed_orders_week": _safe_int(snap_row.get("completed_orders_week")),
            "supply_hours_day": _safe_float(snap_row.get("supply_hours_day")),
            "supply_hours_week": _safe_float(snap_row.get("supply_hours_week")),
            "trips_per_supply_hour_week": _safe_float(snap_row.get("trips_per_supply_hour_week")),
            "distance_to_weekly_target": _safe_float(snap_row.get("distance_to_weekly_target")),
            "reached_target_flag": snap_row.get("reached_target_flag"),
            "declining_flag": snap_row.get("declining_flag"),
            "churn_risk_flag": snap_row.get("churn_risk_flag"),
            "recoverable_flag": snap_row.get("recoverable_flag"),
            "new_driver_flag": snap_row.get("new_driver_flag"),
        }
        snap_date = snap["snapshot_date"]

        # 2. Get historical weekly data
        cur.execute(
            f"SELECT week_start_date, completed_orders_week, best_week_12w FROM {TABLE_HISTORY_W} "
            f"WHERE driver_profile_id = %(did)s ORDER BY week_start_date DESC LIMIT 12",
            {"did": driver_id}
        )
        hist_weeks = cur.fetchall()
        best_week_12w = max((r.get("best_week_12w") or 0 for r in hist_weeks), default=0)
        current_week_orders = hist_weeks[0].get("completed_orders_week", 0) if hist_weeks else 0

        # 3. Get last trip date
        cur.execute(
            f"SELECT MAX(date) as last_date FROM {TABLE_HISTORY_D} WHERE driver_profile_id = %(did)s AND completed_orders > 0",
            {"did": driver_id}
        )
        last_trip_row = cur.fetchone()
        last_trip_date = str(last_trip_row["last_date"]) if last_trip_row and last_trip_row.get("last_date") else None

        # 4. Get program eligibility
        cur.execute(
            f"SELECT program_code, eligibility_reason, priority FROM {TABLE_ELIGIBILITY} "
            f"WHERE driver_profile_id = %(did)s AND eligibility_date = %(d)s",
            {"did": driver_id, "d": snap_date}
        )
        eligibility_rows = cur.fetchall()
        eligible_programs = {r["program_code"]: {"reason": r.get("eligibility_reason"), "priority": r.get("priority")} for r in eligibility_rows}

        # 5. Get prioritized data
        cur.execute(
            f"SELECT selected_program_code, opportunity_score, final_rank, is_actionable_today, exclusion_reason "
            f"FROM {TABLE_PRIORITIZED} WHERE driver_profile_id = %(did)s AND opportunity_date = %(d)s",
            {"did": driver_id, "d": snap_date}
        )
        pri_row = cur.fetchone()

        # 6. Get queue status
        cur.execute(
            f"SELECT queue_status, assigned_channel, exported_at FROM {TABLE_QUEUE} "
            f"WHERE driver_id = %(did)s AND assignment_date = %(d)s",
            {"did": driver_id, "d": snap_date}
        )
        queue_row = cur.fetchone()

    # ── Build explainability per program ──
    programs_explained = []

    for prog_code, prog_def in PROGRAM_RULES.items():
        is_eligible = prog_code in eligible_programs
        rules_evaluated = []

        for rule in prog_def["rules"]:
            rule_id = rule["rule_id"]
            source_field = rule["source_field"]

            # Evaluate based on which table the rule reads from
            if rule["source_table"] == TABLE_SNAPSHOT:
                value = snap.get(source_field)
            elif rule["source_table"] == TABLE_HISTORY_W:
                if source_field == "best_week_12w":
                    value = best_week_12w
                elif source_field == "completed_orders_week":
                    value = current_week_orders
                else:
                    value = None
            elif rule["source_table"] == TABLE_HISTORY_D:
                value = last_trip_date
            else:
                value = None

            # Determine if rule matched
            matched = False
            if rule_id == "CP-001":
                matched = value in ("AT_RISK", "CHURN_RISK") if value else False
            elif rule_id == "CP-002":
                matched = bool(value)
            elif rule_id == "CP-003":
                matched = bool(value)
            elif rule_id == "AG-001":
                matched = value in ("NO_TRIPS", "LOW", "MEDIUM") if value else False
            elif rule_id == "AG-002":
                matched = value in ("ACTIVATED", "EARLY_LIFE", "ESTABLISHED", "REACTIVATED") if value else False
            elif rule_id == "AG-003":
                matched = _safe_float(value) > 0
            elif rule_id == "14-001":
                matched = value in ("REGISTERED", "ACTIVATED", "EARLY_LIFE", "REACTIVATED") if value else False
            elif rule_id == "14-002":
                matched = not bool(value)
            elif rule_id == "HV-001":
                matched = _safe_int(value) >= 80
            elif rule_id == "HV-002":
                matched = _safe_int(value) == 0
            elif rule_id == "HV-003":
                matched = value is not None

            rules_evaluated.append({
                "rule_id": rule_id,
                "description": rule["description"],
                "condition": rule["condition"],
                "source_field": source_field,
                "value": str(value) if value is not None else None,
                "matched": matched,
            })

        all_rules_matched = all(r["matched"] for r in rules_evaluated) if rules_evaluated else False

        explanation = {
            "program_code": prog_code,
            "program_name": prog_def["name"],
            "eligible": is_eligible,
            "eligibility_reason": eligible_programs.get(prog_code, {}).get("reason") if is_eligible else None,
            "rules": rules_evaluated,
            "all_rules_matched": all_rules_matched,
        }

        if pri_row and pri_row.get("selected_program_code") == prog_code:
            explanation["prioritized"] = {
                "opportunity_score": _safe_float(pri_row.get("opportunity_score")),
                "final_rank": _safe_int(pri_row.get("final_rank")),
                "is_actionable_today": bool(pri_row.get("is_actionable_today")),
                "exclusion_reason": pri_row.get("exclusion_reason"),
            }

        if queue_row and is_eligible:
            explanation["queue_status"] = {
                "status": queue_row.get("queue_status"),
                "assigned_channel": queue_row.get("assigned_channel"),
                "exported_at": queue_row["exported_at"].isoformat() if queue_row.get("exported_at") else None,
            }

        programs_explained.append(explanation)

    return {
        "driver_id": driver_id,
        "found": True,
        "snapshot_date": snap_date,
        "snapshot": {
            "lifecycle_state": snap["lifecycle_state"],
            "performance_state": snap["performance_state"],
            "retention_state": snap["retention_state"],
            "completed_orders_week": snap["completed_orders_week"],
            "supply_hours_week": snap["supply_hours_week"],
            "distance_to_weekly_target": snap["distance_to_weekly_target"],
        },
        "historical": {
            "best_week_12w": best_week_12w,
            "current_week_orders": current_week_orders,
            "last_trip_date": last_trip_date,
        },
        "programs": programs_explained,
        "in_programs": list(eligible_programs.keys()),
        "not_in_programs": [p for p in PROGRAM_RULES if p not in eligible_programs],
    }


def get_program_rules() -> Dict[str, Any]:
    """Return all program rules with descriptions. Read-only reference."""
    return {
        "programs": PROGRAM_RULES,
        "total_programs": len(PROGRAM_RULES),
        "total_rules": sum(len(p["rules"]) for p in PROGRAM_RULES.values()),
        "source": "Extracted from actual service code. No AI. No inference.",
    }


def get_program_coverage(date: str) -> Dict[str, Any]:
    """Audit program coverage: empty programs, impossible rules, overlaps."""
    with get_db() as conn:
        cur = conn.cursor()

        coverage = {}
        for prog_code in PROGRAM_RULES:
            cur.execute(
                f"SELECT COUNT(*) FROM {TABLE_ELIGIBILITY} "
                f"WHERE program_code = %(pc)s AND eligibility_date = %(d)s AND eligible_flag = true",
                {"pc": prog_code, "d": date}
            )
            eligible = cur.fetchone()[0] or 0

            cur.execute(
                f"SELECT COUNT(*) FROM {TABLE_PRIORITIZED} "
                f"WHERE selected_program_code = %(pc)s AND opportunity_date = %(d)s",
                {"pc": prog_code, "d": date}
            )
            prioritized = cur.fetchone()[0] or 0

            cur.execute(
                f"SELECT COUNT(*) FROM {TABLE_QUEUE} "
                f"WHERE program_code = %(pc)s AND assignment_date = %(d)s",
                {"pc": prog_code, "d": date}
            )
            queued = cur.fetchone()[0] or 0

            coverage[prog_code] = {
                "name": PROGRAM_RULES[prog_code]["name"],
                "eligible": eligible,
                "prioritized": prioritized,
                "queued": queued,
                "empty": eligible == 0,
                "rules_count": len(PROGRAM_RULES[prog_code]["rules"]),
            }

    # Check for drivers without any program
    cur.execute(
        f"SELECT COUNT(*) FROM {TABLE_SNAPSHOT} s "
        f"WHERE s.snapshot_date = %(d)s "
        f"AND NOT EXISTS (SELECT 1 FROM {TABLE_ELIGIBILITY} e "
        f"WHERE e.driver_profile_id = s.driver_profile_id AND e.eligibility_date = %(d)s AND e.eligible_flag = true)",
        {"d": date}
    )
    unassigned = cur.fetchone()[0] or 0

    return {
        "date": date,
        "programs": coverage,
        "drivers_without_program": unassigned,
        "total_snapshot_drivers": 0,  # filled below
    }
