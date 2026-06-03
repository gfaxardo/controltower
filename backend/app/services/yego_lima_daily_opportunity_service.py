"""
YEGO Lima Growth — Daily Opportunity Engine Service (Fase 2D-R).

Generates daily opportunity lists from program_eligibility.
Replaces conceptual use of actionable_list_daily legacy.

Principles:
- Lists are generated fresh daily from programs (reset diario)
- Programs consume states, lists consume programs
- Pending from previous day are NOT carried forward
- History is preserved

Opportunity Types:
- OPPORTUNITY_14_90
- OPPORTUNITY_ACTIVE_GROWTH
- OPPORTUNITY_CHURN_PREVENTION
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_PROGRAM = "growth.yango_lima_program_eligibility_daily"
TABLE_STATE = "growth.yango_lima_driver_state_snapshot"
TABLE_OUT = "growth.yango_lima_daily_opportunity_list"

OPPORTUNITY_14_90 = "OPPORTUNITY_14_90"
OPPORTUNITY_ACTIVE_GROWTH = "OPPORTUNITY_ACTIVE_GROWTH"
OPPORTUNITY_CHURN_PREVENTION = "OPPORTUNITY_CHURN_PREVENTION"

PROGRAM_TO_OPPORTUNITY = {
    "PROGRAM_14_90": OPPORTUNITY_14_90,
    "PROGRAM_ACTIVE_GROWTH": OPPORTUNITY_ACTIVE_GROWTH,
    "PROGRAM_CHURN_PREVENTION": OPPORTUNITY_CHURN_PREVENTION,
}


def build_daily_opportunity_lists(opportunity_date_str: str) -> Dict[str, Any]:
    opportunity_date = date.fromisoformat(opportunity_date_str)

    logger.info("Building daily opportunity lists: date=%s", opportunity_date)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"SELECT MAX(eligibility_date) FROM {TABLE_PROGRAM}")
        latest = cur.fetchone()
        if not latest or not latest["max"]:
            return {"ok": False, "error": "No program eligibility data available"}
        prog_date = latest["max"]

        # Find latest state snapshot
        cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_STATE}")
        snap_r = cur.fetchone()
        snap_date = snap_r["max"] if snap_r and snap_r["max"] else prog_date

        # Clear existing for this date (fresh generation)
        cur.execute(f"DELETE FROM {TABLE_OUT} WHERE opportunity_date = %(d)s", {"d": opportunity_date})

        counts = {}
        total = 0

        for prog_code, opp_type in PROGRAM_TO_OPPORTUNITY.items():
            cur.execute(f"""
                INSERT INTO {TABLE_OUT} (
                    opportunity_date, driver_profile_id, opportunity_type, program_code,
                    priority, opportunity_reason,
                    lifecycle_state, performance_state, retention_state,
                    completed_orders_week, supply_hours_week,
                    distance_to_weekly_target, trips_per_supply_hour_week,
                    management_status
                )
                SELECT %(d)s, e.driver_profile_id, %(ot)s, e.program_code,
                       e.priority, e.eligibility_reason,
                       s.lifecycle_state, s.performance_state, s.retention_state,
                       s.completed_orders_week, s.supply_hours_week,
                       s.distance_to_weekly_target, s.trips_per_supply_hour_week,
                       'PENDING_ACTION'
                FROM {TABLE_PROGRAM} e
                LEFT JOIN {TABLE_STATE} s
                    ON e.driver_profile_id = s.driver_profile_id
                    AND s.snapshot_date = %(sd)s
                WHERE e.eligibility_date = %(ed)s
                  AND e.program_code = %(pc)s
                  AND e.eligible_flag = true
                ON CONFLICT (opportunity_date, driver_profile_id, opportunity_type) DO NOTHING
            """, {
                "d": opportunity_date, "ot": opp_type,
                "ed": prog_date, "pc": prog_code, "sd": snap_date,
            })

            cur.execute(f"""
                SELECT COUNT(*) FROM {TABLE_OUT}
                WHERE opportunity_date = %(d)s AND opportunity_type = %(ot)s
            """, {"d": opportunity_date, "ot": opp_type})
            cnt = cur.fetchone()["count"]
            counts[opp_type] = cnt
            total += cnt

        conn.commit()

    return {
        "ok": True,
        "opportunity_date": opportunity_date_str,
        "source_eligibility_date": str(prog_date),
        "source_snapshot_date": str(snap_date) if snap_date else None,
        "total_opportunities": total,
        "by_opportunity_type": counts,
    }


def close_unmanaged_opportunities(opportunity_date_str: str) -> Dict[str, Any]:
    opportunity_date = date.fromisoformat(opportunity_date_str)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            UPDATE {TABLE_OUT}
            SET management_status = 'NO_ACTION', closed_at = now()
            WHERE opportunity_date = %(d)s AND management_status = 'PENDING_ACTION'
        """, {"d": opportunity_date})
        closed = cur.rowcount
        conn.commit()

    return {"ok": True, "opportunity_date": opportunity_date_str, "items_closed": closed}


