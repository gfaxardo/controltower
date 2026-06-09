"""
YEGO Lima Growth — Scheduler Service (LG-INFRA-R1.2 / LG-CF-HOTFIX-1B)

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
TABLE_TICK_LOG = "growth.yego_lima_scheduler_tick_log"
SCHEDULER_NAME = "lima_growth_refresh"

TICK_LOCK_ID = 9001


def _now():
    return datetime.now(timezone.utc)


def _try_acquire_tick_lock(conn) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT pg_try_advisory_lock(%(id)s)", {"id": TICK_LOCK_ID})
    return cur.fetchone()[0]


def _release_tick_lock(conn):
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_unlock(%(id)s)", {"id": TICK_LOCK_ID})
    except Exception:
        pass


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


# ── CATCH-UP LOGIC (LG-INFRA-R1.5) ──

def catch_up_on_startup() -> Dict[str, Any]:
    """
    Detects unprocessed dates since last successful pipeline run and
    executes daily closed pipeline for each missing date.

    Called:
    - On scheduler startup (first tick)
    - After backend restart
    - On explicit /scheduler/catch-up call

    Does NOT:
    - Export campaigns
    - Touch exported queues
    - Rebuild already-processed dates
    """
    now = _now()
    result = {
        "catch_up_attempted": True,
        "started_at": now.isoformat(),
        "dates_caught_up": [],
        "dates_failed": [],
        "status": "CATCHING_UP",
    }

    try:
        from app.services.yego_lima_daily_refresh_service import detect_latest_closed_data_date

        date_info = detect_latest_closed_data_date()
        latest_available = date_info.get("operational_data_date")
        result["latest_available_date"] = latest_available

        if not latest_available:
            result["status"] = "WAITING_FOR_CLOSED_DATA"
            result["message"] = "No operational data available yet"
            return result

        # Find last successfully processed date
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT operational_data_date FROM growth.yego_lima_refresh_run_log "
                "WHERE status = 'SUCCESS' ORDER BY operational_data_date DESC LIMIT 1"
            )
            row = cur.fetchone()
            last_processed = str(row[0]) if row and row[0] else None

        result["last_processed_date"] = last_processed

        if last_processed == latest_available:
            result["status"] = "CAUGHT_UP"
            result["message"] = f"Already caught up. Latest processed: {last_processed}"
            result["finished_at"] = _now().isoformat()
            return result

        # Find all dates between last processed and latest available that have snapshots
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT DISTINCT snapshot_date FROM growth.yango_lima_driver_state_snapshot "
                "WHERE snapshot_date > COALESCE(%(lp)s::date, '2026-01-01') "
                "AND snapshot_date <= %(la)s::date "
                "ORDER BY snapshot_date",
                {"lp": last_processed, "la": latest_available}
            )
            missing_dates = [str(r[0]) for r in cur.fetchall()]

        if not missing_dates:
            # Try eligible_universe or program_eligibility as fallback
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT DISTINCT eligibility_date FROM growth.yango_lima_program_eligibility_daily "
                    "WHERE eligibility_date > COALESCE(%(lp)s::date, '2026-01-01') "
                    "AND eligibility_date <= %(la)s::date "
                    "ORDER BY eligibility_date",
                    {"lp": last_processed, "la": latest_available}
                )
                missing_dates = [str(r[0]) for r in cur.fetchall()]

        result["missing_dates_detected"] = len(missing_dates)

        if not missing_dates:
            result["status"] = "CAUGHT_UP"
            result["message"] = "No unprocessed dates detected"
            result["finished_at"] = _now().isoformat()
            return result

        # Process each missing date
        from app.services.yego_lima_daily_refresh_service import run_daily_refresh

        for missing_date in missing_dates:
            try:
                refresh_result = run_daily_refresh(target_date=missing_date)
                if refresh_result.get("success"):
                    result["dates_caught_up"].append(missing_date)
                    logger.info("Catch-up: %s processed successfully", missing_date)
                else:
                    error_msg = refresh_result.get("error", "Unknown error")
                    result["dates_failed"].append({
                        "date": missing_date,
                        "error": error_msg,
                    })
                    logger.warning("Catch-up: %s FAILED - %s", missing_date, error_msg)
            except Exception as e:
                result["dates_failed"].append({
                    "date": missing_date,
                    "error": str(e)[:200],
                })
                logger.error("Catch-up: %s exception - %s", missing_date, e)

        if result["dates_failed"]:
            result["status"] = "CATCHUP_FAILED" if not result["dates_caught_up"] else "CAUGHT_UP"
        else:
            result["status"] = "CAUGHT_UP"

    except Exception as e:
        result["status"] = "CATCHUP_FAILED"
        result["error"] = str(e)[:300]
        logger.error("Catch-up failed: %s", e)

    result["finished_at"] = _now().isoformat()
    return result


# ── LIVE MONITORING (R1.5 hardened) ──

def run_live_monitoring() -> Dict[str, Any]:
    """
    B) LIVE 5-MIN MONITORING — maintains API freshness, monitors results.
    NO eligibility rebuild. NO prioritization rebuild. NO queue rebuild.
    NO campaign export. NO Action Engine.

    LG-INFRA-R1.3: Builds intraday signals for today's action_date.
    LG-INFRA-R1.5: Includes catch-up detection, history snapshot, hardened validation.
    """
    now = _now()
    result = {
        "mode": "live_monitoring_tick",
        "tick_at": now.isoformat(),
        "refresh_api": False,
        "refresh_mvs": False,
        "update_signals": True,
        "update_governance": True,
        "catch_up": None,
    }

    try:
        from app.services.yego_lima_daily_refresh_service import detect_latest_closed_data_date
        from app.services.yego_lima_refresh_governance_service import get_governance_status, _refresh_freshness_registry
        from app.services.yego_lima_serving_facts_service import generate_all_serving_facts

        date_info = detect_latest_closed_data_date()
        op_date = date_info.get("operational_data_date")
        result["operational_date"] = op_date

        if op_date:
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

                # LG-INFRA-R1.5: Auto catch-up if gap detected
                try:
                    catch_up = catch_up_on_startup()
                    result["catch_up"] = catch_up
                    if catch_up.get("status") == "CAUGHT_UP":
                        result["action"] = "catch_up_completed"
                except Exception as e:
                    result["catch_up"] = {"error": str(e)[:200]}
                    logger.warning("Auto catch-up attempt failed: %s", e)
            else:
                result["new_day_detected"] = False

            # Build intraday signals
            try:
                from app.services.yego_lima_intraday_signal_service import build_intraday_signals
                signals = build_intraday_signals(op_date)
                result["intraday_signals"] = {
                    "built": True,
                    "signal_count": signals.get("signal_count", 0),
                    "new_signals": signals.get("new_signals", 0),
                    "updated_signals": signals.get("updated_signals", 0),
                }
            except Exception as e:
                result["intraday_signals"] = {"built": False, "error": str(e)[:200]}
                logger.warning("Intraday signal build failed: %s", e)

            # Snapshot driver list to history (idempotent)
            try:
                from app.services.yego_lima_driver_list_history_service import snapshot_queue_to_history
                from app.services.yego_lima_opportunity_policy_service import get_active_policy
                policy = get_active_policy()
                hist = snapshot_queue_to_history(
                    op_date,
                    policy_id=policy.get("policy", {}).get("policy_id") if policy.get("active") else None,
                )
                result["history_snapshot"] = {"rows": hist.get("rows_snapshotted", 0)}
            except Exception as e:
                result["history_snapshot"] = {"error": str(e)[:200]}

            # Governance status
            _refresh_freshness_registry(op_date)
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

    # LG-INFRA-R1.6: Record tick log
    import json
    try:
        duration = int((_now() - now).total_seconds() * 1000)
        tick_status = "FAILED" if result.get("error") else ("SUCCESS" if not result.get("catch_up", {}).get("status") == "CATCHUP_FAILED" else "PARTIAL")
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE_TICK_LOG} "
                f"(started_at, finished_at, duration_ms, tick_status, "
                f" catch_up_attempted, catch_up_status, catch_up_dates_processed, "
                f" signals_built, signals_new, signals_updated, "
                f" history_snapshot_rows, governance_checked, governance_operability, "
                f" operational_date, new_day_detected, error_message, remediation, raw_result_json) "
                f"VALUES (%(st)s, %(ft)s, %(dur)s, %(ts)s, "
                f" %(ca)s, %(cst)s, %(cdp)s, "
                f" %(sb)s, %(sn)s, %(su)s, "
                f" %(hsr)s, %(gc)s, %(go)s, "
                f" %(od)s, %(nd)s, %(err)s, %(rem)s, %(raw)s::jsonb)",
                {
                    "st": now,
                    "ft": _now(),
                    "dur": duration,
                    "ts": tick_status,
                    "ca": result.get("catch_up") is not None,
                    "cst": result.get("catch_up", {}).get("status") if result.get("catch_up") else None,
                    "cdp": len(result.get("catch_up", {}).get("dates_caught_up", [])) if result.get("catch_up") else 0,
                    "sb": result.get("intraday_signals", {}).get("signal_count", 0),
                    "sn": result.get("intraday_signals", {}).get("new_signals", 0),
                    "su": result.get("intraday_signals", {}).get("updated_signals", 0),
                    "hsr": result.get("history_snapshot", {}).get("rows", 0),
                    "gc": result.get("governance") is not None,
                    "go": result.get("governance", {}).get("operability") if result.get("governance") else None,
                    "od": result.get("operational_date"),
                    "nd": result.get("new_day_detected", False),
                    "err": result.get("error", "")[:500] if result.get("error") else None,
                    "rem": result.get("remediation", "")[:500] if result.get("remediation") else None,
                    "raw": json.dumps(result, default=str),
                }
            )
            conn.commit()
    except Exception as e:
        logger.warning("Failed to record tick log: %s", e)

    result["next_tick_at"] = next_tick.isoformat()
    return result


# ── AUTONOMOUS TICK (LG-INFRA-R1.7) ──

def autonomous_tick() -> Dict[str, Any]:
    """
    Lightweight autonomous tick for APScheduler.
    Runs every 5 minutes without human intervention.

    Executes:
    - Governance check (lightweight)
    - Catch-up detection (gap audit only)
    - Intraday signals
    - History snapshot
    - Tick log recording

    Does NOT:
    - Rebuild lists
    - Call Yango API
    - Export campaigns
    - Block for more than a few seconds

    LG-CF-HOTFIX-1B: Advisory lock prevents overlapping ticks.
    If a previous tick is still running, this tick logs SKIPPED_OVERLAP and exits.
    """
    now = _now()
    result = {
        "mode": "autonomous_tick",
        "tick_at": now.isoformat(),
        "governance_checked": False,
        "catch_up_needed": False,
    }

    conn = get_db().__enter__()
    if not _try_acquire_tick_lock(conn):
        overlap_result = {
            "status": "SKIPPED_OVERLAP",
            "tick_at": now.isoformat(),
            "reason": "Previous tick still running. Tick skipped to prevent overlap.",
            "mode": "autonomous_tick",
        }
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO %s (started_at, finished_at, duration_ms, tick_status, "
                " operational_date, error_message, raw_result_json) "
                "VALUES (%%(st)s, %%(ft)s, 0, 'SKIPPED_OVERLAP', NULL, "
                " 'Previous tick still running', %%(raw)s::jsonb)" % TABLE_TICK_LOG,
                {"st": now, "ft": now, "raw": __import__('json').dumps(overlap_result, default=str)}
            )
            conn.commit()
        except Exception:
            pass
        return overlap_result

    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT enabled FROM {TABLE} WHERE scheduler_name = %(n)s",
                {"n": SCHEDULER_NAME}
            )
            row = cur.fetchone()
            if not row or not row[0]:
                result["status"] = "SKIPPED"
                result["reason"] = "Scheduler not enabled"
                _release_tick_lock(conn)
                return result

        from app.services.yego_lima_daily_refresh_service import detect_latest_closed_data_date
        date_info = detect_latest_closed_data_date()
        op_date = date_info.get("operational_data_date")
        result["operational_date"] = op_date

        if op_date:
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT MAX(operational_data_date) FROM growth.yego_lima_refresh_run_log "
                    "WHERE status = 'SUCCESS'"
                )
                last_processed = cur.fetchone()[0]
                last_processed_str = str(last_processed) if last_processed else None

            if last_processed_str != op_date:
                result["catch_up_needed"] = True
                result["last_processed"] = last_processed_str
                result["latest_available"] = op_date

        try:
            from app.services.yego_lima_refresh_governance_service import get_governance_status, _refresh_freshness_registry
            _refresh_freshness_registry(op_date)
            gov = get_governance_status()
            result["governance"] = {
                "operability": gov.get("operability"),
                "days_behind": gov.get("days_behind"),
            }
            result["governance_checked"] = True
        except Exception as e:
            result["governance_error"] = str(e)[:100]

        try:
            from app.services.yego_lima_intraday_signal_service import build_intraday_signals
            signals = build_intraday_signals(op_date) if op_date else {"signal_count": 0}
            result["signals"] = {
                "count": signals.get("signal_count", 0),
                "new": signals.get("new_signals", 0),
            }
        except Exception as e:
            result["signals_error"] = str(e)[:100]

        try:
            from app.services.yego_lima_driver_list_history_service import snapshot_queue_to_history
            hist = snapshot_queue_to_history(op_date) if op_date else {"rows_snapshotted": 0}
            result["history_snapshot"] = hist.get("rows_snapshotted", 0)
        except Exception as e:
            result["history_error"] = str(e)[:100]

        result["status"] = "SUCCESS"

    except Exception as e:
        result["status"] = "FAILED"
        result["error"] = str(e)[:200]
        logger.error("Autonomous tick failed: %s", e)

    finally:
        _release_tick_lock(conn)

    finished = _now()
    duration_ms = int((finished - now).total_seconds() * 1000)
    try:
        next_tick = finished + timedelta(minutes=5)
        with conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {TABLE} SET last_tick_at = %(now)s, next_tick_at = %(nt)s, "
                f"tick_count = tick_count + 1, last_status = %(st)s, "
                f"success_count = success_count + CASE WHEN %(st)s = 'SUCCESS' THEN 1 ELSE 0 END, "
                f"fail_count = fail_count + CASE WHEN %(st)s = 'FAILED' THEN 1 ELSE 0 END, "
                f"updated_at = now() WHERE scheduler_name = %(n)s",
                {"now": finished, "nt": next_tick, "st": result.get("status", "UNKNOWN"),
                 "n": SCHEDULER_NAME}
            )
            conn.commit()
    except Exception as e:
        logger.warning("Failed to update scheduler status: %s", e)

    import json
    try:
        with conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE_TICK_LOG} "
                f"(started_at, finished_at, duration_ms, tick_status, "
                f" catch_up_attempted, catch_up_status, "
                f" signals_built, signals_new, "
                f" history_snapshot_rows, governance_checked, governance_operability, "
                f" operational_date, new_day_detected, error_message, raw_result_json) "
                f"VALUES (%(st)s, %(ft)s, %(dur)s, %(ts)s, "
                f" %(ca)s, %(cst)s, "
                f" %(sb)s, %(sn)s, "
                f" %(hsr)s, %(gc)s, %(go)s, "
                f" %(od)s, %(nd)s, %(err)s, %(raw)s::jsonb)",
                {
                    "st": now,
                    "ft": finished,
                    "dur": duration_ms,
                    "ts": result.get("status", "UNKNOWN"),
                    "ca": result.get("catch_up_needed", False),
                    "cst": "GAP_DETECTED" if result.get("catch_up_needed") else "CAUGHT_UP",
                    "sb": result.get("signals", {}).get("count", 0),
                    "sn": result.get("signals", {}).get("new", 0),
                    "hsr": result.get("history_snapshot", 0),
                    "gc": result.get("governance_checked", False),
                    "go": result.get("governance", {}).get("operability") if result.get("governance") else None,
                    "od": result.get("operational_date"),
                    "nd": result.get("catch_up_needed", False),
                    "err": result.get("error", "")[:500] if result.get("error") else None,
                    "raw": json.dumps(result, default=str),
                }
            )
            conn.commit()
    except Exception as e:
        logger.warning("Failed to record tick log: %s", e)

    result["duration_ms"] = duration_ms
    result["next_tick_at"] = next_tick.isoformat()
    return result
