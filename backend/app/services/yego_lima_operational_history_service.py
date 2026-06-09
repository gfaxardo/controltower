"""
YEGO Lima Growth — Operational History Service (LG-OEF-1.0A)
Consolidates membership history, actions, aging from existing tables.
"""
from __future__ import annotations
import logging
from typing import Any, Dict
from app.db.connection import get_db

logger = logging.getLogger(__name__)


def get_driver_operational_history(driver_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        # Membership history from existing tables
        cur.execute("""
            SELECT action_date, program_code, queue_status, priority_rank, assigned_channel
            FROM growth.yego_lima_driver_list_history
            WHERE driver_profile_id = %(did)s
            ORDER BY action_date DESC LIMIT 10
        """, {"did": driver_id})
        membership = []
        for r in cur.fetchall():
            membership.append({
                "date": str(r[0]), "program": r[1], "status": r[2],
                "rank": r[3], "channel": r[4],
            })

        # Program history from decision traces
        cur.execute("""
            SELECT snapshot_date, selected_program_code, selection_reason, final_rank
            FROM growth.yego_lima_program_decision_trace
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_date DESC LIMIT 10
        """, {"did": driver_id})
        program_history = []
        for r in cur.fetchall():
            program_history.append({
                "date": str(r[0]), "program": r[1], "reason": r[2], "rank": r[3],
            })

        # Actions
        cur.execute("""
            SELECT action_type, channel, agent, action_timestamp, result, notes
            FROM growth.yego_lima_action_ledger
            WHERE driver_profile_id = %(did)s
            ORDER BY action_timestamp DESC LIMIT 10
        """, {"did": driver_id})
        actions = []
        for r in cur.fetchall():
            actions.append({
                "type": r[0], "channel": r[1], "agent": r[2],
                "timestamp": r[3].isoformat() if r[3] else None,
                "result": r[4], "notes": r[5],
            })

        # Aging
        cur.execute("""
            SELECT MAX(action_timestamp), COUNT(*) FILTER (WHERE action_timestamp >= now() - interval '7 days'),
                   COUNT(*) FILTER (WHERE action_timestamp >= now() - interval '30 days')
            FROM growth.yego_lima_action_ledger
            WHERE driver_profile_id = %(did)s
        """, {"did": driver_id})
        aging_row = cur.fetchone()
        last_action = aging_row[0]
        actions_7d = aging_row[1] or 0
        actions_30d = aging_row[2] or 0

        days_since = None
        stale_status = "UNKNOWN"
        if last_action:
            cur.execute("SELECT EXTRACT(DAY FROM now() - %(la)s::timestamptz)::int", {"la": last_action})
            days_since = cur.fetchone()[0]
            if days_since <= 2:
                stale_status = "FRESH"
            elif days_since <= 6:
                stale_status = "AGING"
            elif days_since <= 13:
                stale_status = "STALE"
            else:
                stale_status = "CRITICAL"

        # Current queue status
        cur.execute("""
            SELECT assignment_date, queue_status, program_code, assigned_channel
            FROM growth.yego_lima_assignment_queue
            WHERE driver_id = %(did)s
            ORDER BY assignment_date DESC LIMIT 1
        """, {"did": driver_id})
        q = cur.fetchone()
        current_queue = None
        if q:
            current_queue = {"date": str(q[0]), "status": q[1], "program": q[2], "channel": q[3]}

    return {
        "driver_id": driver_id,
        "found": bool(membership or program_history or current_queue),
        "current": current_queue,
        "membership_history": membership,
        "program_history": program_history,
        "actions": actions,
        "aging": {
            "last_action_at": last_action.isoformat() if last_action else None,
            "days_since_last_action": days_since,
            "action_count_7d": actions_7d,
            "action_count_30d": actions_30d,
            "stale_status": stale_status,
        },
    }
