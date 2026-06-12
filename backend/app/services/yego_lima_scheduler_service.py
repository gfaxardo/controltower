"""
YEGO Lima Growth — Scheduler Service (LG-INFRA-R1.2 / LG-CF-HOTFIX-1B / LG-REL-1A)

Dual-mode scheduler:
A) DAILY CLOSED PIPELINE — once per day, after data close, builds all operational layers
B) LIVE 5-MIN MONITORING — maintains API freshness, monitors results, NO rebuild
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE = "growth.yego_lima_scheduler_status"
TABLE_TICK_LOG = "growth.yego_lima_scheduler_tick_log"
SCHEDULER_NAME = "lima_growth_refresh"

TICK_LOCK_ID = 9001
MAX_DB_RETRIES = 3
DB_RETRY_DELAY_SECONDS = 2


def _now():
    return datetime.now(timezone.utc)


def _ensure_scheduler_row(conn):
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {TABLE} (scheduler_name, enabled, interval_minutes, last_tick_at, "
        f"next_tick_at, last_run_id, last_status, last_error, tick_count, "
        f"success_count, fail_count, updated_at) "
        f"VALUES (%(n)s, true, 5, NULL, NULL, NULL, NULL, NULL, 0, 0, 0, now()) "
        f"ON CONFLICT (scheduler_name) DO NOTHING",
        {"n": SCHEDULER_NAME}
    )


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
    Autonomous tick for APScheduler. Every 5 min.

    Detects new raw data → runs daily cascade → syncs control_loop.
    If no new data → lightweight governance + signals + history snapshot.

    Always writes to refresh_run_log (triggered_by='autonomous_tick') and tick_log.
    LG-CTRL-HOTFIX-1E: Full rollover capability + never fail silently.
    """
    now = _now()
    import uuid
    tick_id = f"tick-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    result = {
        "mode": "autonomous_tick",
        "tick_id": tick_id,
        "tick_at": now.isoformat(),
        "governance_checked": False,
        "catch_up_needed": False,
        "cascade_executed": False,
        "control_loop_synced": False,
        "serving_facts_generated": False,
    }

    op_date = None
    refresh_run_id = None
    refresh_status = None

    with get_db() as conn:
        _ensure_scheduler_row(conn)
        conn.commit()

    conn = get_db().__enter__()
    if not _try_acquire_tick_lock(conn):
        result["status"] = "SKIPPED_OVERLAP"
        result["reason"] = "Previous tick still running"
        _write_tick_log_always(now, now, 0, result)
        return result

    try:
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
            _write_tick_log_always(now, _now(), 0, result)
            return result

        from app.services.yego_lima_daily_refresh_service import detect_latest_closed_data_date

        try:
            from app.services.yango_raw_tick_ingestion_service import ingest_recent_orders
            raw_ingest = ingest_recent_orders()
            result["raw_ingest"] = {
                "attempted": raw_ingest.get("attempted"),
                "dates_attempted": raw_ingest.get("dates_attempted", []),
                "dates_inserted": raw_ingest.get("dates_inserted", []),
                "total_inserted": raw_ingest.get("total_inserted", 0),
                "total_skipped": raw_ingest.get("total_skipped", 0),
                "api_empty_dates": raw_ingest.get("api_empty_dates", []),
                "api_errors": raw_ingest.get("api_errors", []),
                "duration_seconds": raw_ingest.get("duration_seconds"),
            }
            if raw_ingest.get("error"):
                result["raw_ingest"]["error"] = raw_ingest["error"]
        except Exception as e:
            result["raw_ingest"] = {"attempted": True, "error": str(e)[:200]}
            logger.warning("Autonomous tick: raw ingestion failed — %s", e)

        date_info = detect_latest_closed_data_date()
        op_date = date_info.get("operational_data_date")
        result["operational_date"] = op_date

        max_raw_date = None
        max_snapshot_date = None
        try:
            cur = conn.cursor()
            cur.execute("SELECT MAX(order_ended_at)::date FROM raw_yango.orders_raw")
            row = cur.fetchone()
            max_raw_date = str(row[0]) if row and row[0] else None
            cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
            row = cur.fetchone()
            max_snapshot_date = str(row[0]) if row and row[0] else None
            result["raw_max_date"] = max_raw_date
            result["snapshot_max_date_before"] = max_snapshot_date
        except Exception:
            pass

        cascade_required = False
        target_dates = []
        if max_raw_date and max_snapshot_date and max_raw_date > max_snapshot_date:
            from datetime import date as date_type
            raw_dt = date_type.fromisoformat(max_raw_date)
            snap_dt = date_type.fromisoformat(max_snapshot_date)
            cascade_required = True
            d = snap_dt + timedelta(days=1)
            while d <= raw_dt:
                target_dates.append(d.strftime("%Y-%m-%d"))
                d += timedelta(days=1)
            if len(target_dates) > 3:
                target_dates = target_dates[-3:]
            result["cascade_reason"] = "RAW_AHEAD_OF_SNAPSHOT"
            result["cascade_required"] = True
            result["target_dates"] = target_dates
            logger.info("Autonomous tick: raw ahead of snapshot (raw=%s snap=%s). Cascade required for %s.",
                        max_raw_date, max_snapshot_date, target_dates)

        run_refresh = False
        if cascade_required:
            pipeline_steps = []
            pipeline_failed = False
            for target_date in target_dates:
                if pipeline_failed:
                    break

                def _run_step(name, fn):
                    nonlocal pipeline_failed
                    t0 = _now()
                    try:
                        r = fn()
                        elapsed = int((_now() - t0).total_seconds() * 1000)
                        step = {"step": name, "status": "SUCCESS", "duration_ms": elapsed,
                                "date": target_date}
                        if isinstance(r, dict):
                            step["result"] = {k: v for k, v in r.items()
                                              if k in ('drivers_processed', 'rows_inserted', 'rows_updated',
                                                       'programs_found', 'opportunities_created',
                                                       'prioritized_count', 'actionable_today',
                                                       'created_count', 'ready_count', 'held_count')}
                        pipeline_steps.append(step)
                        return r
                    except Exception as e:
                        elapsed = int((_now() - t0).total_seconds() * 1000)
                        err = str(e)[:200]
                        pipeline_steps.append({"step": name, "status": "FAILED",
                                               "duration_ms": elapsed, "date": target_date,
                                               "error": err})
                        pipeline_failed = True
                        logger.error("Pipeline step %s failed for %s: %s", name, target_date, err)
                        return None

                from app.services.yego_lima_driver_state_service import build_driver_state_snapshot
                _run_step("driver_state", lambda d=target_date: build_driver_state_snapshot(d))

                from app.services.yego_lima_program_eligibility_service import build_program_eligibility
                _run_step("eligibility", lambda d=target_date: build_program_eligibility(d))

                from app.services.yego_lima_daily_opportunity_service import build_daily_opportunity_lists
                _run_step("opportunity_lists", lambda d=target_date: build_daily_opportunity_lists(d))

                from app.services.yego_lima_opportunity_policy_service import build_prioritized_opportunities
                _run_step("prioritized", lambda d=target_date: build_prioritized_opportunities(d, max_drivers=500))

                from app.services.yego_lima_daily_refresh_service import run_daily_refresh
                refresh = run_daily_refresh(target_date=target_date, triggered_by="autonomous_tick")

            result["cascade_executed"] = True
            result["pipeline_steps"] = pipeline_steps
            result["refresh_success"] = not pipeline_failed
            result["refresh_status"] = "SUCCESS" if not pipeline_failed else "PARTIAL_CASCADE_FAILED"
            result["target_dates"] = target_dates
            refresh_status = "SUCCESS" if not pipeline_failed else "FAILED"
            refresh_run_id = None

            if not pipeline_failed:
                for target_date in target_dates:
                    try:
                        from app.services.yego_lima_control_loop_sync_service import sync_assignment_queue_to_control_loop
                        cl_result = sync_assignment_queue_to_control_loop(target_date)
                        result["control_loop_synced"] = True
                        result["control_loop_target_date"] = target_date
                        result["control_loop_inserted"] = cl_result.get("inserted", 0)
                        result["control_loop_skipped"] = cl_result.get("skipped", 0)
                        pipeline_steps.append({"step": "control_loop_sync", "status": "SUCCESS",
                                               "date": target_date,
                                               "inserted": cl_result.get("inserted", 0),
                                               "skipped": cl_result.get("skipped", 0)})
                    except Exception as e:
                        pipeline_steps.append({"step": "control_loop_sync", "status": "FAILED",
                                               "date": target_date, "error": str(e)[:100]})
                        logger.warning("Pipeline control_loop_sync failed for %s: %s", target_date, e)

            try:
                cur = conn.cursor()
                cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
                row = cur.fetchone()
                result["snapshot_max_date_after"] = str(row[0]) if row and row[0] else None
            except Exception:
                pass

        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(operational_data_date) FROM growth.yego_lima_refresh_run_log "
            "WHERE status = 'SUCCESS'"
        )
        last_processed = cur.fetchone()[0]
        last_processed_str = str(last_processed) if last_processed else None

        if not op_date and not cascade_required:
            result["status"] = "NOOP_NO_DATA"
            result["reason"] = "No operational data available"
            _release_tick_lock(conn)
            _log_autonomous_run(tick_id, op_date, "NOOP_NO_DATA", result, now)
            _update_scheduler(now, "NOOP_NO_DATA", None, None)
            _write_tick_log_always(now, _now(), 0, result)
            return result

        if not cascade_required and last_processed_str != op_date:
            result["catch_up_needed"] = True
            result["last_processed"] = last_processed_str
            result["latest_available"] = op_date
            run_refresh = True
            logger.info("Autonomous tick: new day detected %s (last processed: %s)", op_date, last_processed_str)
        elif not cascade_required:
            refresh_status = "NOOP_CAUGHT_UP"
            refresh_run_id = None

        if run_refresh and not cascade_required:
            try:
                from app.services.yego_lima_daily_refresh_service import run_daily_refresh
                refresh = run_daily_refresh(target_date=op_date, triggered_by="autonomous_tick")
                result["cascade_executed"] = True
                result["refresh_success"] = refresh.get("success", False)
                result["refresh_status"] = refresh.get("status", "UNKNOWN")
                result["refresh_run_id"] = refresh.get("run_id")
                result["refresh_steps"] = refresh.get("steps", [])
                refresh_status = "SUCCESS" if refresh.get("success") else "FAILED"
                refresh_run_id = refresh.get("run_id")
            except Exception as e:
                result["cascade_executed"] = True
                result["refresh_success"] = False
                result["refresh_error"] = str(e)[:200]
                refresh_status = "FAILED"
                refresh_run_id = None
                logger.error("Autonomous tick: daily refresh failed — %s", e)
        else:
            refresh_status = "NOOP_CAUGHT_UP"
            refresh_run_id = None

        try:
            from app.services.yego_lima_control_loop_sync_service import sync_assignment_queue_to_control_loop
            cl_sync = sync_assignment_queue_to_control_loop(op_date)
            result["control_loop_synced"] = True
            result["control_loop_inserted"] = cl_sync.get("inserted", 0)
            result["control_loop_skipped"] = cl_sync.get("skipped", 0)
        except Exception as e:
            result["control_loop_error"] = str(e)[:100]
            logger.warning("Autonomous tick: control_loop sync failed — %s", e)

        try:
            from app.services.yego_lima_serving_facts_service import generate_all_serving_facts
            facts = generate_all_serving_facts(op_date)
            result["serving_facts_generated"] = True
            result["serving_facts_count"] = facts.get("generated_count", 0) if isinstance(facts, dict) else 0
        except Exception as e:
            result["serving_facts_error"] = str(e)[:100]

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
            signals = build_intraday_signals(op_date)
            result["signals"] = {
                "count": signals.get("signal_count", 0),
                "new": signals.get("new_signals", 0),
            }
        except Exception as e:
            result["signals_error"] = str(e)[:100]

        try:
            from app.services.yego_lima_driver_list_history_service import snapshot_queue_to_history
            hist = snapshot_queue_to_history(op_date)
            result["history_snapshot"] = hist.get("rows_snapshotted", 0)
        except Exception as e:
            result["history_error"] = str(e)[:100]

        if not run_refresh and result.get("refresh_success") is not False:
            result["status"] = "SUCCESS_NO_CASCADE"
        elif result.get("refresh_success") is False:
            result["status"] = "PARTIAL_CASCADE_FAILED"
        else:
            result["status"] = "SUCCESS"

    except Exception as e:
        result["status"] = "FAILED"
        result["error"] = str(e)[:200]
        refresh_status = "FAILED"
        refresh_run_id = None
        logger.error("Autonomous tick exception: %s", e)

    finally:
        _release_tick_lock(conn)

    finished = _now()
    duration_ms = int((finished - now).total_seconds() * 1000)
    result["duration_ms"] = duration_ms

    _log_autonomous_run(tick_id, op_date,
                        result.get("status", "UNKNOWN"), result, now)

    next_tick = finished + timedelta(minutes=5)
    _update_scheduler(finished, result.get("status", "UNKNOWN"),
                      refresh_run_id, result.get("error"))

    _write_tick_log_always(now, finished, duration_ms, result)

    result["next_tick_at"] = next_tick.isoformat()
    return result


