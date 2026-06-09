"""
OV2-CLOSE.2C.1 — Omniview Cascade Service
Wraps the canonical waterfall cascade as an importable, lock-protected service.
Supports: manual, scheduler, startup_self_heal trigger sources.

Cascade layers:
  RAW → DRIVER_BRIDGE → DAY_FACT → WEEK_FACT → MONTH_FACT → SNAPSHOT

Idempotent. Uses refresh_guard() for concurrency control.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import os
import time
from datetime import date as dt_date, timedelta
from typing import Any, Dict, Optional

from app.services.refresh_control_service import (
    refresh_guard,
    start_refresh_run,
    finish_refresh_run,
    fail_refresh_run,
)
from app.db.connection import get_db

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logger = logging.getLogger(__name__)

CASCADE_REFRESH_NAME = "omniview_cascade"
CASCADE_PIPELINE_NAME = "omniview_cascade_pipeline"


def _get_python() -> str:
    """Return the Python interpreter path."""
    return sys.executable


def _run_script_step(script: str, args: list[str], timeout: int = 300) -> dict[str, Any]:
    """Run a Python script via subprocess with timeout."""
    script_path = os.path.join(BACKEND_DIR, script.replace(".", os.sep)) + ".py"
    if not os.path.exists(script_path):
        return {"name": script, "ok": False, "ms": 0, "output": f"Script not found: {script_path}", "returncode": -1}
    cmd = [_get_python(), script_path] + args
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = round((time.time() - t0) * 1000)
        ok = result.returncode == 0
        output = (result.stdout or "")[-500:] + (result.stderr or "")[-500:]
        return {"name": script, "ok": ok, "ms": elapsed, "output": output, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        elapsed = round((time.time() - t0) * 1000)
        return {"name": script, "ok": False, "ms": elapsed, "output": f"TIMEOUT after {timeout}s", "returncode": -1}
    except Exception as e:
        elapsed = round((time.time() - t0) * 1000)
        return {"name": script, "ok": False, "ms": elapsed, "output": str(e)[:500], "returncode": -1}


def _get_today() -> dt_date:
    return dt_date.today()


def run_cascade(
    trigger_source: str = "manual",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute the full waterfall cascade.

    Args:
        trigger_source: "manual" | "scheduler" | "startup_self_heal"
        dry_run: If True, measure before/after without executing rebuilds

    Returns:
        Dict with results per layer and overall status.
    """
    today = _get_today()
    d1 = (today - timedelta(days=1)).isoformat()
    d2 = (today - timedelta(days=2)).isoformat()

    layers = [
        {
            "name": "driver_bridge",
            "pipeline": "bridge_update",
            "script": "scripts/build_driver_bridge_direct",
            "args": ["--date-from", d2, "--date-to", d1, "--batch-days", "1", "--confirm"],
            "timeout": 180,
            "table": "ops.driver_day_slice_fact",
            "col": "activity_date",
            "filter": "WHERE country='peru' AND city='lima'",
        },
        {
            "name": "day_fact",
            "pipeline": "day_rebuild",
            "script": "scripts/rebuild_day_from_bridge",
            "args": ["--date-from", d2, "--date-to", d1, "--confirm"],
            "timeout": 120,
            "table": "ops.real_business_slice_day_fact",
            "col": "trip_date",
            "filter": "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
        },
        {
            "name": "week_fact",
            "pipeline": "week_rebuild",
            "script": "scripts/rebuild_week_from_day_and_bridge",
            "args": ["--date-from", "2026-04-01", "--date-to", d1, "--confirm"],
            "timeout": 300,
            "table": "ops.real_business_slice_week_fact",
            "col": "week_start",
            "filter": "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
        },
        {
            "name": "month_fact",
            "pipeline": "month_rebuild",
            "script": "scripts/rebuild_month_from_day_and_bridge",
            "args": ["--date-from", "2026-06-01", "--date-to", d1, "--confirm"],
            "timeout": 120,
            "table": "ops.real_business_slice_month_fact",
            "col": "month",
            "filter": "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'",
        },
        {
            "name": "snapshot",
            "pipeline": "snapshot_refresh",
            "script": "scripts/refresh_omniview_v2_snapshots",
            "args": ["--confirm"],
            "timeout": 120,
            "table": "ops.omniview_v2_serving_snapshot",
            "col": "operating_date",
            "filter": "WHERE status='READY'",
        },
    ]

    results = []
    advanced_count = 0

    for layer in layers:
        before_max = None
        before_rows = 0
        try:
            with get_db() as conn:
                cur = conn.cursor()
                try:
                    cur.execute(f"SELECT MAX({layer['col']}) FROM {layer['table']} {layer['filter']}")
                    row = cur.fetchone()
                    before_max = str(row[0])[:10] if row and row[0] else None
                    cur.execute(f"SELECT COUNT(*) FROM {layer['table']} {layer['filter']}")
                    before_rows = int(cur.fetchone()[0] or 0)
                finally:
                    cur.close()
        except Exception as e:
            results.append({"layer": layer["name"], "status": "FAIL", "error": f"preflight: {str(e)[:100]}"})
            continue

        if dry_run:
            results.append({
                "layer": layer["name"], "status": "DRY_RUN",
                "before": before_max, "after": before_max,
                "rows_before": before_rows, "rows_after": before_rows,
            })
            logger.info("CASCADE DRY-RUN layer=%s before=%s rows=%s", layer["name"], before_max, before_rows)
            continue

        logger.info("CASCADE EXEC layer=%s before=%s rows=%s", layer["name"], before_max, before_rows)
        step = _run_script_step(layer["script"], layer["args"], timeout=layer["timeout"])

        after_max = None
        after_rows = 0
        try:
            with get_db() as conn:
                cur = conn.cursor()
                try:
                    cur.execute(f"SELECT MAX({layer['col']}) FROM {layer['table']} {layer['filter']}")
                    row = cur.fetchone()
                    after_max = str(row[0])[:10] if row and row[0] else None
                    cur.execute(f"SELECT COUNT(*) FROM {layer['table']} {layer['filter']}")
                    after_rows = int(cur.fetchone()[0] or 0)
                finally:
                    cur.close()
        except Exception as e:
            logger.warning("CASCADE post-flight error layer=%s: %s", layer["name"], e)

        advanced = after_max and before_max != after_max
        status = "SUCCESS_WITH_ADVANCEMENT" if advanced else ("SUCCESS_NO_CHANGE" if step["ok"] else "FAIL")

        # Log to advancement log
        try:
            from datetime import datetime as dt_datetime, timezone as dt_timezone
            now_utc = dt_datetime.now(dt_timezone.utc).isoformat()
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO ops.refresh_advancement_log
                        (pipeline_name, layer_name, started_at, finished_at,
                         before_max_period, after_max_period, before_row_count, after_row_count,
                         advanced_periods, advanced_rows, status, error_message)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    layer["pipeline"], layer["name"],
                    now_utc, now_utc,
                    before_max, after_max, before_rows, after_rows,
                    1 if advanced else 0, (after_rows or 0) - (before_rows or 0),
                    status, step.get("output")[:1000] if not step["ok"] else None,
                ))
                conn.commit()
                cur.close()
        except Exception as e:
            logger.warning("CASCADE advancement_log error layer=%s: %s", layer["name"], e)

        logger.info(
            "CASCADE layer=%s status=%s before=%s after=%s rows=%s->%s ms=%s",
            layer["name"], status, before_max, after_max, before_rows, after_rows, step.get("ms", "?"),
        )

        results.append({
            "layer": layer["name"], "status": status,
            "before": before_max, "after": after_max,
            "rows_before": before_rows, "rows_after": after_rows,
            "ms": step.get("ms", 0), "ok": step["ok"],
        })

        if advanced:
            advanced_count += 1

        if not step["ok"]:
            logger.warning(
                "CASCADE layer=%s FAILED (continuing to next layer). output=%s",
                layer["name"], step.get("output", "")[:200],
            )

    total = len(results)
    overall = "ok" if advanced_count > 0 else ("dry_run" if dry_run else "no_advancement")

    return {
        "overall": overall,
        "trigger_source": trigger_source,
        "advanced_layers": advanced_count,
        "total_layers": total,
        "results": results,
        "date": today.isoformat(),
    }


