"""
Job operacional: recarga ops.real_business_slice_day_fact + week_fact
para el mes en curso y el anterior (semanas que cruzan meses).

Misma lógica que scripts/backfill_business_slice_daily.py pero acotada
a ventana operativa — invocable por APScheduler, POST admin o CLI.
"""
from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any, Dict, List, Optional

from app.db.connection import get_db, get_db_audit
from app.services.business_slice_incremental_load import (
    load_business_slice_day_for_month,
    load_business_slice_week_for_month,
)
from app.services.business_slice_service import FACT_DAILY
from app.services.upstream_real_status_service import get_upstream_real_status
from app.settings import settings

logger = logging.getLogger(__name__)

_last_refresh_completed_ts: float = 0.0


def get_last_real_refresh_completed_ts() -> float:
    """Monotonic wall time (time.time) del último refresh completado con éxito."""
    return _last_refresh_completed_ts


def run_business_slice_real_refresh_job(force: bool = False) -> Dict[str, Any]:
    """
    Recalcula day_fact + week_fact para [mes anterior, mes actual] respecto a hoy.

    Args:
        force: si True, ignora cooldown entre corridas.

    Returns:
        Dict con ok, months, duration_seconds, errors, freshness_after (best-effort).
    """
    global _last_refresh_completed_ts

    t0 = time.perf_counter()
    timeout_ms = int(getattr(settings, "OMNIVIEW_REAL_REFRESH_TIMEOUT_MS", 1_800_000))
    min_interval_min = max(1, int(getattr(settings, "OMNIVIEW_REAL_REFRESH_MIN_INTERVAL_MINUTES", 15) or 15))
    min_sec = min_interval_min * 60

    if not force and _last_refresh_completed_ts > 0:
        elapsed = time.time() - _last_refresh_completed_ts
        if elapsed < min_sec:
            logger.info(
                "REAL_REFRESH SKIP cooldown elapsed_s=%.0f min_required=%s",
                elapsed,
                min_interval_min,
            )
            return {
                "ok": True,
                "skipped": True,
                "reason": "cooldown",
                "cooldown_seconds_remaining": round(min_sec - elapsed, 1),
                "duration_seconds": round(time.perf_counter() - t0, 2),
            }

    before_max: Optional[str] = None
    upstream: Dict[str, Any] = {}
    try:
        with get_db() as conn:
            upstream = get_upstream_real_status(conn)
            cur = conn.cursor()
            try:
                cur.execute(f"SELECT MAX(trip_date) FROM {FACT_DAILY}")
                row = cur.fetchone()
                before_max = str(row[0]) if row and row[0] is not None else None
            finally:
                cur.close()
    except Exception as e:
        logger.warning("REAL_REFRESH preflight: %s", e)

    logger.info(
        "REAL_REFRESH START upstream_status=%s upstream_max=%s before_day_fact_max=%s force=%s",
        upstream.get("status"),
        upstream.get("max_event_date"),
        before_max,
        force,
    )

    if upstream.get("status") == "empty":
        logger.warning("REAL_REFRESH SKIP no_upstream_data")
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_upstream_data",
            "upstream": upstream,
            "duration_seconds": round(time.perf_counter() - t0, 2),
        }

    today = date.today()
    cur_m = _month_first(today)
    prev_m = _prev_month_first(today)
    months: List[date] = [prev_m, cur_m]

    errors: List[Dict[str, str]] = []
    log_lines: List[str] = []

    logger.info(
        "omniview_real_refresh_job START months=%s timeout_ms=%s",
        [m.isoformat() for m in months],
        timeout_ms,
    )

    for mo in months:
        mo_label = mo.isoformat()[:7]
        try:
            t_m = time.perf_counter()
            logger.info("omniview_real_refresh_job day_fact month=%s", mo_label)
            with get_db_audit(timeout_ms=timeout_ms) as conn:
                cur = conn.cursor()
                nd = load_business_slice_day_for_month(cur, mo, conn)
                conn.commit()
                logger.info("omniview_real_refresh_job week_fact month=%s", mo_label)
                nw = load_business_slice_week_for_month(cur, mo, conn)
                conn.commit()
                cur.close()
            dt = time.perf_counter() - t_m
            log_lines.append(f"{mo_label}: day_rows={nd} week_rows={nw} {dt:.1f}s")
            logger.info(
                "omniview_real_refresh_job month=%s day_rows=%s week_rows=%s duration_s=%.1f",
                mo_label, nd, nw, dt,
            )
        except Exception as e:
            logger.exception("omniview_real_refresh_job month=%s", mo_label)
            errors.append({"month": mo_label, "error": str(e)})

    elapsed = time.perf_counter() - t0
    freshness_after: Dict[str, Any] = {}
    try:
        from app.services.business_slice_real_freshness_service import (
            get_omniview_business_slice_real_freshness,
        )

        freshness_after = get_omniview_business_slice_real_freshness()
    except Exception as fe:
        logger.debug("omniview_real_refresh_job freshness_after skip: %s", fe)

    max_d = (freshness_after.get("day_fact") or {}).get("max_trip_date")
    if len(errors) == 0:
        _last_refresh_completed_ts = time.time()

    logger.info(
        "REAL_REFRESH END duration_s=%.1f errors=%d new_max_date=%s",
        elapsed,
        len(errors),
        max_d,
    )
    logger.info(
        "omniview_real_refresh_job END duration_s=%.1f errors=%d max_trip_date=%s",
        elapsed,
        len(errors),
        max_d,
    )

    return {
        "ok": len(errors) == 0,
        "months": [m.isoformat()[:7] for m in months],
        "duration_seconds": round(elapsed, 2),
        "errors": errors,
        "log": log_lines,
        "freshness_after": freshness_after,
        "upstream_preflight": upstream,
        "before_max_trip_date": before_max,
    }


def _month_first(d: date) -> date:
    return date(d.year, d.month, 1)


def _prev_month_first(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)
