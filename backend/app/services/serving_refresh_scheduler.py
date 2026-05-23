"""
Serving Refresh Scheduler — FASE 1H.1
Scheduler con locking anti-concurrencia, retry y timeout para serving facts.
Se integra con APScheduler existente en app.main.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.services.serving_governance_service import (
    mark_refresh_start,
    mark_refresh_end,
    get_serving_health,
)

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REFRESH_SCRIPT = BACKEND_DIR / "scripts" / "refresh_omniview_projection_facts.py"
PYTHON = sys.executable

DEFAULT_GRAINS = ["daily", "weekly", "monthly"]
DEFAULT_PLAN_VERSION = "ruta27_2026_04_21"
REFRESH_TIMEOUT_SECONDS = 600  # 10 min max
MAX_RETRIES = 2

_lock = {}  # in-memory lock por serving_key


def _run_refresh(plan_version: str, grain: str, year: int = 2026) -> tuple[bool, int, str]:
    """Ejecuta el script de refresh como subprocess."""
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            [PYTHON, str(REFRESH_SCRIPT),
             "--plan-version", plan_version,
             "--grain", grain,
             "--year", str(year)],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=REFRESH_TIMEOUT_SECONDS,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)
        if result.returncode == 0:
            return True, duration_ms, ""
        else:
            err = result.stderr[:500] if result.stderr else f"exit code {result.returncode}"
            return False, duration_ms, err
    except subprocess.TimeoutExpired:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        return False, duration_ms, f"timeout after {REFRESH_TIMEOUT_SECONDS}s"
    except Exception as e:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        return False, duration_ms, str(e)[:500]


def refresh_grain(
    grain: str,
    plan_version: str = DEFAULT_PLAN_VERSION,
    year: int = 2026,
    triggered_by: str = "scheduler",
) -> dict:
    """Refresca un grain específico con locking y retry."""
    serving_key = f"omniview_projection_{grain}_{plan_version}"

    # Lock anti-concurrencia
    if _lock.get(serving_key):
        return {"status": "skipped", "reason": "already_running", "serving_key": serving_key}
    _lock[serving_key] = True

    try:
        refresh_id = mark_refresh_start(serving_key, triggered_by)
        success = False
        rows = 0
        duration_ms = 0
        error = ""

        for attempt in range(1 + MAX_RETRIES):
            success, duration_ms, error = _run_refresh(plan_version, grain, year)
            if success:
                break
            if attempt < MAX_RETRIES:
                logger.warning(
                    "refresh_grain retry %d/%d for %s: %s",
                    attempt + 1, MAX_RETRIES, serving_key, error[:100],
                )
                time.sleep(5)

        mark_refresh_end(serving_key, refresh_id, success, rows, duration_ms, error if not success else None)

        return {
            "status": "success" if success else "failed",
            "serving_key": serving_key,
            "refresh_id": refresh_id,
            "duration_ms": duration_ms,
            "attempts": attempt + 1,
            "error": error if not success else None,
        }
    finally:
        _lock.pop(serving_key, None)


def refresh_all_grains(plan_version: str = DEFAULT_PLAN_VERSION, year: int = 2026) -> list[dict]:
    """Refresca todos los grains secuencialmente."""
    results = []
    for grain in DEFAULT_GRAINS:
        r = refresh_grain(grain, plan_version, year)
        results.append(r)
    return results


def scheduled_daily_refresh():
    """Entry point para APScheduler — refresca todos los grains una vez al día."""
    logger.info("scheduled_daily_refresh: START")
    try:
        health = get_serving_health()
        if health.get("status") == "healthy" and health.get("stale_count", 0) == 0:
            logger.info("scheduled_daily_refresh: all fresh, skipping")
            return {"status": "skipped", "reason": "all_fresh"}

        results = refresh_all_grains()
        ok = sum(1 for r in results if r["status"] == "success")
        fail = sum(1 for r in results if r["status"] == "failed")
        logger.info("scheduled_daily_refresh: DONE ok=%d fail=%d", ok, fail)
        return {"status": "done", "ok": ok, "fail": fail, "results": results}
    except Exception as e:
        logger.exception("scheduled_daily_refresh: FATAL")
        return {"status": "error", "error": str(e)}
