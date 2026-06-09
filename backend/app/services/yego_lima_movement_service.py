"""
YEGO Lima Growth — Movement Attribution Service (LG-ATTR-1.0A)
Aggregates movements from existing transition + decision traces.
No new tables needed. Builds on R1.3A persistence.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)


def get_daily_movement_summary(snapshot_date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        # Program changes from decision traces
        cur.execute("""
            SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace
            WHERE snapshot_date = %(d)s
        """, {"d": snapshot_date})
        program_total = cur.fetchone()[0] or 0

        # State changes from transition traces
        cur.execute("""
            SELECT transition_type, COUNT(*) FROM growth.yego_lima_state_transition_trace
            WHERE snapshot_after = %(d)s
            GROUP BY transition_type ORDER BY COUNT(*) DESC
        """, {"d": snapshot_date})
        transitions = {r[0]: r[1] for r in cur.fetchall()}

        state_changes = sum(transitions.values())
        entries = sum(v for k, v in transitions.items() if 'ENTERED' in str(k))
        exits = sum(v for k, v in transitions.items() if 'EXITED' in str(k))

        # Membership history
        cur.execute("""
            SELECT COUNT(*) FROM growth.yego_lima_driver_list_history
            WHERE action_date = %(d)s
        """, {"d": snapshot_date})
        membership_total = cur.fetchone()[0] or 0

    return {
        "date": snapshot_date,
        "total_movements": program_total + state_changes,
        "program_decisions": program_total,
        "state_changes": state_changes,
        "entries": entries,
        "exits": exits,
        "membership_records": membership_total,
        "transition_types": transitions,
    }


def get_driver_movement_history(driver_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        # State transitions
        cur.execute("""
            SELECT snapshot_before, snapshot_after, transition_type,
                   trigger_reason, rule_delta_json, state_before_json, state_after_json
            FROM growth.yego_lima_state_transition_trace
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_after DESC LIMIT 20
        """, {"did": driver_id})
        state_movements = []
        for r in cur.fetchall():
            state_movements.append({
                "date": str(r[1]),
                "type": "STATE_CHANGE",
                "transition": r[2],
                "trigger": r[3],
                "rule_deltas": r[4] if isinstance(r[4], list) else [],
            })

        # Program changes
        cur.execute("""
            SELECT snapshot_date, selected_program_code, selection_reason,
                   eligible_programs_json
            FROM growth.yego_lima_program_decision_trace
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_date DESC LIMIT 20
        """, {"did": driver_id})
        program_movements = []
        prev_prog = None
        for r in cur.fetchall():
            curr = r[1]
            change = None
            if prev_prog and prev_prog != curr:
                change = f"{prev_prog} -> {curr}"
            elif not prev_prog:
                change = f"ENTERED: {curr}"
            prev_prog = curr

            program_movements.append({
                "date": str(r[0]),
                "type": "PROGRAM_CHANGE" if change and 'ENTERED' not in str(change) else "PROGRAM_ENTRY",
                "change": change or f"CONTINUED: {curr}",
                "program": curr,
                "reason": r[2],
            })

        # Membership
        cur.execute("""
            SELECT action_date, program_code, queue_status
            FROM growth.yego_lima_driver_list_history
            WHERE driver_profile_id = %(did)s
            ORDER BY action_date DESC LIMIT 20
        """, {"did": driver_id})
        membership = []
        for r in cur.fetchall():
            membership.append({"date": str(r[0]), "program": r[1], "status": r[2]})

    # Merge all movements chronologically
    all_movements = []
    for m in state_movements:
        all_movements.append({"date": m["date"], "type": m["type"], "detail": m})
    for m in program_movements:
        all_movements.append({"date": m["date"], "type": m["type"], "detail": m})
    all_movements.sort(key=lambda x: x["date"], reverse=True)

    return {
        "driver_id": driver_id,
        "found": bool(state_movements or program_movements or membership),
        "total_movements": len(all_movements),
        "movements": all_movements[:30],
        "state_movements": state_movements,
        "program_movements": program_movements,
        "membership": membership,
    }


def get_movement_list(
    movement_date: Optional[str] = None,
    driver_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        params: Dict[str, Any] = {"lim": min(limit, 1000), "off": offset}

        where_state = []
        where_prog = []
        if movement_date:
            where_state.append("snapshot_after = %(d)s")
            where_prog.append("snapshot_date = %(d)s")
            params["d"] = movement_date
        if driver_id:
            where_state.append("driver_profile_id = %(did)s")
            where_prog.append("driver_profile_id = %(did)s")
            params["did"] = driver_id

        wc_s = "WHERE " + " AND ".join(where_state) if where_state else ""
        wc_p = "WHERE " + " AND ".join(where_prog) if where_prog else ""

        cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_state_transition_trace {wc_s}", params)
        state_total = cur.fetchone()[0] or 0
        cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace {wc_p}", params)
        prog_total = cur.fetchone()[0] or 0

        # Get state movements
        cur.execute(f"""
            SELECT driver_profile_id, snapshot_before, snapshot_after, transition_type,
                   trigger_reason
            FROM growth.yego_lima_state_transition_trace {wc_s}
            ORDER BY snapshot_after DESC LIMIT %(lim)s OFFSET %(off)s
        """, params)
        records = []
        for r in cur.fetchall():
            records.append({
                "driver_id": r[0], "type": "STATE_CHANGE",
                "before": str(r[1]), "after": str(r[2]),
                "transition": r[3], "trigger": r[4],
            })

    return {
        "total": state_total + prog_total,
        "limit": limit, "offset": offset,
        "records": records,
    }