def check_freshness_stale() -> Dict[str, Any]:
    """
    Lightweight freshness check. Returns stale status per layer.
    Does NOT run any cascade.
    """
    from datetime import date as dt_date
    today = dt_date.today()

    checks = [
        ("driver_bridge", "ops.driver_day_slice_fact", "activity_date",
         "WHERE country='peru' AND city='lima'"),
        ("day_fact", "ops.real_business_slice_day_fact", "trip_date",
         "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"),
        ("week_fact", "ops.real_business_slice_week_fact", "week_start",
         "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"),
        ("month_fact", "ops.real_business_slice_month_fact", "month",
         "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"),
        ("snapshot", "ops.omniview_v2_serving_snapshot", "operating_date",
         "WHERE status='READY'"),
    ]

    layers = {}
    any_stale = False

    try:
        with get_db() as conn:
            cur = conn.cursor()
            for name, table, col, filter_clause in checks:
                try:
                    cur.execute(f"SELECT MAX({col}) FROM {table} {filter_clause}")
                    row = cur.fetchone()
                    max_date = str(row[0])[:10] if row and row[0] else None
                    gap = None
                    if max_date:
                        try:
                            gap = (today - dt_date.fromisoformat(max_date)).days
                        except Exception:
                            pass
                    # Stale if gap > 2 days or no data
                    stale = gap is None or gap > 2
                    if stale:
                        any_stale = True
                    layers[name] = {
                        "max_date": max_date,
                        "freshness_gap_days": gap,
                        "stale": stale,
                    }
                    cur.execute(f"SELECT COUNT(*) FROM {table} {filter_clause}")
                    layers[name]["rows"] = int(cur.fetchone()[0] or 0)
                except Exception as e:
                    layers[name] = {"error": str(e)[:200], "stale": True}
                    any_stale = True
            cur.close()
    except Exception as e:
        return {"error": str(e)[:200], "stale": True, "layers": {}}

    return {
        "stale": any_stale,
        "checked_at": today.isoformat(),
        "layers": layers,
    }