def get_daily_opportunities(
    opportunity_date: Optional[str] = None,
    opportunity_type: Optional[str] = None,
    management_status: Optional[str] = None,
    assigned_agent: Optional[str] = None,
    limit: int = 100,
) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if not opportunity_date:
            cur.execute(f"SELECT MAX(opportunity_date) FROM {TABLE_OUT}")
            r = cur.fetchone()
            if not r or not r["max"]:
                return []
            opportunity_date = str(r["max"])

        where = ["opportunity_date = %(d)s"]
        params = {"d": opportunity_date, "limit": min(limit, 500)}

        if opportunity_type:
            where.append("opportunity_type = %(ot)s")
            params["ot"] = opportunity_type
        if management_status:
            where.append("management_status = %(ms)s")
            params["ms"] = management_status
        if assigned_agent:
            where.append("assigned_agent = %(ag)s")
            params["ag"] = assigned_agent

        cur.execute(f"""
            SELECT opportunity_date, driver_profile_id, opportunity_type, program_code,
                   priority, opportunity_reason,
                   lifecycle_state, performance_state, retention_state,
                   completed_orders_week, supply_hours_week,
                   distance_to_weekly_target, trips_per_supply_hour_week,
                   management_status, assigned_agent, action_id,
                   generated_at, closed_at
            FROM {TABLE_OUT}
            WHERE {' AND '.join(where)}
            ORDER BY priority ASC NULLS LAST
            LIMIT %(limit)s
        """, params)

        result = []
        for row in cur.fetchall():
            item = dict(row)
            item["opportunity_date"] = str(item["opportunity_date"])
            if item.get("generated_at"):
                item["generated_at"] = item["generated_at"].isoformat()
            if item.get("closed_at"):
                item["closed_at"] = item["closed_at"].isoformat()
            result.append(item)
        return result


def assign_agent(
    opportunity_date_str: str,
    driver_profile_id: str,
    opportunity_type: str,
    agent: str,
) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_OUT}
            SET assigned_agent = %(agent)s
            WHERE opportunity_date = %(d)s
              AND driver_profile_id = %(did)s
              AND opportunity_type = %(ot)s
        """, {
            "d": opportunity_date_str, "did": driver_profile_id,
            "ot": opportunity_type, "agent": agent,
        })
        conn.commit()
        return {"ok": cur.rowcount > 0, "assigned_agent": agent}


def link_action(
    opportunity_date_str: str,
    driver_profile_id: str,
    opportunity_type: str,
    action_id: str,
    management_status: str = "ACTION_CONFIRMED",
) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_OUT}
            SET action_id = %(aid)s::uuid,
                management_status = %(ms)s,
                closed_at = CASE WHEN %(ms)s != 'PENDING_ACTION' THEN now() ELSE closed_at END
            WHERE opportunity_date = %(d)s
              AND driver_profile_id = %(did)s
              AND opportunity_type = %(ot)s
        """, {
            "d": opportunity_date_str, "did": driver_profile_id,
            "ot": opportunity_type, "aid": action_id, "ms": management_status,
        })
        conn.commit()
        return {"ok": cur.rowcount > 0, "status": management_status}
