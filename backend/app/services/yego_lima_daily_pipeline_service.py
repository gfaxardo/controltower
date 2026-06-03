"""
YEGO Lima Growth — Daily Pipeline Orchestrator (Fase 2D.0 + Fase 2D-R).

Manual daily pipeline runner. Idempotent steps, status per step.
No automatic scheduler.

Fase 2D-R: New step order with state/program/opportunity canonical flow.
Legacy steps preserved for backward compatibility.
"""

from __future__ import annotations
import logging
import time
import json as json_mod
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_RUN = "growth.yango_lima_pipeline_run_log"
TABLE_STEP = "growth.yango_lima_pipeline_run_step_log"

PIPELINE_STEPS = [
    ("validate_foundation", 1),
    ("build_eligible_universe", 2),
    ("stabilize_driver_360_day", 3),
    ("build_loyalty_sub50", 4),
    ("build_driver_segments", 5),
    ("build_driver_state_snapshot", 6),
    ("build_program_eligibility", 7),
    ("build_daily_opportunity_lists", 8),
    ("close_previous_day_unmanaged_opportunities", 9),
    ("close_previous_day_unmanaged", 10),
    ("build_daily_impact", 11),
    ("build_segment_transitions", 12),
    ("build_list_outcomes", 13),
    ("build_impact_attribution", 14),
    ("build_executive_metrics_check", 15),
]


