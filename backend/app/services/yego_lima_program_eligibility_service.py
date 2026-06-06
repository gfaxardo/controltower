"""
YEGO Lima Growth — Program Eligibility Service (Fase 2D-R).

Evaluates driver eligibility for operational programs from driver_state_snapshot.
Generates growth.yango_lima_program_eligibility_daily.

Programs:
- PROGRAM_14_90: Early-life activation & acceleration
- PROGRAM_ACTIVE_GROWTH: Growth for underperforming drivers
- PROGRAM_CHURN_PREVENTION: Retention for at-risk drivers
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.settings import settings
from app.services.freshness_service import compute_freshness
from app.services.lima_growth_explainability_service import explain_kpi

logger = logging.getLogger(__name__)

TABLE_STATE = "growth.yango_lima_driver_state_snapshot"
TABLE_OUT = "growth.yango_lima_program_eligibility_daily"

PROGRAM_14_90 = "PROGRAM_14_90"
PROGRAM_ACTIVE_GROWTH = "PROGRAM_ACTIVE_GROWTH"
PROGRAM_CHURN_PREVENTION = "PROGRAM_CHURN_PREVENTION"

PROGRAM_14_90_LIFECYCLES = ("REGISTERED", "ACTIVATED", "EARLY_LIFE", "REACTIVATED")
PROGRAM_ACTIVE_GROWTH_PERFORMANCE = ("NO_TRIPS", "LOW", "MEDIUM")
PROGRAM_ACTIVE_GROWTH_LIFECYCLES = ("ACTIVATED", "EARLY_LIFE", "ESTABLISHED", "REACTIVATED")
PROGRAM_CHURN_PREVENTION_RETENTION = ("AT_RISK", "CHURN_RISK")


def build_program_eligibility(eligibility_date_str: str) -> Dict[str, Any]:
    eligibility_date = date.fromisoformat(eligibility_date_str)

    logger.info("Building program eligibility: date=%s", eligibility_date)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_STATE}")
        latest = cur.fetchone()
        if not latest or not latest["max"]:
            return {"ok": False, "error": "No driver state snapshot available"}
        snap_date = latest["max"]

        # Clear existing for this date
        cur.execute(f"DELETE FROM {TABLE_OUT} WHERE eligibility_date = %(d)s", {"d": eligibility_date})

        counts = {}
        total = 0

        # ── PROGRAM_14_90 ──
        cur.execute(f"""
            INSERT INTO {TABLE_OUT} (
                eligibility_date, driver_profile_id, program_code,
                eligible_flag, eligibility_reason, priority,
                lifecycle_state, performance_state, retention_state,
                distance_to_weekly_target
            )
            SELECT %(d)s, driver_profile_id, %(prog)s,
                   true,
                   CASE
                       WHEN lifecycle_state = 'EARLY_LIFE' THEN 'new_driver_in_window'
                       WHEN lifecycle_state = 'REACTIVATED' THEN 'recently_reactivated'
                       ELSE lifecycle_state
                   END,
                   CASE
                       WHEN lifecycle_state = 'EARLY_LIFE' THEN 1
                       WHEN lifecycle_state = 'REACTIVATED' THEN 2
                       WHEN lifecycle_state = 'ACTIVATED' THEN 3
                       ELSE 4
                   END,
                   lifecycle_state, performance_state, retention_state,
                   distance_to_weekly_target
            FROM {TABLE_STATE}
            WHERE snapshot_date = %(sd)s
              AND lifecycle_state = ANY(%(lc)s)
              AND reached_target_flag = false
            ON CONFLICT (eligibility_date, driver_profile_id, program_code) DO NOTHING
        """, {
            "d": eligibility_date, "prog": PROGRAM_14_90,
            "sd": snap_date, "lc": list(PROGRAM_14_90_LIFECYCLES),
        })
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_OUT} WHERE eligibility_date = %(d)s AND program_code = %(prog)s",
                     {"d": eligibility_date, "prog": PROGRAM_14_90})
        counts[PROGRAM_14_90] = cur.fetchone()["count"]
        total += counts[PROGRAM_14_90]

        # ── PROGRAM_ACTIVE_GROWTH ──
        cur.execute(f"""
            INSERT INTO {TABLE_OUT} (
                eligibility_date, driver_profile_id, program_code,
                eligible_flag, eligibility_reason, priority,
                lifecycle_state, performance_state, retention_state,
                distance_to_weekly_target
            )
            SELECT %(d)s, driver_profile_id, %(prog)s,
                   true,
                   CASE
                       WHEN recoverable_flag THEN 'recoverable_historical_performer'
                       WHEN performance_state = 'NO_TRIPS' THEN 'no_trips_this_week'
                       WHEN performance_state = 'LOW' THEN 'low_performance'
                       WHEN performance_state = 'MEDIUM' THEN 'medium_performance'
                       ELSE 'under_target'
                   END,
                   CASE
                       WHEN recoverable_flag THEN 10
                       WHEN performance_state = 'NO_TRIPS' THEN 20
                       WHEN performance_state = 'LOW' THEN 30
                       WHEN performance_state = 'MEDIUM' THEN 40
                       ELSE 50
                   END,
                   lifecycle_state, performance_state, retention_state,
                   distance_to_weekly_target
            FROM {TABLE_STATE}
            WHERE snapshot_date = %(sd)s
              AND performance_state = ANY(%(ps)s)
              AND lifecycle_state = ANY(%(lc)s)
              AND distance_to_weekly_target > 0
            ON CONFLICT (eligibility_date, driver_profile_id, program_code) DO NOTHING
        """, {
            "d": eligibility_date, "prog": PROGRAM_ACTIVE_GROWTH,
            "sd": snap_date,
            "ps": list(PROGRAM_ACTIVE_GROWTH_PERFORMANCE),
            "lc": list(PROGRAM_ACTIVE_GROWTH_LIFECYCLES),
        })
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_OUT} WHERE eligibility_date = %(d)s AND program_code = %(prog)s",
                     {"d": eligibility_date, "prog": PROGRAM_ACTIVE_GROWTH})
        counts[PROGRAM_ACTIVE_GROWTH] = cur.fetchone()["count"]
        total += counts[PROGRAM_ACTIVE_GROWTH]

        # ── PROGRAM_CHURN_PREVENTION ──
        cur.execute(f"""
            INSERT INTO {TABLE_OUT} (
                eligibility_date, driver_profile_id, program_code,
                eligible_flag, eligibility_reason, priority,
                lifecycle_state, performance_state, retention_state,
                distance_to_weekly_target
            )
            SELECT %(d)s, driver_profile_id, %(prog)s,
                   true,
                   CASE
                       WHEN churn_risk_flag AND declining_flag THEN 'churn_risk_declining'
                       WHEN churn_risk_flag THEN 'churn_risk_flag_active'
                       WHEN declining_flag THEN 'declining_flag_active'
                       ELSE retention_state
                   END,
                   CASE
                       WHEN retention_state = 'CHURN_RISK' THEN 100
                       WHEN churn_risk_flag THEN 110
                       WHEN declining_flag THEN 120
                       ELSE 130
                   END,
                   lifecycle_state, performance_state, retention_state,
                   distance_to_weekly_target
            FROM {TABLE_STATE}
            WHERE snapshot_date = %(sd)s
              AND (
                  retention_state = ANY(%(rs)s)
                  OR declining_flag = true
                  OR churn_risk_flag = true
              )
            ON CONFLICT (eligibility_date, driver_profile_id, program_code) DO NOTHING
        """, {
            "d": eligibility_date, "prog": PROGRAM_CHURN_PREVENTION,
            "sd": snap_date, "rs": list(PROGRAM_CHURN_PREVENTION_RETENTION),
        })
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_OUT} WHERE eligibility_date = %(d)s AND program_code = %(prog)s",
                     {"d": eligibility_date, "prog": PROGRAM_CHURN_PREVENTION})
        counts[PROGRAM_CHURN_PREVENTION] = cur.fetchone()["count"]
        total += counts[PROGRAM_CHURN_PREVENTION]

        conn.commit()

    return {
        "ok": True,
        "eligibility_date": eligibility_date_str,
        "source_snapshot_date": str(snap_date),
        "total_eligible": total,
        "by_program": counts,
    }


def get_program_summary(eligibility_date_str: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if not eligibility_date_str:
            cur.execute(f"SELECT MAX(eligibility_date) FROM {TABLE_OUT}")
            r = cur.fetchone()
            if not r or not r["max"]:
                return {"error": "No program eligibility data"}
            eligibility_date_str = str(r["max"])

        cur.execute(f"""
            SELECT e.program_code, COUNT(*) AS total,
                   SUM(CASE WHEN s.lifecycle_state = 'EARLY_LIFE' THEN 1 ELSE 0 END) AS early_life,
                   SUM(CASE WHEN s.recoverable_flag THEN 1 ELSE 0 END) AS recoverable,
                   SUM(CASE WHEN s.churn_risk_flag THEN 1 ELSE 0 END) AS churn_risk
            FROM {TABLE_OUT} e
            LEFT JOIN {TABLE_STATE} s
                ON e.driver_profile_id = s.driver_profile_id
                AND s.snapshot_date = (
                    SELECT MAX(snapshot_date) FROM {TABLE_STATE}
                    WHERE driver_profile_id = e.driver_profile_id
                )
            WHERE e.eligibility_date = %(d)s
            GROUP BY e.program_code ORDER BY total DESC
        """, {"d": eligibility_date_str})
        programs = [dict(r) for r in cur.fetchall()]

        # Enrich with prioritized + actionable counts
        cur.execute(
            "SELECT selected_program_code, COUNT(*) as prioritized, "
            "SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END) as actionable "
            "FROM growth.yango_lima_prioritized_opportunity_daily "
            "WHERE opportunity_date = %(d)s GROUP BY selected_program_code",
            {"d": eligibility_date_str},
        )
        prioritized_map = {
            r["selected_program_code"]: {"prioritized_total": r["prioritized"], "actionable_today": r["actionable"]}
            for r in cur.fetchall()
        }

        cur.execute(
            "SELECT program_code, COUNT(*) as queued "
            "FROM growth.yego_lima_assignment_queue "
            "WHERE assignment_date = %(d)s GROUP BY program_code",
            {"d": eligibility_date_str},
        )
        queued_map = {r["program_code"]: r["queued"] for r in cur.fetchall()}

        cur.execute(
            "SELECT program_code, SUM(contacts_inserted) as exported "
            "FROM growth.yango_lima_loopcontrol_campaign_export "
            "WHERE export_status = 'exported' GROUP BY program_code"
        )
        exported_map = {r["program_code"] or "": r["exported"] for r in cur.fetchall()}

        freshness = compute_freshness("program_eligibility", eligibility_date_str, "growth.yango_lima_program_eligibility_daily")

        enriched = []
        for p in programs:
            code = p["program_code"]
            prio = prioritized_map.get(code, {})
            eligible = p["total"]
            prioritized = prio.get("prioritized_total", 0)
            actionable = prio.get("actionable_today", 0)
            queued = queued_map.get(code, 0)
            exported = exported_map.get(code, 0)

            # Operational status
            if freshness["status"] == "STALE":
                op_status = "STALE"
            elif freshness["status"] == "UNKNOWN":
                op_status = "UNKNOWN"
            elif eligible == 0:
                op_status = "EMPTY"
            elif actionable > 0:
                op_status = "READY"
            elif eligible > 0:
                op_status = "ACTIVE"
            else:
                op_status = "UNKNOWN"

            blockers = []
            if freshness["status"] == "STALE":
                blockers.append({"type": "STALE_DATA", "message": f"Data is {freshness.get('age_minutes', '?')}min old"})
            if freshness["status"] == "UNKNOWN":
                blockers.append({"type": "UNKNOWN_FRESHNESS", "message": "No timestamp available"})
            if eligible == 0 and op_status != "STALE":
                blockers.append({"type": "NO_ELIGIBLE", "message": "No eligible drivers for this program"})

            remediation = []
            if freshness["status"] in ("STALE", "UNKNOWN"):
                remediation.append("Refresh program eligibility data")
            if eligible == 0:
                remediation.append("Run POST /programs/build-eligibility to generate eligibility")

            program_name_map = {
                "PROGRAM_HIGH_VALUE_RECOVERY": "High Value Recovery",
                "PROGRAM_CHURN_PREVENTION": "Churn Prevention",
                "PROGRAM_14_90": "14/90",
                "PROGRAM_ACTIVE_GROWTH": "Active Growth",
            }
            display_name = program_name_map.get(code, code.replace("PROGRAM_", ""))

            enriched.append({
                **p,
                "program_name": display_name,
                "eligible_total": eligible,
                "prioritized_total": prioritized,
                "actionable_today": actionable,
                "queued_total": queued,
                "exported_total": exported,
                "exported_campaigns_count": 1 if exported > 0 else 0,
                "status": op_status,
                "last_run_at": eligibility_date_str,
                "freshness": freshness,
                "explainability": explain_kpi("eligible_total", eligible, freshness, {"universe_total": 0}),
                "blockers": blockers,
                "remediation": remediation,
                "source": "STATIC_REGISTRY",
            })

        # Ensure all STATIC_REGISTRY programs appear, even with 0 eligible
        all_codes = {"PROGRAM_HIGH_VALUE_RECOVERY", "PROGRAM_CHURN_PREVENTION", "PROGRAM_14_90", "PROGRAM_ACTIVE_GROWTH"}
        existing_codes = {p["program_code"] for p in enriched}
        missing_codes = all_codes - existing_codes

        program_name_map = {
            "PROGRAM_HIGH_VALUE_RECOVERY": "High Value Recovery",
            "PROGRAM_CHURN_PREVENTION": "Churn Prevention",
            "PROGRAM_14_90": "14/90",
            "PROGRAM_ACTIVE_GROWTH": "Active Growth",
        }

        for code in missing_codes:
            enriched.append({
                "program_code": code,
                "program_name": program_name_map.get(code, code),
                "total": 0,
                "early_life": 0,
                "recoverable": 0,
                "churn_risk": 0,
                "eligible_total": 0,
                "prioritized_total": 0,
                "actionable_today": 0,
                "queued_total": 0,
                "exported_total": 0,
                "exported_campaigns_count": 0,
                "status": "EMPTY",
                "last_run_at": eligibility_date_str,
                "freshness": freshness,
                "explainability": explain_kpi("eligible_total", 0, freshness, {"universe_total": 0}),
                "blockers": [{"type": "NO_ELIGIBLE", "message": "No eligible drivers for this program"}],
                "remediation": ["Review eligibility criteria or wait for next eligibility refresh"],
                "source": "STATIC_REGISTRY",
            })

        return {
            "eligibility_date": eligibility_date_str,
            "programs": enriched,
            "source": "STATIC_REGISTRY",
            "notice": "Programas definidos en registry estatico. Program Builder pendiente P2.",
            "freshness": {
                "program_eligibility": freshness,
            },
        }


def get_program_drivers(
    eligibility_date_str: Optional[str] = None,
    program_code: Optional[str] = None,
    limit: int = 100,
) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if not eligibility_date_str:
            cur.execute(f"SELECT MAX(eligibility_date) FROM {TABLE_OUT}")
            r = cur.fetchone()
            if not r or not r["max"]:
                return []
            eligibility_date_str = str(r["max"])

        where = ["e.eligibility_date = %(d)s"]
        params = {"d": eligibility_date_str, "limit": min(limit, 500)}

        if program_code:
            where.append("e.program_code = %(pc)s")
            params["pc"] = program_code

        cur.execute(f"""
            SELECT e.driver_profile_id, e.program_code, e.eligible_flag,
                   e.eligibility_reason, e.priority,
                   s.lifecycle_state, s.performance_state, s.retention_state,
                   s.completed_orders_week, s.distance_to_weekly_target,
                   s.recoverable_flag, s.churn_risk_flag
            FROM {TABLE_OUT} e
            LEFT JOIN {TABLE_STATE} s
                ON e.driver_profile_id = s.driver_profile_id
                AND s.snapshot_date = (
                    SELECT MAX(snapshot_date) FROM {TABLE_STATE}
                    WHERE driver_profile_id = e.driver_profile_id
                )
            WHERE {' AND '.join(where)}
            ORDER BY e.priority ASC NULLS LAST, e.driver_profile_id
            LIMIT %(limit)s
        """, params)
        return [dict(r) for r in cur.fetchall()]