def run_startup_self_heal() -> Dict[str, Any]:
    """
    Check freshness at startup. If stale, trigger cascade in foreground.
    Called during app startup before scheduler starts.

    Returns:
        Dict with status: "triggered", "skipped_fresh", "skipped_locked", "error"
    """
    freshness = check_freshness_stale()

    if freshness.get("error"):
        logger.warning("STARTUP_SELF_HEAL freshness check failed: %s", freshness.get("error"))
        return {
            "action": "error",
            "reason": "freshness_check_failed",
            "freshness": freshness,
        }

    if not freshness.get("stale"):
        logger.info("STARTUP_SELF_HEAL all layers fresh — no cascade needed")
        return {
            "action": "skipped_fresh",
            "reason": "all_layers_fresh",
            "freshness": freshness,
        }

    stale_layers = [k for k, v in freshness.get("layers", {}).items() if v.get("stale")]
    logger.info("STARTUP_SELF_HEAL stale detected: %s — triggering cascade", stale_layers)

    # Try cascade with lock
    result = run_cascade_with_lock(trigger_source="startup_self_heal")

    if result.get("skipped"):
        logger.info("STARTUP_SELF_HEAL cascade skipped — lock held by another process")
        return {
            "action": "skipped_locked",
            "reason": "lock_held",
            "freshness": freshness,
            "stale_layers": stale_layers,
        }

    return {
        "action": "triggered",
        "reason": f"stale_layers={stale_layers}",
        "freshness": freshness,
        "cascade_result": result,
    }


def run_cascade_with_lock(
    trigger_source: str = "manual",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Run cascade protected by refresh_guard advisory lock.
    Prevents concurrent cascade executions.
    """
    with refresh_guard(
        refresh_name=CASCADE_REFRESH_NAME,
        pipeline_name=CASCADE_PIPELINE_NAME,
        trigger_source=trigger_source,
        grain="all",
        period_status="mixed",
    ) as guard:
        if guard.skipped:
            return {
                "ok": True,
                "skipped": True,
                "reason": "lock_held_by_another_process",
                "trigger_source": trigger_source,
            }

        try:
            result = run_cascade(trigger_source=trigger_source, dry_run=dry_run)
            guard._warning = None if result.get("overall") == "ok" else "no_advancement"
            return {
                "ok": True,
                "skipped": False,
                "cascade": result,
            }
        except Exception as e:
            logger.exception("CASCADE failed: %s", e)
            return {
                "ok": False,
                "skipped": False,
                "error": str(e)[:500],
                "trigger_source": trigger_source,
            }