def _log_autonomous_run(tick_id: str, op_date, status: str, result: dict, now: datetime):
    try:
        import json, uuid
        run_uuid = str(uuid.uuid4())
        db_status = _normalize_run_log_status(status)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO growth.yego_lima_refresh_run_log "
                "(id, operational_data_date, status, started_at, finished_at, "
                " triggered_by, summary, warnings) "
                "VALUES (%(id)s, %(d)s, %(st)s, %(sa)s, %(fa)s, "
                " 'autonomous_tick', %(sum)s::jsonb, %(warn)s::jsonb)",
                {
                    "id": run_uuid,
                    "d": op_date,
                    "st": db_status,
                    "sa": now,
                    "fa": _now(),
                    "sum": json.dumps({
                        "tick_id": tick_id,
                        "run_uuid": run_uuid,
                        "raw_status": status,
                        "cascade_executed": result.get("cascade_executed", False),
                        "refresh_success": result.get("refresh_success"),
                        "control_loop_inserted": result.get("control_loop_inserted"),
                        "serving_facts_generated": result.get("serving_facts_generated"),
                        "raw_ingest": result.get("raw_ingest"),
                        "raw_max_date": result.get("raw_max_date"),
                        "snapshot_max_date_before": result.get("snapshot_max_date_before"),
                        "snapshot_max_date_after": result.get("snapshot_max_date_after"),
                        "cascade_reason": result.get("cascade_reason"),
                        "target_dates": result.get("target_dates"),
                        "pipeline_steps": result.get("pipeline_steps"),
                    }),
                    "warn": json.dumps(result.get("error")) if result.get("error") else json.dumps(None),
                }
            )
            conn.commit()
    except Exception as e:
        logger.warning("Failed to write autonomous run log: %s", e)


