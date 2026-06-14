"""
YEGO Lima Growth — Exclusive Worklist Transition Service (LG-TRACE-1B)

Compares consecutive daily worklists and classifies driver movements.
Reads ONLY from growth.yango_lima_exclusive_driver_worklist_daily.
Does NOT recalculate assignments. V1 operational traceability.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from app.db.connection import _get_connection_params, get_db

logger = logging.getLogger(__name__)

TABLE_WORKLIST = "growth.yango_lima_exclusive_driver_worklist_daily"
TABLE_OUT = "growth.yango_lima_exclusive_worklist_transition_daily"

TRANSITION_LOCK_ID = 9020
BAND_ORDER = ["0", "1-10", "11-20", "21-30", "31-40", "41-50", "51-75", "76-99", "100+"]

RECOVERY_UNIVERSES = {"RECOVERY_RECENT_INACTIVE_HIGH_VALUE", "RECOVERY_RECENT_INACTIVE_LOW_VALUE"}
CEMETERY_UNIVERSE = {"CEMETERY_LONG_CHURNED"}


def _band_index(band: Optional[str]) -> int:
    try:
        return BAND_ORDER.index(band) if band else -1
    except ValueError:
        return -1


def _acquire_lock(conn) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT pg_try_advisory_lock(%(id)s)", {"id": TRANSITION_LOCK_ID})
    return cur.fetchone()[0]


def _release_lock(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_unlock(%(id)s)", {"id": TRANSITION_LOCK_ID})
    except Exception:
        pass


def _classify_transition(prev: Optional[Dict], curr: Optional[Dict]) -> Dict[str, Any]:
    p_uni = (prev or {}).get("assigned_universe_v1")
    c_uni = (curr or {}).get("assigned_universe_v1")
    p_inact = (prev or {}).get("inactivity_days") or 0
    c_inact = (curr or {}).get("inactivity_days") or 0
    p_wk = (prev or {}).get("weekly_trips") or 0
    c_wk = (curr or {}).get("weekly_trips") or 0
    p_act = (prev or {}).get("activation_window_trips") or 0
    c_act = (curr or {}).get("activation_window_trips") or 0
    p_band = (prev or {}).get("productivity_band")
    c_band = (curr or {}).get("productivity_band")

    ttype = "NO_DATA"
    reason = ""
    goal_met = False
    recovered = False
    inact_before = None

    if not curr:
        return {"transition_type": "NO_DATA", "transition_reason": "No current worklist row.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}

    if not prev or not p_uni:
        return {"transition_type": "ENTERED_LIST", "transition_reason": "Driver entered this operational list for the first time in tracked worklist history.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}

    # RECOVERED_TO_ACTIVE: inactive >=45 days, now active
    if p_inact >= 45 and c_inact < p_inact and c_uni not in RECOVERY_UNIVERSES and c_uni not in CEMETERY_UNIVERSE:
        return {"transition_type": "RECOVERED_TO_ACTIVE", "transition_reason": f"Driver returned to active work after {p_inact} days without trips. Classified as recovered (threshold: 45 days).", "goal_met_flag": False, "recovered_flag": True, "inactivity_days_before_return": p_inact}

    if p_uni in RECOVERY_UNIVERSES | CEMETERY_UNIVERSE and c_uni not in RECOVERY_UNIVERSES and c_uni not in CEMETERY_UNIVERSE:
        return {"transition_type": "RECOVERED_TO_ACTIVE", "transition_reason": f"Driver returned to active work from {p_uni}.", "goal_met_flag": False, "recovered_flag": True, "inactivity_days_before_return": p_inact}

    # EXITED_GOAL_MET
    if p_uni == "NEW_REACTIVATED_0_14_TO_50" and p_act < 50 and c_act >= 50:
        return {"transition_type": "EXITED_GOAL_MET", "transition_reason": f"Driver achieved activation goal: activation_window_trips reached {c_act} (threshold: 50).", "goal_met_flag": True, "recovered_flag": False, "inactivity_days_before_return": None}

    if p_uni == "RAMP_UP_15_45_TO_100W" and p_wk < 100 and c_wk >= 100:
        return {"transition_type": "EXITED_GOAL_MET", "transition_reason": f"Driver achieved weekly goal: weekly_trips reached {c_wk} (threshold: 100).", "goal_met_flag": True, "recovered_flag": False, "inactivity_days_before_return": None}

    if p_uni == "CONSOLIDATION_46_90_TO_100W" and p_wk < 100 and c_wk >= 100:
        return {"transition_type": "EXITED_GOAL_MET", "transition_reason": f"Driver achieved consolidation goal: weekly_trips reached {c_wk} (threshold: 100).", "goal_met_flag": True, "recovered_flag": False, "inactivity_days_before_return": None}

    # PROTECTED_GOAL_MET
    if c_uni == "PROTECTED_ALREADY_MEETING_GOAL" and (c_wk >= 100 or c_act >= 50):
        return {"transition_type": "PROTECTED_GOAL_MET", "transition_reason": f"Driver reached protected state: weekly_trips={c_wk}, activation_trips={c_act}.", "goal_met_flag": True, "recovered_flag": False, "inactivity_days_before_return": None}

    # MOVED_TO_CEMETERY
    if c_uni == "CEMETERY_LONG_CHURNED" and p_uni != "CEMETERY_LONG_CHURNED":
        return {"transition_type": "MOVED_TO_CEMETERY", "transition_reason": f"Driver moved to cemetery. Inactivity reached {c_inact} days (>60).", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}

    # MOVED_TO_RECOVERY
    if c_uni in RECOVERY_UNIVERSES and p_uni not in RECOVERY_UNIVERSES:
        return {"transition_type": "MOVED_TO_RECOVERY", "transition_reason": f"Driver moved to recovery ({c_uni}) after {c_inact} days without trips.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}

    # MOVED_UP_BAND / MOVED_DOWN_BAND
    if p_uni == "ACTIVE_GROWTH_90_PLUS_BAND_UP" and c_uni == "ACTIVE_GROWTH_90_PLUS_BAND_UP":
        pi = _band_index(p_band)
        ci = _band_index(c_band)
        if ci > pi:
            return {"transition_type": "MOVED_UP_BAND", "transition_reason": f"Driver moved up from band {p_band} to {c_band}.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}
        if ci < pi:
            return {"transition_type": "MOVED_DOWN_BAND", "transition_reason": f"Driver moved down from band {p_band} to {c_band}.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}

    # NO_LONGER_EXPORTABLE / BECAME_EXPORTABLE
    p_exp = (prev or {}).get("export_to_control_loop")
    c_exp = (curr or {}).get("export_to_control_loop")
    if p_exp and not c_exp:
        return {"transition_type": "NO_LONGER_EXPORTABLE", "transition_reason": "Driver is no longer in the exportable Control Loop list.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}
    if not p_exp and c_exp:
        return {"transition_type": "BECAME_EXPORTABLE", "transition_reason": "Driver became eligible for Control Loop export.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}

    # STAYED_IN_LIST
    if p_uni == c_uni:
        return {"transition_type": "STAYED_IN_LIST", "transition_reason": "Driver stayed in the same operational list.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}

    return {"transition_type": "EXITED_TO_ACTIVE", "transition_reason": f"Driver moved from {p_uni} to {c_uni}.", "goal_met_flag": False, "recovered_flag": False, "inactivity_days_before_return": None}


def refresh_exclusive_worklist_transition_daily(
    generated_date: Optional[str] = None,
    previous_generated_date: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    params = _get_connection_params()
    params["options"] = "-c statement_timeout=300000"

    if generated_date is None:
        c = psycopg2.connect(**params)
        cur = c.cursor()
        cur.execute(f"SELECT MAX(generated_date) FROM {TABLE_WORKLIST}")
        generated_date = str(cur.fetchone()[0])
        cur.close(); c.close()
    target_d = date.fromisoformat(generated_date[:10])

    if previous_generated_date is None:
        c = psycopg2.connect(**params)
        cur = c.cursor()
        cur.execute(f"SELECT MAX(generated_date) FROM {TABLE_WORKLIST} WHERE generated_date < %s", (target_d,))
        r = cur.fetchone()
        previous_generated_date = str(r[0]) if r and r[0] else None
        cur.close(); c.close()
    prev_d = date.fromisoformat(previous_generated_date[:10]) if previous_generated_date else None

    conn = psycopg2.connect(**params)
    conn.autocommit = False
    if not dry_run and not _acquire_lock(conn):
        conn.close()
        return {"ok": False, "status": "SKIPPED_LOCKED", "reason": "Another transition refresh in progress"}

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"SELECT * FROM {TABLE_WORKLIST} WHERE generated_date = %s", (target_d,))
        current_rows = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        prev_rows = {}
        if prev_d:
            cur.execute(f"SELECT * FROM {TABLE_WORKLIST} WHERE generated_date = %s", (prev_d,))
            prev_rows = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        cur.close()

        # Build transitions
        all_dids = set(current_rows.keys()) | set(prev_rows.keys())
        rows: List[Dict] = []
        type_counts: Dict[str, int] = {}

        for did in sorted(all_dids):
            prev = prev_rows.get(did)
            curr = current_rows.get(did)
            t = _classify_transition(prev, curr)

            if prev and prev.get("evidence_json") and isinstance(prev["evidence_json"], str):
                try: import json; prev["evidence_json"] = json.loads(prev["evidence_json"])
                except: pass
            if curr and curr.get("evidence_json") and isinstance(curr["evidence_json"], str):
                try: import json; curr["evidence_json"] = json.loads(curr["evidence_json"])
                except: pass

            tev = {
                "generated_date": str(target_d),
                "previous_generated_date": str(prev_d) if prev_d else None,
                "driver_profile_id": did,
                "previous_universe": (prev or {}).get("assigned_universe_v1"),
                "current_universe": (curr or {}).get("assigned_universe_v1"),
                "previous_weekly_trips": (prev or {}).get("weekly_trips") or 0,
                "current_weekly_trips": (curr or {}).get("weekly_trips") or 0,
                "previous_activation_window_trips": (prev or {}).get("activation_window_trips") or 0,
                "current_activation_window_trips": (curr or {}).get("activation_window_trips") or 0,
                "previous_inactivity_days": (prev or {}).get("inactivity_days") or 0,
                "current_inactivity_days": (curr or {}).get("inactivity_days") or 0,
                "previous_gap_to_target": (prev or {}).get("gap_to_target"),
                "current_gap_to_target": (curr or {}).get("gap_to_target"),
                "transition_type": t["transition_type"],
                "goal_met_flag": t["goal_met_flag"],
                "recovered_flag": t["recovered_flag"],
                "recovered_threshold_days": 45,
                "source_table": TABLE_WORKLIST,
                "source_version": "exclusive_lists_v1",
            }

            row = {
                "generated_date": target_d,
                "previous_generated_date": prev_d,
                "driver_profile_id": did,
                "driver_id": (curr or prev or {}).get("driver_id"),
                "previous_assigned_universe_v1": (prev or {}).get("assigned_universe_v1"),
                "previous_productivity_band": (prev or {}).get("productivity_band"),
                "previous_export_to_control_loop": (prev or {}).get("export_to_control_loop"),
                "previous_weekly_trips": (prev or {}).get("weekly_trips"),
                "previous_activation_window_trips": (prev or {}).get("activation_window_trips"),
                "previous_inactivity_days": (prev or {}).get("inactivity_days"),
                "previous_gap_to_target": (prev or {}).get("gap_to_target"),
                "current_assigned_universe_v1": (curr or {}).get("assigned_universe_v1"),
                "current_productivity_band": (curr or {}).get("productivity_band"),
                "current_export_to_control_loop": (curr or {}).get("export_to_control_loop"),
                "current_weekly_trips": (curr or {}).get("weekly_trips"),
                "current_activation_window_trips": (curr or {}).get("activation_window_trips"),
                "current_inactivity_days": (curr or {}).get("inactivity_days"),
                "current_gap_to_target": (curr or {}).get("gap_to_target"),
                "transition_type": t["transition_type"],
                "transition_reason": t["transition_reason"],
                "goal_met_flag": t["goal_met_flag"],
                "recovered_flag": t["recovered_flag"],
                "recovered_threshold_days": t.get("recovered_threshold_days") or 45,
                "inactivity_days_before_return": t.get("inactivity_days_before_return"),
                "previous_evidence_json": (prev or {}).get("evidence_json"),
                "current_evidence_json": (curr or {}).get("evidence_json"),
                "transition_evidence_json": tev,
            }
            rows.append(row)
            type_counts[t["transition_type"]] = type_counts.get(t["transition_type"], 0) + 1

        if dry_run:
            conn.rollback()
            _release_lock(conn)
            conn.close()
            return {
                "dry_run": True,
                "generated_date": str(target_d),
                "previous_generated_date": str(prev_d) if prev_d else None,
                "candidate_rows": len(rows),
                "by_transition_type": type_counts,
            }

        # UPSERT
        from psycopg2.extras import execute_values
        import json as _json

        cur2 = conn.cursor()
        cols = [
            "generated_date", "previous_generated_date", "driver_profile_id", "driver_id",
            "previous_assigned_universe_v1", "previous_productivity_band", "previous_export_to_control_loop",
            "previous_weekly_trips", "previous_activation_window_trips", "previous_inactivity_days", "previous_gap_to_target",
            "current_assigned_universe_v1", "current_productivity_band", "current_export_to_control_loop",
            "current_weekly_trips", "current_activation_window_trips", "current_inactivity_days", "current_gap_to_target",
            "transition_type", "transition_reason", "goal_met_flag", "recovered_flag",
            "recovered_threshold_days", "inactivity_days_before_return",
            "previous_evidence_json", "current_evidence_json", "transition_evidence_json",
        ]
        vals = [
            (
                r["generated_date"], r["previous_generated_date"], r["driver_profile_id"], r["driver_id"],
                r["previous_assigned_universe_v1"], r["previous_productivity_band"], r["previous_export_to_control_loop"],
                r["previous_weekly_trips"], r["previous_activation_window_trips"], r["previous_inactivity_days"], r["previous_gap_to_target"],
                r["current_assigned_universe_v1"], r["current_productivity_band"], r["current_export_to_control_loop"],
                r["current_weekly_trips"], r["current_activation_window_trips"], r["current_inactivity_days"], r["current_gap_to_target"],
                r["transition_type"], r["transition_reason"], r["goal_met_flag"], r["recovered_flag"],
                r["recovered_threshold_days"], r["inactivity_days_before_return"],
                _json.dumps(r["previous_evidence_json"]) if r["previous_evidence_json"] else None,
                _json.dumps(r["current_evidence_json"]) if r["current_evidence_json"] else None,
                _json.dumps(r["transition_evidence_json"]),
            )
            for r in rows
        ]
        col_list = ", ".join(cols)
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in ("generated_date", "driver_profile_id")) + ", updated_at = now()"

        execute_values(cur2, f"INSERT INTO {TABLE_OUT} ({col_list}) VALUES %s ON CONFLICT (generated_date, driver_profile_id) DO UPDATE SET {set_clause}", vals, page_size=5000)
        cur2.close()
        conn.commit()

        return {
            "dry_run": False,
            "generated_date": str(target_d),
            "previous_generated_date": str(prev_d) if prev_d else None,
            "candidate_rows": len(rows),
            "inserted_or_updated": len(rows),
            "by_transition_type": type_counts,
            "goal_met_count": sum(1 for r in rows if r["goal_met_flag"]),
            "recovered_count": sum(1 for r in rows if r["recovered_flag"]),
            "ok": True,
            "status": "SUCCESS",
        }

    except Exception as e:
        conn.rollback()
        logger.error("Transition refresh failed: %s", e)
        return {"ok": False, "status": "FAILED", "error": str(e)[:500]}
    finally:
        _release_lock(conn)
        try: conn.close()
        except: pass
