"""
YEGO Lima Growth — Daily Refresh Orchestrator (LG-UX-R2.9G.3)

Detects latest operational date, validates sources, runs pipeline steps,
logs run/step status. Wraps existing services. NO new engines.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_RUN = "growth.yego_lima_refresh_run_log"
TABLE_STEP = "growth.yego_lima_refresh_step_log"


def _now():
    return datetime.now(timezone.utc)


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


# ── DETECT OPERATIONAL DATE ──

def detect_latest_closed_data_date() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
        max_snapshot = cur.fetchone()[0]
        cur.execute("SELECT MAX(eligibility_date) FROM growth.yango_lima_program_eligibility_daily")
        max_eligibility = cur.fetchone()[0]
        cur.execute("SELECT MAX(opportunity_date) FROM growth.yango_lima_prioritized_opportunity_daily")
        max_opportunity = cur.fetchone()[0]

    operational_date = max_snapshot or max_eligibility or max_opportunity
    today = date.today()
    action_date = today.isoformat()

    return {
        "operational_data_date": str(operational_date) if operational_date else None,
        "today_action_date": action_date,
        "max_snapshot_date": str(max_snapshot) if max_snapshot else None,
        "max_eligibility_date": str(max_eligibility) if max_eligibility else None,
        "max_opportunity_date": str(max_opportunity) if max_opportunity else None,
        "is_fresh": operational_date and str(operational_date) == today.isoformat(),
    }


# ── VALIDATE SOURCE READINESS ──

def validate_source_readiness(target_date: str) -> Dict[str, Any]:
    checks = {}
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM growth.yango_lima_driver_state_snapshot WHERE snapshot_date = %(d)s", {"d": target_date})
        checks["driver_state_snapshot"] = _safe_int(cur.fetchone()[0]) > 0

        cur.execute("SELECT COUNT(*) as cnt FROM growth.yango_lima_program_eligibility_daily WHERE eligibility_date = %(d)s", {"d": target_date})
        checks["program_eligibility"] = _safe_int(cur.fetchone()[0]) > 0

        cur.execute("SELECT COUNT(*) as cnt FROM growth.yango_lima_prioritized_opportunity_daily WHERE opportunity_date = %(d)s", {"d": target_date})
        checks["prioritized_opportunity"] = _safe_int(cur.fetchone()[0]) > 0

    all_ready = all(checks.values())
    return {
        "ready": all_ready,
        "checks": checks,
        "missing": [k for k, v in checks.items() if not v],
        "remediation": "Run daily pipeline: POST /yego-lima-growth/pipeline/run-daily" if not all_ready else None,
    }


# ── RUN LOG ──

def _create_run(run_type: str, triggered_by: str, operational_date: str) -> str:
    run_id = str(uuid4())
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE_RUN} (id, run_type, triggered_by, operational_data_date, status) "
            f"VALUES (%(id)s, %(rt)s, %(tb)s, %(od)s, 'RUNNING')",
            {"id": run_id, "rt": run_type, "tb": triggered_by, "od": operational_date}
        )
        conn.commit()
    return run_id


def _finish_run(run_id: str, status: str, warnings: list = None, summary: dict = None):
    import json
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {TABLE_RUN} SET status = %(st)s, finished_at = now(), warnings = %(w)s, summary = %(s)s "
            f"WHERE id = %(id)s",
            {"st": status, "w": json.dumps(warnings) if warnings else None,
             "s": json.dumps(summary) if summary else None, "id": run_id}
        )
        conn.commit()


def _log_step(run_id: str, step_name: str, status: str, rows_in: int = None,
              rows_out: int = None, error: str = None, remediation: str = None):
    import json
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE_STEP} (run_id, step_name, status, started_at, finished_at, "
            f" rows_in, rows_out, error_message, remediation) "
            f"VALUES (%(rid)s, %(sn)s, %(st)s, now(), now(), %(ri)s, %(ro)s, %(err)s, %(rem)s)",
            {"rid": run_id, "sn": step_name, "st": status, "ri": rows_in,
             "ro": rows_out, "err": error, "rem": remediation}
        )
        conn.commit()


# ── ORCHESTRATOR ──

def run_daily_refresh(target_date: Optional[str] = None,
                      triggered_by: str = "system",
                      dry_run: bool = False) -> Dict[str, Any]:
    date_info = detect_latest_closed_data_date()
    operational_date = target_date or date_info.get("operational_data_date")
    if not operational_date:
        return {"success": False, "error": "No operational data date detected. Run bootstrap first.",
                "remediation": "Ejecutar bootstrap: POST /yego-lima-growth/pipeline/run-daily"}

    if dry_run:
        readiness = validate_source_readiness(operational_date)
        return {
            "success": True,
            "dry_run": True,
            "operational_data_date": operational_date,
            "today_action_date": date_info["today_action_date"],
            "readiness": readiness,
            "steps_available": [
                "pipeline_run_daily",
                "opportunity_policy_build",
                "assignment_queue_build",
            ],
        }

    run_id = _create_run("manual", triggered_by, operational_date)
    warnings = []
    steps_executed = []

    def run_step(name, fn):
        try:
            t0 = datetime.now(timezone.utc)
            result = fn()
            elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
            _log_step(run_id, name, "SUCCESS")
            steps_executed.append({"step": name, "status": "SUCCESS", "elapsed_s": round(elapsed, 1)})
            return result
        except Exception as e:
            error_msg = str(e)[:300]
            _log_step(run_id, name, "FAILED", error=error_msg)
            steps_executed.append({"step": name, "status": "FAILED", "error": error_msg})
            warnings.append(f"{name}: {error_msg}")
            return None

    # Step 1: Detect date
    _log_step(run_id, "detect_operational_date", "SUCCESS",
              remediation=f"Operational date: {operational_date}")

    # Step 2: Validate source
    readiness = validate_source_readiness(operational_date)
    if not readiness["ready"]:
        _log_step(run_id, "validate_source_readiness", "FAILED",
                  remediation=readiness["remediation"])
        _finish_run(run_id, "FAILED", warnings, {"steps": steps_executed})
        return {
            "success": False, "run_id": run_id,
            "error": "Source data not ready",
            "missing": readiness["missing"],
            "remediation": readiness["remediation"],
        }

    _log_step(run_id, "validate_source_readiness", "SUCCESS")

    # Step 3: Build assignment queue if needed
    try:
        from app.services.yego_lima_assignment_queue_service import create_assignment_batch
        result = create_assignment_batch(operational_date)
        _log_step(run_id, "build_assignment_queue", "SUCCESS",
                  rows_out=result.get("created_count", 0))
        steps_executed.append({
            "step": "build_assignment_queue", "status": "SUCCESS",
            "created": result.get("created_count", 0),
            "ready": result.get("ready_count", 0),
            "held": result.get("held_count", 0),
        })
    except Exception as e:
        _log_step(run_id, "build_assignment_queue", "FAILED", error=str(e)[:300])
        warnings.append(f"build_assignment_queue: {str(e)[:200]}")

    # Step 4: Run opportunity policy (prioritized opportunities)
    try:
        from app.services.yego_lima_opportunity_policy_service import build_prioritized_opportunities
        policy = build_prioritized_opportunities(operational_date)
        actionable = sum(
            1 for r in policy.get("result", []) if isinstance(r, dict) and r.get("is_actionable_today")
        ) if policy else 0
        _log_step(run_id, "build_prioritized_opportunities", "SUCCESS",
                  rows_out=actionable)
        steps_executed.append({"step": "build_prioritized_opportunities", "status": "SUCCESS"})
    except Exception as e:
        _log_step(run_id, "build_prioritized_opportunities", "FAILED", error=str(e)[:300])
        warnings.append(f"build_prioritized_opportunities: {str(e)[:200]}")

    # Step 5: Generate serving facts
    try:
        from app.services.yego_lima_serving_facts_service import generate_all_serving_facts
        from app.services.freshness_service import compute_freshness
        from app.db.connection import get_db
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
            ts = cur.fetchone()[0]
        fs = compute_freshness("driver_snapshot", ts, "...")
        fact_results = generate_all_serving_facts(operational_date, run_id, fs.get("status"))
        _log_step(run_id, "generate_serving_facts", "SUCCESS",
                  remediation=f"Facts saved: {fact_results}")
        steps_executed.append({"step": "generate_serving_facts", "status": "SUCCESS", "facts": fact_results})
    except Exception as e:
        _log_step(run_id, "generate_serving_facts", "FAILED", error=str(e)[:300])
        warnings.append(f"generate_serving_facts: {str(e)[:200]}")

    final_status = "SUCCESS" if len(warnings) == 0 else "PARTIAL_SUCCESS"
    _finish_run(run_id, final_status, warnings, {"steps": steps_executed})

    return {
        "success": final_status != "FAILED",
        "run_id": run_id,
        "operational_data_date": operational_date,
        "today_action_date": date_info["today_action_date"],
        "status": final_status,
        "steps": steps_executed,
        "warnings": warnings,
        "remediation": "Datos operativos disponibles. Today Action Plan usara operational_data_date." if final_status == "SUCCESS" else None,
    }


# ── STATUS ──

def get_refresh_status() -> Dict[str, Any]:
    date_info = detect_latest_closed_data_date()
    op_date = date_info.get("operational_data_date")

    if not op_date:
        return {"status": "NO_DATA", "message": "No operational data found. Run bootstrap.",
                "remediation": "POST /yego-lima-growth/pipeline/run-daily"}

    readiness = validate_source_readiness(op_date)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT * FROM {TABLE_RUN} WHERE operational_data_date = %(d)s OR operational_data_date IS NULL "
            f"ORDER BY started_at DESC LIMIT 5",
            {"d": op_date}
        )
        recent_runs = [dict(r) for r in cur.fetchall()]
        for r in recent_runs:
            r["id"] = str(r["id"])
            if r.get("started_at"): r["started_at"] = r["started_at"].isoformat()
            if r.get("finished_at"): r["finished_at"] = r["finished_at"].isoformat()

    from app.services.freshness_service import compute_freshness
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
        ts = cur.fetchone()[0]
    freshness = compute_freshness("driver_snapshot", ts, "driver_state_snapshot")

    return {
        "status": "READY" if readiness["ready"] else "STALE",
        "operational_data_date": op_date,
        "today_action_date": date_info["today_action_date"],
        "readiness": readiness,
        "freshness": freshness,
        "is_fresh": date_info.get("is_fresh", False),
        "recent_runs": recent_runs,
        "remediation": None if readiness["ready"] else readiness["remediation"],
    }


def get_refresh_history(limit: int = 20) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT * FROM {TABLE_RUN} ORDER BY started_at DESC LIMIT %(lim)s",
            {"lim": limit}
        )
        runs = []
        for r in cur.fetchall():
            rd = dict(r)
            rd["id"] = str(rd["id"])
            if rd.get("started_at"): rd["started_at"] = rd["started_at"].isoformat()
            if rd.get("finished_at"): rd["finished_at"] = rd["finished_at"].isoformat()
            runs.append(rd)
    return {"runs": runs, "count": len(runs)}
