"""
Referencias al BackgroundScheduler de Omniview (main.py) para exponer next_run en /real-freshness.
"""
from __future__ import annotations

from typing import Any, Optional

_scheduler: Any = None


def attach_omniview_scheduler(scheduler: Any) -> None:
    global _scheduler
    _scheduler = scheduler


def get_omniview_scheduler() -> Any:
    return _scheduler


def _next_iso(job_id: str) -> Optional[str]:
    if _scheduler is None:
        return None
    try:
        j = _scheduler.get_job(job_id)
        if j and j.next_run_time:
            return j.next_run_time.isoformat()
    except Exception:
        return None
    return None


def get_next_omniview_refresh_run_iso() -> Optional[str]:
    return _next_iso("omniview_business_slice_real_refresh")


def get_next_omniview_watchdog_run_iso() -> Optional[str]:
    return _next_iso("omniview_real_data_watchdog")
