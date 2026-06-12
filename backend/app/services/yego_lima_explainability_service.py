"""
LG-UI-1B — Unified Explainability Service
Aggregates explanations across all domains per driver.
Read-only. Reads from persisted traces. NO recalculation. NO inference.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_LC = "growth.yego_lima_driver_lifecycle_daily"
TABLE_LC_EVENT = "growth.yego_lima_driver_lifecycle_event"
TABLE_TAX = "growth.yego_lima_driver_taxonomy_v2_daily"
TABLE_DT = "growth.yego_lima_program_decision_trace"
TABLE_TT = "growth.yego_lima_state_transition_trace"
TABLE_DS = "growth.yango_lima_driver_state_snapshot"
TABLE_PR = "growth.yango_lima_program_eligibility_daily"
TABLE_DH = "growth.yango_lima_driver_history_daily"


def _safe_json(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val) if isinstance(val, str) else val
    except (json.JSONDecodeError, TypeError):
        return val


def get_driver_explainability(driver_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        result = {"driver_id": driver_id, "found": False, "domains": {}}

        # ── Lifecycle ──
        cur.execute(f"""
            SELECT lifecycle_status, lifecycle_reason, evidence_json,
                   completed_trips_7d, completed_trips_30d,
                   days_since_last_completed_trip, lifecycle_version,
                   snapshot_date
            FROM {TABLE_LC}
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_date DESC LIMIT 1
        """, {"did": driver_id})
        lc = cur.fetchone()
        if lc:
            result["found"] = True
            result["domains"]["lifecycle"] = {
                "status": lc[0],
                "reason": lc[1] or "No explicit reason recorded",
                "evidence": _safe_json(lc[2]),
                "trips_7d": lc[3],
                "trips_30d": lc[4],
                "days_since_last_trip": lc[5],
                "version": lc[6],
                "source_date": str(lc[7]) if lc[7] else None,
            }

        # ── Segment / Taxonomy ──
        cur.execute(f"""
            SELECT operational_status, activity_status, value_tier,
                   momentum_state, operational_persona,
                   matched_rules_json, failed_rules_json,
                   snapshot_date
            FROM {TABLE_TAX}
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_date DESC LIMIT 1
        """, {"did": driver_id})
        tx = cur.fetchone()
        if tx:
            result["found"] = True
            result["domains"]["segment"] = {
                "operational_status": tx[0],
                "activity_status": tx[1],
                "value_tier": tx[2],
                "momentum": tx[3],
                "persona": tx[4],
                "matched_rules": _safe_json(tx[5]),
                "failed_rules": _safe_json(tx[6]),
                "source_date": str(tx[7]) if tx[7] else None,
            }

        # ── Program ──
        cur.execute(f"""
            SELECT selected_program_code, selection_reason,
                   opportunity_score, final_rank, eligible_programs_json,
                   evidence_json, snapshot_date
            FROM {TABLE_DT}
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_date DESC LIMIT 1
        """, {"did": driver_id})
        pt = cur.fetchone()
        if pt:
            result["found"] = True
            result["domains"]["program"] = {
                "selected_program": pt[0],
                "selection_reason": pt[1] or "No selection reason recorded",
                "opportunity_score": float(pt[2]) if pt[2] is not None else None,
                "final_rank": pt[3],
                "eligible_programs": _safe_json(pt[4]),
                "evidence": _safe_json(pt[5]),
                "source_date": str(pt[6]) if pt[6] else None,
            }

        # ── Movement ──
        cur.execute(f"""
            SELECT transition_type, trigger_reason,
                   rule_delta_json, state_before_json, state_after_json,
                   evidence_json, snapshot_after
            FROM {TABLE_TT}
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_after DESC LIMIT 1
        """, {"did": driver_id})
        mt = cur.fetchone()
        if mt:
            result["found"] = True
            result["domains"]["movement"] = {
                "transition_type": mt[0],
                "trigger_reason": mt[1] or "No trigger reason recorded",
                "rule_deltas": _safe_json(mt[2]),
                "state_before": _safe_json(mt[3]),
                "state_after": _safe_json(mt[4]),
                "evidence": _safe_json(mt[5]),
                "source_date": str(mt[6]) if mt[6] else None,
            }

        # ── RNA ──
        cur.execute(f"""
            SELECT is_rna, contactability, cancelled_signal,
                   registration_date, first_trip_date, last_trip_date,
                   phone_available
            FROM {TABLE_DS}
            WHERE driver_profile_id = %(did)s
            ORDER BY snapshot_date DESC LIMIT 1
        """, {"did": driver_id})
        rna = cur.fetchone()
        if rna:
            result["found"] = True
            raw_rna = {
                "is_rna": rna[0],
                "contactable": rna[1] if rna[1] is not None else rna[6],
                "cancelled_signal": rna[2],
                "registration_date": str(rna[3]) if rna[3] else None,
                "first_trip_date": str(rna[4]) if rna[4] else None,
                "last_trip_date": str(rna[5]) if rna[5] else None,
            }
            # Add RNA-specific explanation
            reasons = []
            if raw_rna["is_rna"]:
                if not raw_rna["first_trip_date"]:
                    reasons.append("Driver registered but has never completed a trip")
                if not raw_rna["contactable"]:
                    reasons.append("Driver has no phone on file — cannot be contacted")
                if raw_rna["cancelled_signal"]:
                    reasons.append("Driver cancelled after being contacted")
            result["domains"]["rna"] = {
                **raw_rna,
                "reason": "; ".join(reasons) if reasons else "Driver is not RNA or no explanation available",
            }

        return result


def get_explainability_by_domain(driver_id: str, domain: str) -> Dict[str, Any]:
    full = get_driver_explainability(driver_id)
    if not full.get("found"):
        return {"driver_id": driver_id, "found": False, "domain": domain, "explanation": None}
    domain_data = full.get("domains", {}).get(domain)
    return {
        "driver_id": driver_id,
        "found": True,
        "domain": domain,
        "explanation": domain_data,
    }
