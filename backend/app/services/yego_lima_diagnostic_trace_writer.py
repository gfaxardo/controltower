"""
LG-DIAG-R1.3A — Diagnostic Trace Persistence Writer
Persists decision traces and transition traces. Idempotent.
"""
from __future__ import annotations
import json, logging
from typing import Any, Dict, List
from uuid import uuid4
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_DT = "growth.yego_lima_program_decision_trace"
TABLE_TT = "growth.yego_lima_state_transition_trace"


def write_decision_traces(run_id: str, snapshot_date: str, traces: List[Dict]) -> Dict[str, Any]:
    inserted = 0
    with get_db() as conn:
        cur = conn.cursor()
        for t in traces:
            cur.execute(f"""
                INSERT INTO {TABLE_DT} (run_id, snapshot_date, driver_profile_id,
                    eligible_programs_json, selected_program_code, selection_reason,
                    opportunity_score, final_rank, policy_version, evidence_json)
                VALUES (%(rid)s, %(sd)s, %(did)s, %(epj)s::jsonb, %(spc)s, %(sr)s,
                        %(os)s, %(fr)s, %(pv)s, %(ev)s::jsonb)
                ON CONFLICT (run_id, driver_profile_id, snapshot_date) DO UPDATE SET
                    eligible_programs_json = EXCLUDED.eligible_programs_json,
                    selected_program_code = EXCLUDED.selected_program_code,
                    selection_reason = EXCLUDED.selection_reason,
                    opportunity_score = EXCLUDED.opportunity_score,
                    final_rank = EXCLUDED.final_rank,
                    evidence_json = EXCLUDED.evidence_json
            """, {
                "rid": run_id, "sd": snapshot_date, "did": t["driver_id"],
                "epj": json.dumps(t.get("eligible_programs", [])),
                "spc": t.get("selected_program"), "sr": t.get("selection_reason"),
                "os": t.get("selection_score", 0), "fr": t.get("selection_priority"),
                "pv": t.get("policy_version", "v1"),
                "ev": json.dumps(t, default=str),
            })
            inserted += 1
        conn.commit()
    return {"inserted": inserted, "run_id": run_id}


def write_transition_traces(run_id: str, snapshot_before: str, snapshot_after: str, traces: List[Dict]) -> Dict[str, Any]:
    inserted = 0
    with get_db() as conn:
        cur = conn.cursor()
        for t in traces:
            cur.execute(f"""
                INSERT INTO {TABLE_TT} (run_id, snapshot_before, snapshot_after, driver_profile_id,
                    state_before_json, state_after_json, transition_type,
                    rule_delta_json, trigger_reason, evidence_json, policy_version)
                VALUES (%(rid)s, %(sb)s, %(sa)s, %(did)s,
                        %(stb)s::jsonb, %(sta)s::jsonb, %(tt)s,
                        %(rdj)s::jsonb, %(tr)s, %(ev)s::jsonb, %(pv)s)
                ON CONFLICT (run_id, driver_profile_id, snapshot_before, snapshot_after) DO UPDATE SET
                    state_before_json = EXCLUDED.state_before_json,
                    state_after_json = EXCLUDED.state_after_json,
                    transition_type = EXCLUDED.transition_type,
                    rule_delta_json = EXCLUDED.rule_delta_json,
                    trigger_reason = EXCLUDED.trigger_reason,
                    evidence_json = EXCLUDED.evidence_json
            """, {
                "rid": run_id, "sb": snapshot_before, "sa": snapshot_after,
                "did": t["driver_id"],
                "stb": json.dumps(t.get("state_before", {})),
                "sta": json.dumps(t.get("state_after", {})),
                "tt": t.get("transition_type"),
                "rdj": json.dumps(t.get("rule_deltas", [])),
                "tr": t.get("trigger_reason"),
                "ev": json.dumps(t, default=str),
                "pv": t.get("policy_version", "v1"),
            })
            inserted += 1
        conn.commit()
    return {"inserted": inserted, "run_id": run_id}
