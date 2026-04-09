"""
Estado de arranque y health extendido (hardening): ok | degraded | blocked.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

_last_report: Optional[Dict[str, Any]] = None


def set_startup_report(report: Dict[str, Any]) -> None:
    global _last_report
    _last_report = dict(report) if report else None


def get_startup_report() -> Dict[str, Any]:
    if _last_report is None:
        return {
            "overall": "unknown",
            "message": "Startup aún no ejecutado o reporte no disponible",
            "checks": [],
        }
    return dict(_last_report)
