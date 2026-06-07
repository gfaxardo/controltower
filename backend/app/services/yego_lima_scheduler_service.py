"""
YEGO Lima Growth — Scheduler Service (LG-INFRA-R1.2)

Dual-mode scheduler:
A) DAILY CLOSED PIPELINE — once per day, after data close, builds all operational layers
B) LIVE 5-MIN MONITORING — maintains API freshness, monitors results, NO rebuild
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE = "growth.yego_lima_scheduler_status"
SCHEDULER_NAME = "lima_growth_refresh"


def _now():
    return datetime.now(timezone.utc)


def get_scheduler_status() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM {TABLE} WHERE scheduler_name = %(n)s",
            {"n": SCHEDULER_NAME}
        )
        row = cur.fetchone()
        if not row:
            return {"scheduler_name": SCHEDULER_NAME, "enabled": False,
                    "status": "NOT_INITIALIZED", "message": "Scheduler not found"}

        return {
            "scheduler_name": row[0],
            "enabled": row[1],
            "interval_minutes": row[2],
            "last_tick_at": row[3].isoformat() if row[3] else None,
            "next_tick_at": row[4].isoformat() if row[4] else None,
            "last_run_id": row[5],
            "last_status": row[6],
            "last_error": row[7],
            "tick_count": row[8],
            "success_count": row[9],
            "fail_count": row[10],
            "status": "RUNNING" if row[1] else "STOPPED",
        }


def start_scheduler() -> Dict[str, Any]:
    next_tick = _now() + timedelta(minutes=5)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {TABLE} SET enabled = true, next_tick_at = %(nt)s, updated_at = now() "
            f"WHERE scheduler_name = %(n)s",
            {"nt": next_tick, "n": SCHEDULER_NAME}
        )
        conn.commit()
    return {"started": True, "scheduler_name": SCHEDULER_NAME,
            "next_tick_at": next_tick.isoformat(), "interval_minutes": 5}


def stop_scheduler() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {TABLE} SET enabled = false, updated_at = now() "
            f"WHERE scheduler_name = %(n)s",
            {"n": SCHEDULER_NAME}
        )
        conn.commit()
    return {"stopped": True, "scheduler_name": SCHEDULER_NAME}


def scheduler_tick() -> Dict[str, Any]:
    """Execute one tick: detect new data, run refresh if needed."""
    now = _now()

    # Check if enabled
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT enabled, last_tick_at, tick_count FROM {TABLE} WHERE scheduler_name = %(n)s",
            {"n": SCHEDULER_NAME}
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return {"tick": False, "reason": "Scheduler is stopped or not initialized",
                    "action": "POST /yego-lima-growth/scheduler/start"}

    # Detect latest available source date
    from app.services.yego_lima_daily_refresh_service import detect_latest_closed_data_date
    date_info = detect_latest_closed_data_date()
    op_date = date_info.get("operational_data_date")

    if not op_date:
        # Record tick
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {TABLE} SET last_tick_at = %(now)s, tick_count = tick_count + 1, "
                f"last_status = 'NO_DATA', updated_at = now() WHERE scheduler_name = %(n)s",
                {"now": now, "n": SCHEDULER_NAME}
            )
            conn.commit()
        return {"tick": True, "ran_refresh": False, "operational_date": None,
                "reason": "No operational data available. Pipeline must be run manually first."}

    # Check if refresh is needed (last refresh older than interval)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(finished_at) FROM growth.yego_lima_refresh_run_log "
            "WHERE operational_data_date = %(d)s AND status = 'SUCCESS'",
            {"d": op_date}
        )
        last_success = cur.fetchone()[0]

    # Run refresh
    need_refresh = True
    if last_success:
        age = (now - last_success).total_seconds() / 60
        if age < 5:  # Already refreshed within 5 min
            need_refresh = False

    result = {"tick": True, "ran_refresh": False, "operational_date": op_date}

    if need_refresh:
        try:
            from app.services.yego_lima_daily_refresh_service import run_daily_refresh
            refresh = run_daily_refresh(target_date=op_date)
            result["ran_refresh"] = True
            result["refresh_success"] = refresh.get("success", False)
            result["refresh_status"] = refresh.get("status")
            last_status = refresh.get("status", "UNKNOWN")
            last_run_id = refresh.get("run_id")
            error = None if refresh.get("success") else str(refresh.get("warnings", []))[:200]
        except Exception as e:
            result["ran_refresh"] = True
            result["refresh_success"] = False
            result["error"] = str(e)[:200]
            last_status = "FAILED"
            last_run_id = None
            error = str(e)[:200]
    else:
        last_status = "SKIPPED"
        last_run_id = None
        error = None

    # Update scheduler state
    next_tick = now + timedelta(minutes=5)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {TABLE} SET last_tick_at = %(now)s, next_tick_at = %(nt)s, "
            f"tick_count = tick_count + 1, "
            f"last_run_id = %(rid)s, last_status = %(st)s, last_error = %(err)s, "
            f"success_count = success_count + CASE WHEN %(st)s = 'SUCCESS' THEN 1 ELSE 0 END, "
            f"fail_count = fail_count + CASE WHEN %(st)s = 'FAILED' THEN 1 ELSE 0 END, "
            f"updated_at = now() WHERE scheduler_name = %(n)s",
            {"now": now, "nt": next_tick, "rid": last_run_id, "st": last_status,
             "err": error, "n": SCHEDULER_NAME}
        )
        conn.commit()

    result["next_tick_at"] = next_tick.isoformat()
    return result


# ── DUAL-MODE FUNCTIONS (LG-INFRA-R1.2) ──

def run_daily_closed_pipeline(date: str = None) -> Dict[str, Any]:
    """
    A) DAILY CLOSED PIPELINE — once per day, after data close.
    Builds all operational layers from Yango API source data.
    Does NOT modify exported records. Does NOT export campaigns.
    """
    from app.services.yego_lima_daily_refresh_service import detect_latest_closed_data_date

    if not date:
        date_info = detect_latest_closed_data_date()
        date = date_info.get("operational_data_date")

    if not date:
        return {"mode": "daily_closed_pipeline", "success": False,
                "error": "No operational data date available",
                "remediation": "Run Yango API ingestion first"}

    now = _now()
    result = {"mode": "daily_closed_pipeline", "date": date, "started_at": now.isoformat()}

    try:
        from app.services.yego_lima_daily_refresh_service import run_daily_refresh
        refresh = run_daily_refresh(target_date=date)
        result["success"] = refresh.get("success", False)
        result["status"] = refresh.get("status", "UNKNOWN")
        result["steps"] = refresh.get("steps", [])
        result["run_id"] = refresh.get("run_id")
        result["finished_at"] = _now().isoformat()

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {TABLE} SET last_run_id = %(rid)s, last_status = %(st)s, "
                f"updated_at = now() WHERE scheduler_name = %(n)s",
                {"rid": refresh.get("run_id"), "st": refresh.get("status", "UNKNOWN"),
                 "n": SCHEDULER_NAME}
            )
            conn.commit()
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)[:200]
        result["finished_at"] = _now().isoformat()

    return result


def run_live_monitoring() -> Dict[str, Any]:
    """
    B) LIVE 5-MIN MONITORING — maintains API freshness, monitors results.
    NO eligibility rebuild. NO prioritization rebuild. NO queue rebuild.
    NO campaign export. NO Action Engine.
    """
    now = _now()
    result = {
        "mode": "live_monitoring_tick",
        "tick_at": now.isoformat(),
        "refresh_api": False,
        "refresh_mvs": False,
        "update_signals": False,
        "update_governance": True,
    }

    try:
        from app.services.yego_lima_daily_refresh_service import detect_latest_closed_data_date
        from app.services.yego_lima_refresh_governance_service import get_governance_status
        from app.services.yego_lima_serving_facts_service import generate_all_serving_facts

        date_info = detect_latest_closed_data_date()
        op_date = date_info.get("operational_data_date")
        result["operational_date"] = op_date

        if op_date:
            # Check if the closed date changed (new day available)
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT MAX(operational_data_date) FROM growth.yego_lima_refresh_run_log "
                    "WHERE status = 'SUCCESS'"
                )
                last_processed = cur.fetchone()[0]
                last_processed_str = str(last_processed) if last_processed else None

            if last_processed_str != op_date:
                result["new_day_detected"] = True
                result["action"] = "daily_closed_pipeline_needed"
                result["remediation"] = "Run POST /scheduler/run-daily-closed or wait for auto-detection"
            else:
                result["new_day_detected"] = False

            # Refresh serving facts for governance (lightweight)
            gov = get_governance_status()
            result["governance"] = {
                "operability": gov.get("operability"),
                "freshness_status": gov.get("freshness_status"),
                "days_behind": gov.get("days_behind"),
            }
    except Exception as e:
        result["error"] = str(e)[:200]

    with get_db() as conn:
        cur = conn.cursor()
        next_tick = now + timedelta(minutes=5)
        cur.execute(
            f"UPDATE {TABLE} SET last_tick_at = %(now)s, next_tick_at = %(nt)s, "
            f"tick_count = tick_count + 1, last_status = 'LIVE_MONITORING', "
            f"updated_at = now() WHERE scheduler_name = %(n)s",
            {"now": now, "nt": next_tick, "n": SCHEDULER_NAME}
        )
        conn.commit()

    result["next_tick_at"] = next_tick.isoformat()
    return result
