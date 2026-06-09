"""
YEGO Lima Growth — Diagnostic Trace Serving API (LG-DIAG-R1.4A)
Reads from persisted trace tables. NO recalculation. NO runtime logic.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_DT = "growth.yego_lima_program_decision_trace"
TABLE_TT = "growth.yego_lima_state_transition_trace"


def get_driver_diagnostic_trace(driver_id: str) -> Dict[str, Any]:
    """Consolidated diagnostic view for one driver from persisted traces."""
    with get_db() as conn:
        cur = conn.cursor()

        # Latest decision trace
        cur.execute(f"""
            SELECT snapshot_date, selected_program_code, selection_reason,
                   opportunity_score, final_rank, eligible_programs_json,
                   policy_version, run_id, evidence_json, created_at
            FROM {TABLE_DT}
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_date DESC LIMIT 1
        """, {"did": driver_id})
        dt = cur.fetchone()

        # Latest transition trace
        cur.execute(f"""
            SELECT snapshot_before, snapshot_after, transition_type,
                   trigger_reason, rule_delta_json, state_before_json,
                   state_after_json, policy_version, run_id, evidence_json, created_at
            FROM {TABLE_TT}
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_after DESC LIMIT 1
        """, {"did": driver_id})
        tt = cur.fetchone()

    result = {"driver_id": driver_id, "found": bool(dt or tt)}

    if dt:
        result["program_trace"] = {
            "snapshot_date": str(dt[0]),
            "selected_program": dt[1],
            "selection_reason": dt[2],
            "opportunity_score": float(dt[3]) if dt[3] else 0,
            "final_rank": dt[4],
            "eligible_programs": dt[5] if isinstance(dt[5], list) else [],
            "policy_version": dt[6],
            "run_id": dt[7],
            "created_at": dt[9].isoformat() if dt[9] else None,
        }
    if tt:
        result["transition_trace"] = {
            "snapshot_before": str(tt[0]),
            "snapshot_after": str(tt[1]),
            "transition_type": tt[2],
            "trigger_reason": tt[3],
            "rule_deltas": tt[4] if isinstance(tt[4], list) else [],
            "state_before": tt[5] if isinstance(tt[5], dict) else {},
            "state_after": tt[6] if isinstance(tt[6], dict) else {},
            "policy_version": tt[7],
            "run_id": tt[8],
            "created_at": tt[10].isoformat() if tt[10] else None,
        }

    return result


def get_program_traces(
    driver_id: Optional[str] = None,
    snapshot_date: Optional[str] = None,
    selected_program: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Query decision traces with filters. Read-only from persisted table."""
    with get_db() as conn:
        cur = conn.cursor()
        where = []
        params: Dict[str, Any] = {"lim": min(limit, 1000), "off": offset}

        if driver_id:
            where.append("driver_profile_id = %(did)s")
            params["did"] = driver_id
        if snapshot_date:
            where.append("snapshot_date = %(sd)s")
            params["sd"] = snapshot_date
        if selected_program:
            where.append("selected_program_code = %(spc)s")
            params["spc"] = selected_program
        if run_id:
            where.append("run_id = %(rid)s")
            params["rid"] = run_id

        wc = "WHERE " + " AND ".join(where) if where else ""

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_DT} {wc}", params)
        total = cur.fetchone()[0] or 0

        cur.execute(f"""
            SELECT driver_profile_id, snapshot_date, selected_program_code,
                   selection_reason, opportunity_score, final_rank,
                   eligible_programs_json, policy_version, run_id, created_at
            FROM {TABLE_DT} {wc}
            ORDER BY created_at DESC LIMIT %(lim)s OFFSET %(off)s
        """, params)
        records = []
        for r in cur.fetchall():
            records.append({
                "driver_id": r[0], "snapshot_date": str(r[1]), "selected_program": r[2],
                "selection_reason": r[3], "opportunity_score": float(r[4]) if r[4] else 0,
                "final_rank": r[5], "eligible_programs": r[6] if isinstance(r[6], list) else [],
                "policy_version": r[7], "run_id": r[8],
                "created_at": r[9].isoformat() if r[9] else None,
            })

    return {"total": total, "limit": limit, "offset": offset, "records": records}


def get_transition_traces(
    driver_id: Optional[str] = None,
    snapshot_before: Optional[str] = None,
    snapshot_after: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Query transition traces with filters. Read-only from persisted table."""
    with get_db() as conn:
        cur = conn.cursor()
        where = []
        params: Dict[str, Any] = {"lim": min(limit, 1000), "off": offset}

        if driver_id:
            where.append("driver_profile_id = %(did)s")
            params["did"] = driver_id
        if snapshot_before:
            where.append("snapshot_before = %(sb)s")
            params["sb"] = snapshot_before
        if snapshot_after:
            where.append("snapshot_after = %(sa)s")
            params["sa"] = snapshot_after
        if run_id:
            where.append("run_id = %(rid)s")
            params["rid"] = run_id

        wc = "WHERE " + " AND ".join(where) if where else ""

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_TT} {wc}", params)
        total = cur.fetchone()[0] or 0

        cur.execute(f"""
            SELECT driver_profile_id, snapshot_before, snapshot_after,
                   transition_type, trigger_reason, rule_delta_json,
                   state_before_json, state_after_json, policy_version,
                   run_id, created_at
            FROM {TABLE_TT} {wc}
            ORDER BY created_at DESC LIMIT %(lim)s OFFSET %(off)s
        """, params)
        records = []
        for r in cur.fetchall():
            records.append({
                "driver_id": r[0], "snapshot_before": str(r[1]), "snapshot_after": str(r[2]),
                "transition_type": r[3], "trigger_reason": r[4],
                "rule_deltas": r[5] if isinstance(r[5], list) else [],
                "state_before": r[6] if isinstance(r[6], dict) else {},
                "state_after": r[7] if isinstance(r[7], dict) else {},
                "policy_version": r[8], "run_id": r[9],
                "created_at": r[10].isoformat() if r[10] else None,
            })

    return {"total": total, "limit": limit, "offset": offset, "records": records}
