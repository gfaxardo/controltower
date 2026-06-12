"""
OV2-MVP.3A — Usage Metrics (in-memory, no DB, no PII)

Tracks operational adoption metrics during the trial.
Exposed via /ops/omniview-v2/usage-metrics endpoint.

Rules:
- No PII
- No IP tracking
- No browser fingerprinting
- No external analytics
- Aggregated counters only
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict

_trial_start: str = ""
_metrics: Dict = {
    "v2_sessions": 0,
    "v1_sessions": 0,
    "grain": defaultdict(int),
    "source": defaultdict(int),
    "filters": defaultdict(int),
    "fullscreen_toggles": 0,
    "errors": 0,
    "retries": 0,
}
_events: list = []


def set_trial_start(iso_date: str):
    global _trial_start
    _trial_start = iso_date


def record_v2_session(grain: str = "", source: str = ""):
    _metrics["v2_sessions"] += 1
    if grain:
        _metrics["grain"][grain] += 1
    if source:
        _metrics["source"][source] += 1


def record_v1_session():
    _metrics["v1_sessions"] += 1


def record_filter_usage(filter_name: str, value: str = ""):
    _metrics["filters"][f"{filter_name}={value}" if value else filter_name] += 1


def record_fullscreen_toggle():
    _metrics["fullscreen_toggles"] += 1


def record_error():
    _metrics["errors"] += 1


def record_retry():
    _metrics["retries"] += 1


def record_event(event_type: str, detail: str = ""):
    _events.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "detail": detail[:200],
    })
    if len(_events) > 1000:
        _events.pop(0)


def get_usage_metrics() -> dict:
    v2 = _metrics["v2_sessions"]
    v1 = max(_metrics["v1_sessions"], 1)
    ratio = round(v2 / v1, 2)

    v2_errors = _metrics["errors"]
    error_rate = round(v2_errors / max(v2, 1) * 100, 1)

    return {
        "trial_start": _trial_start,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sessions": {
            "v2_total": v2,
            "v1_total": _metrics["v1_sessions"],
            "v2_v1_ratio": ratio,
        },
        "grain_usage": dict(_metrics["grain"]),
        "source_usage": dict(_metrics["source"]),
        "filter_usage": dict(_metrics["filters"]),
        "fullscreen_toggles": _metrics["fullscreen_toggles"],
        "errors": {
            "total": v2_errors,
            "rate_pct": error_rate,
            "retries": _metrics["retries"],
        },
        "recent_events": _events[-20:],
    }