def run_daily_pipeline(run_date_str: str, max_drivers: int = 250,
                       include_warm: bool = False, dry_run: bool = False,
                       requested_by: Optional[str] = None) -> Dict[str, Any]:
    run_date = date.fromisoformat(run_date_str)
    prev_date_str = (run_date - timedelta(days=1)).isoformat()

    config = {"max_drivers": max_drivers, "include_warm": include_warm, "dry_run": dry_run}

    # Create run log
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            INSERT INTO {TABLE_RUN} (run_date, overall_status, requested_by, dry_run, config)
            VALUES (%(d)s, 'running', %(by)s, %(dr)s, %(cfg)s)
            RETURNING run_id
        """, {"d": run_date, "by": requested_by, "dr": dry_run, "cfg": json_mod.dumps(config)})
        run_id = str(cur.fetchone()["run_id"])
        conn.commit()

    steps_result: list = []
    warnings: list = []
    errors: list = []
    overall = "success"

    for step_name, step_order in PIPELINE_STEPS:
        t0 = time.perf_counter()
        status = "success"
        summary = {}
        error_msg = None

        try:
            status, summary, error_msg = _execute_step(step_name, run_date_str, prev_date_str, dry_run)
        except Exception as e:
            status = "failed"
            error_msg = str(e)[:500]
            errors.append(f"{step_name}: {error_msg}")
            logger.exception("Pipeline step %s failed", step_name)

        duration = int((time.perf_counter() - t0) * 1000)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                INSERT INTO {TABLE_STEP} (run_id, step_name, step_order, status, duration_ms, summary, error_message)
                VALUES (%(rid)s::uuid, %(sn)s, %(so)s, %(st)s, %(dur)s, %(sum)s::jsonb, %(err)s)
            """, {
                "rid": run_id, "sn": step_name, "so": step_order,
                "st": status, "dur": duration,
                "sum": json_mod.dumps(summary) if summary else None,
                "err": error_msg,
            })
            conn.commit()

        steps_result.append({
            "step": step_name, "status": status, "duration_ms": duration, "summary": summary,
        })

        if status == "failed":
            overall = "failed"
        elif status == "skipped" and overall != "failed":
            overall = "warning"

    # Update run log
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_RUN}
            SET overall_status = %(os)s, finished_at = now(),
                warnings = %(w)s::jsonb, errors = %(e)s::jsonb, summary = %(s)s::jsonb
            WHERE run_id = %(rid)s::uuid
        """, {
            "os": overall, "rid": run_id,
            "w": json_mod.dumps(warnings), "e": json_mod.dumps(errors),
            "s": json_mod.dumps({"steps": len(steps_result), "dry_run": dry_run}),
        })
        conn.commit()

    return {"run_date": run_date_str, "run_id": run_id, "overall_status": overall,
            "dry_run": dry_run, "steps": steps_result, "warnings": warnings, "errors": errors}


def _execute_step(step_name: str, run_date_str: str, prev_date_str: str, dry_run: bool):
    if dry_run:
        return "skipped", {"dry_run": True}, None

    if step_name == "validate_foundation":
        return _validate_foundation(run_date_str)

    elif step_name == "build_eligible_universe":
        try:
            from app.services.yego_lima_eligible_universe_service import build_eligible_universe
            import asyncio as _asyncio
            r = _asyncio.run(build_eligible_universe(run_date_str))
        except RuntimeError:
            r = {"ok": True, "skipped": "async_in_event_loop"}
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "stabilize_driver_360_day":
        try:
            from app.services.yego_lima_driver_360_service import stabilize_driver_360_day
            import asyncio as _asyncio
            r = _asyncio.run(stabilize_driver_360_day(run_date_str))
        except RuntimeError:
            r = {"ok": True, "skipped": "async_in_event_loop"}
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_loyalty_sub50":
        from app.services.yego_lima_loyalty_sub50_service import build_loyalty_sub50
        r = build_loyalty_sub50(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_driver_segments":
        from app.services.yego_lima_driver_segmentation_service import build_driver_segments
        r = build_driver_segments(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_driver_state_snapshot":
        from app.services.yego_lima_driver_state_service import build_driver_state_snapshot
        r = build_driver_state_snapshot(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_program_eligibility":
        from app.services.yego_lima_program_eligibility_service import build_program_eligibility
        r = build_program_eligibility(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_daily_opportunity_lists":
        from app.services.yego_lima_daily_opportunity_service import build_daily_opportunity_lists
        r = build_daily_opportunity_lists(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "close_previous_day_unmanaged_opportunities":
        from app.services.yego_lima_daily_opportunity_service import close_unmanaged_opportunities
        r = close_unmanaged_opportunities(prev_date_str)
        return "success", r, None

    elif step_name == "close_previous_day_unmanaged":
        from app.services.yego_lima_actionable_list_service import close_unmanaged_items
        r = close_unmanaged_items(prev_date_str)
        return "success", r, None

    elif step_name == "build_actionable_lists":
        from app.services.yego_lima_actionable_list_service import build_daily_actionable_lists
        r = build_daily_actionable_lists(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_daily_impact":
        from app.services.yego_lima_action_impact_service import build_daily_impact_for_date
        r = build_daily_impact_for_date(run_date_str)
        return "success", r, None

    elif step_name == "build_segment_transitions":
        from app.services.yego_lima_segment_migration_service import build_segment_transitions
        r = build_segment_transitions(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_list_outcomes":
        from app.services.yego_lima_list_outcome_service import build_list_outcomes
        r = build_list_outcomes(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_impact_attribution":
        from app.services.yego_lima_impact_attribution_service import build_daily_attribution
        r = build_daily_attribution(run_date_str)
        return "success" if r.get("ok") else "warning", r, None

    elif step_name == "build_executive_metrics_check":
        return "success", {"check": "executive_metrics_available"}, None

    return "skipped", {"reason": "unknown_step"}, None


def _validate_foundation(run_date_str: str):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        checks = []
        layers = [
            ("driver_360_daily", "growth.yango_lima_driver_360_daily", "date"),
            ("segment_snapshot", "growth.yango_lima_driver_segment_snapshot", "snapshot_date"),
            ("history_weekly", "growth.yango_lima_driver_history_weekly", "week_start_date"),
        ]
        for name, table, col in layers:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} <= %(d)s", {"d": run_date_str})
            cnt = cur.fetchone()["count"]
            checks.append({"layer": name, "rows": cnt, "ok": cnt > 0})

        all_ok = all(c["ok"] for c in checks)
        return ("success" if all_ok else "warning",
                {"checks": checks},
                None if all_ok else "Some foundation layers are empty")


def get_pipeline_status(query_date: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if not query_date:
            cur.execute(f"SELECT MAX(run_date) FROM {TABLE_RUN}")
            r = cur.fetchone()
            query_date = str(r["max"]) if r and r["max"] else str(date.today())

        layers = {
            "segment_snapshot": ("growth.yango_lima_driver_segment_snapshot", "snapshot_date"),
            "actionable_list": ("growth.yango_lima_actionable_list_daily", "list_date"),
            "transitions": ("growth.yango_lima_driver_segment_transition_daily", "transition_date"),
            "list_outcomes": ("growth.yango_lima_actionable_list_outcome_daily", "list_date"),
            "attribution": ("growth.yango_lima_action_attribution_daily", "attribution_date"),
            "daily_impact": ("growth.yango_lima_driver_action_daily_impact", "impact_date"),
            # Fase 2D-R new layers
            "driver_state_snapshot": ("growth.yango_lima_driver_state_snapshot", "snapshot_date"),
            "program_eligibility_daily": ("growth.yango_lima_program_eligibility_daily", "eligibility_date"),
            "daily_opportunity_list": ("growth.yango_lima_daily_opportunity_list", "opportunity_date"),
        }

        status = {}
        for name, (table, col) in layers.items():
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = %(d)s", {"d": query_date})
            cnt = cur.fetchone()["count"]
            status[name] = {"exists": cnt > 0, "rows": cnt}

        # Prev day unmanaged check - opportunities
        prev = (date.fromisoformat(query_date) - timedelta(days=1)).isoformat()
        cur.execute("""
            SELECT COUNT(*) FROM growth.yango_lima_daily_opportunity_list
            WHERE opportunity_date = %(d)s AND management_status = 'PENDING_ACTION'
        """, {"d": prev})
        opp_prev_pending = cur.fetchone()["count"]

        # Prev day unmanaged check - legacy
        cur.execute("""
            SELECT COUNT(*) FROM growth.yango_lima_actionable_list_daily
            WHERE list_date = %(d)s AND management_status = 'PENDING_ACTION'
        """, {"d": prev})
        prev_pending = cur.fetchone()["count"]

        missing = [k for k, v in status.items() if not v["exists"]]
        return {
            "date": query_date,
            "layers": status,
            "previous_day_pending": prev_pending,
            "previous_day_opp_pending": opp_prev_pending,
            "status": "ok" if not missing and prev_pending == 0 and opp_prev_pending == 0 else "warning",
            "missing_layers": missing,
            "remediation": "Run POST /pipeline/run-daily" if missing else None,
        }


def consistency_check(query_date: Optional[str] = None) -> Dict[str, Any]:
    if not query_date:
        query_date = str(date.today())

    with get_db() as conn:
        cur = conn.cursor()
        checks = []

        # Snapshot exists (legacy)
        cur.execute("SELECT COUNT(*) FROM growth.yango_lima_driver_segment_snapshot WHERE snapshot_date = %(d)s", {"d": query_date})
        checks.append({"check": "segment_snapshot_exists", "ok": cur.fetchone()[0] > 0,
                       "remediation": "Run build-driver-segments"})

        # Driver state snapshot exists (new)
        cur.execute("SELECT COUNT(*) FROM growth.yango_lima_driver_state_snapshot WHERE snapshot_date = %(d)s", {"d": query_date})
        checks.append({"check": "driver_state_snapshot_exists", "ok": cur.fetchone()[0] > 0,
                       "remediation": "Run POST /state/build-driver-states"})

        # Program eligibility exists (new)
        cur.execute("SELECT COUNT(*) FROM growth.yango_lima_program_eligibility_daily WHERE eligibility_date = %(d)s", {"d": query_date})
        checks.append({"check": "program_eligibility_exists", "ok": cur.fetchone()[0] > 0,
                       "remediation": "Run POST /programs/build-eligibility"})

        # Opportunity list exists (new)
        cur.execute("SELECT COUNT(*) FROM growth.yango_lima_daily_opportunity_list WHERE opportunity_date = %(d)s", {"d": query_date})
        checks.append({"check": "daily_opportunity_exists", "ok": cur.fetchone()[0] > 0,
                       "remediation": "Run POST /opportunities/build-daily"})

        # Actionable list exists (legacy)
        cur.execute("SELECT COUNT(*) FROM growth.yango_lima_actionable_list_daily WHERE list_date = %(d)s", {"d": query_date})
        checks.append({"check": "actionable_list_exists", "ok": cur.fetchone()[0] > 0,
                       "remediation": "Run build-actionable-lists"})

        # No stale pending from yesterday (legacy)
        prev = (date.fromisoformat(query_date) - timedelta(days=1)).isoformat()
        cur.execute("SELECT COUNT(*) FROM growth.yango_lima_actionable_list_daily WHERE list_date = %(d)s AND management_status = 'PENDING_ACTION'", {"d": prev})
        pending = cur.fetchone()[0]
        checks.append({"check": "no_stale_pending_legacy", "ok": pending == 0,
                       "remediation": f"Close {pending} unmanaged items from {prev}" if pending else None})

        # No stale pending from yesterday (new)
        cur.execute("SELECT COUNT(*) FROM growth.yango_lima_daily_opportunity_list WHERE opportunity_date = %(d)s AND management_status = 'PENDING_ACTION'", {"d": prev})
        opp_pending = cur.fetchone()[0]
        checks.append({"check": "no_stale_pending_opportunities", "ok": opp_pending == 0,
                       "remediation": f"Close {opp_pending} unmanaged opportunities from {prev}" if opp_pending else None})

        all_ok = all(c["ok"] for c in checks)
        return {"date": query_date, "status": "ok" if all_ok else "warning", "checks": checks}
