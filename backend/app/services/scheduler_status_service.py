"""
Scheduler Status Service — CF-H1J.7 Regression Guardrails
Tracks APScheduler state: active / disabled / missing_dependency / error.
No silent operational failure allowed.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SCHEDULER_ACTIVE = "active"
SCHEDULER_DISABLED = "disabled"
SCHEDULER_MISSING_DEP = "missing_dependency"
SCHEDULER_ERROR = "error"
SCHEDULER_UNKNOWN = "unknown"

_scheduler_lock = threading.Lock()
_scheduler_status: str = SCHEDULER_UNKNOWN
_scheduler_detail: str = ""
_scheduler_jobs: list = []
_scheduler_started_at: Optional[str] = None


APSCHEDULER_AVAILABLE = False
try:
    import apscheduler  # noqa: F401
    APSCHEDULER_AVAILABLE = True
except ImportError:
    pass


def set_scheduler_active(jobs: list, started_at: Optional[str] = None) -> None:
    global _scheduler_status, _scheduler_detail, _scheduler_jobs, _scheduler_started_at
    with _scheduler_lock:
        _scheduler_status = SCHEDULER_ACTIVE
        _scheduler_detail = ""
        _scheduler_jobs = list(jobs)
        _scheduler_started_at = started_at


def set_scheduler_disabled(reason: str = "CT_SCHEDULER_ENABLED=false") -> None:
    global _scheduler_status, _scheduler_detail, _scheduler_jobs
    with _scheduler_lock:
        _scheduler_status = SCHEDULER_DISABLED
        _scheduler_detail = reason
        _scheduler_jobs = []


def set_scheduler_missing_dependency(detail: str = "apscheduler not installed") -> None:
    global _scheduler_status, _scheduler_detail, _scheduler_jobs
    with _scheduler_lock:
        _scheduler_status = SCHEDULER_MISSING_DEP
        _scheduler_detail = detail
        _scheduler_jobs = []


def set_scheduler_error(detail: str) -> None:
    global _scheduler_status, _scheduler_detail, _scheduler_jobs
    with _scheduler_lock:
        _scheduler_status = SCHEDULER_ERROR
        _scheduler_detail = detail
        _scheduler_jobs = []


def get_scheduler_status() -> Dict[str, Any]:
    with _scheduler_lock:
        return {
            "status": _scheduler_status,
            "detail": _scheduler_detail,
            "dependency_available": APSCHEDULER_AVAILABLE,
            "jobs": list(_scheduler_jobs),
            "started_at": _scheduler_started_at,
        }
