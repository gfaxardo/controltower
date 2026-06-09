"""
YEGO Lima Growth — Control Loop Service (LG-CTRL-1.0A)
Workflow states, action capture, aging, stuck detection, agent workload.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_CL = "growth.yego_lima_control_loop_state"


def get_control_loop_summary(date: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        wc = f"WHERE state_changed_at::date <= %(d)s::date" if date else ""
        params = {"d": date} if date else {}

        cur.execute(f"SELECT current_state, COUNT(*) FROM {TABLE_CL} {wc} GROUP BY current_state ORDER BY COUNT(*) DESC", params)
        by_state = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_CL} {wc}", params)
        total = cur.fetchone()[0] or 0

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_CL} WHERE is_stale = true {('AND state_changed_at::date <= %(d)s::date' if date else '')}", params)
        stale = cur.fetchone()[0] or 0

    return {
        "date": date or "all",
        "total": total,
        "by_state": by_state,
        "ready": by_state.get("READY", 0),
        "contacted": by_state.get("CONTACTED", 0),
        "done": by_state.get("DONE", 0) + by_state.get("CLOSED", 0),
        "stale": stale,
    }


def get_agent_summary() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT COALESCE(agent, 'UNASSIGNED'), COUNT(*),
                   SUM(CASE WHEN current_state IN ('DONE','CLOSED') THEN 1 ELSE 0 END),
                   SUM(CASE WHEN current_state IN ('READY','ASSIGNED','IN_PROGRESS') THEN 1 ELSE 0 END)
            FROM {TABLE_CL} GROUP BY agent ORDER BY COUNT(*) DESC
        """)
        agents = []
        for r in cur.fetchall():
            agents.append({
                "agent": r[0], "total": r[1], "closed": r[2], "pending": r[3],
            })
    return {"agents": agents, "total_agents": len(agents)}


def get_stale_drivers(limit: int = 20) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT driver_profile_id, current_state, agent, channel,
                   days_in_current_state, state_changed_at
            FROM {TABLE_CL}
            WHERE is_stale = true
            ORDER BY days_in_current_state DESC LIMIT %(lim)s
        """, {"lim": limit})
        drivers = []
        for r in cur.fetchall():
            drivers.append({
                "driver_id": r[0], "state": r[1], "agent": r[2], "channel": r[3],
                "days_stuck": r[4], "since": r[5].isoformat() if r[5] else None,
            })
    return {"drivers": drivers, "total": len(drivers)}


def get_driver_control_loop(driver_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT current_state, previous_state, state_changed_at,
                   agent, channel, notes, days_in_current_state, is_stale
            FROM {TABLE_CL}
            WHERE driver_profile_id = %(did)s
            ORDER BY state_changed_at DESC LIMIT 1
        """, {"did": driver_id})
        cl = cur.fetchone()

        # History
        cur.execute("""
            SELECT action_type, agent, channel, action_timestamp, result, notes
            FROM growth.yego_lima_action_ledger
            WHERE driver_profile_id = %(did)s
            ORDER BY action_timestamp DESC LIMIT 20
        """, {"did": driver_id})
        actions = []
        for r in cur.fetchall():
            actions.append({
                "type": r[0], "agent": r[1], "channel": r[2],
                "timestamp": r[3].isoformat() if r[3] else None,
                "result": r[4], "notes": r[5],
            })

    result = {"driver_id": driver_id, "found": bool(cl)}
    if cl:
        result["control_loop"] = {
            "current_state": cl[0], "previous_state": cl[1],
            "state_changed_at": cl[2].isoformat() if cl[2] else None,
            "agent": cl[3], "channel": cl[4], "notes": cl[5],
            "days_in_state": cl[6], "is_stale": cl[7],
        }
    result["actions"] = actions
    return result
