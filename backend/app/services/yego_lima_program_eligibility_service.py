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

        return {"eligibility_date": eligibility_date_str, "programs": programs}


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