def _normalize_run_log_status(status):
    allowed = {"SUCCESS", "PARTIAL_SUCCESS", "FAILED", "PENDING", "RUNNING"}
    if status in allowed:
        return status
    mapping = {
        "SUCCESS_NO_CASCADE": "SUCCESS",
        "NOOP_NO_DATA": "SUCCESS",
        "NOOP_CAUGHT_UP": "SUCCESS",
        "PARTIAL_CASCADE_FAILED": "PARTIAL_SUCCESS",
        "SKIPPED_OVERLAP": "SUCCESS",
        "SKIPPED": "PENDING",
    }
    mapped = mapping.get(status, "SUCCESS")
    logger.info("Normalized run_log status: %s → %s", status, mapped)
    return mapped


def _normalize_tick_status(status):
    allowed = {"STARTED", "SUCCESS", "FAILED", "PARTIAL", "SKIPPED"}
    if status in allowed:
        return status
    mapping = {
        "SUCCESS_NO_CASCADE": "SUCCESS",
        "NOOP_NO_DATA": "SUCCESS",
        "NOOP_CAUGHT_UP": "SUCCESS",
        "PARTIAL_CASCADE_FAILED": "PARTIAL",
        "SKIPPED_OVERLAP": "SKIPPED",
    }
    mapped = mapping.get(status, "SUCCESS")
    logger.info("Normalized tick_status: %s → %s", status, mapped)
    return mapped


def _update_scheduler(now, status, run_id, error):
    try:
        next_tick = now + timedelta(minutes=5)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {TABLE} SET last_tick_at = %(now)s, next_tick_at = %(nt)s, "
                f"tick_count = tick_count + 1, last_run_id = %(rid)s, last_status = %(st)s, "
                f"last_error = %(err)s, "
                f"success_count = success_count + CASE WHEN %(st)s IN ('SUCCESS','SUCCESS_NO_CASCADE','NOOP_NO_DATA','NOOP_CAUGHT_UP') THEN 1 ELSE 0 END, "
                f"fail_count = fail_count + CASE WHEN %(st)s IN ('FAILED','PARTIAL_CASCADE_FAILED') THEN 1 ELSE 0 END, "
                f"updated_at = now() WHERE scheduler_name = %(n)s",
                {"now": now, "nt": next_tick, "rid": run_id, "st": status,
                 "err": error, "n": SCHEDULER_NAME}
            )
            conn.commit()
    except Exception as e:
        logger.warning("Failed to update scheduler: %s", e)


def _write_tick_log_always(started, finished, duration_ms, result, _unused_conn=None):
    try:
        import json
        with get_db() as conn:
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
                    "st": started,
                    "ft": finished,
                    "dur": duration_ms,
                    "ts": _normalize_tick_status(result.get("status", "UNKNOWN")),
                    "ca": bool(result.get("catch_up_needed", False)),
                    "cst": "GAP_DETECTED" if result.get("catch_up_needed") else "CAUGHT_UP",
                    "sb": result.get("signals", {}).get("count", 0),
                    "sn": result.get("signals", {}).get("new", 0),
                    "hsr": result.get("history_snapshot", 0),
                    "gc": result.get("governance_checked", False),
                    "go": result.get("governance", {}).get("operability") if result.get("governance") else None,
                    "od": result.get("operational_date"),
                    "nd": bool(result.get("catch_up_needed", False)),
                    "err": result.get("error", "")[:500] if result.get("error") else None,
                    "raw": json.dumps(result, default=str),
                }
            )
            conn.commit()
    except Exception as e:
        logger.warning("Failed to write tick log: %s", e)
