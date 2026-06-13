"""
Freshness Service — LG-UX-R2.2

Standardized freshness calculation for Lima Growth data sources.
Evaluates age of source data against configurable thresholds.
Returns FRESH / WARNING / STALE / UNKNOWN.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta, date as date_type
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

# Thresholds in minutes
THRESHOLDS: Dict[str, int] = {
    "driver_snapshot": 1440,       # 24h
    "opportunity_engine": 1440,    # 24h
    "assignment_queue": 240,       # 4h
    "exports": 240,                # 4h
    "loopcontrol": 240,            # 4h
    "capacity": 10080,             # 7d
    "program_eligibility": 1440,   # 24h
    "policy_config": 10080,        # 7d
    "driver_history_weekly": 10080,       # 7d (weekly grain)
    "opportunity": 1440,                  # 24h
    "control_loop": 480,                  # 8h
}

DOMAIN_LABELS: Dict[str, str] = {
    "driver_snapshot": "Driver State Snapshot",
    "opportunity_engine": "Opportunity Engine",
    "assignment_queue": "Assignment Queue",
    "exports": "Export Ledger",
    "loopcontrol": "LoopControl Integration",
    "capacity": "Capacity Config",
    "program_eligibility": "Program Eligibility",
    "policy_config": "Policy Config",
    "driver_history_weekly": "Driver History Weekly",
    "opportunity": "Daily Opportunity List",
    "control_loop": "Control Loop State",
}


def compute_freshness(
    domain: str,
    last_refreshed_at: Optional[datetime] = None,
    source: str = "",
) -> Dict[str, Any]:
    threshold = THRESHOLDS.get(domain, 1440)

    if last_refreshed_at is None:
        return {
            "status": "UNKNOWN",
            "last_refreshed_at": None,
            "age_minutes": None,
            "threshold_minutes": threshold,
            "source": source,
            "domain": domain,
            "reason": "No timestamp available",
            "remediation": f"Enable timestamp tracking for {DOMAIN_LABELS.get(domain, domain)}.",
        }

    if isinstance(last_refreshed_at, str):
        try:
            last_refreshed_at = datetime.fromisoformat(last_refreshed_at)
        except (ValueError, TypeError):
            return {
                "status": "UNKNOWN",
                "last_refreshed_at": str(last_refreshed_at),
                "age_minutes": None,
                "threshold_minutes": threshold,
                "source": source,
                "domain": domain,
                "reason": "Unparseable timestamp",
                "remediation": "Check source timestamp format.",
            }

    if isinstance(last_refreshed_at, date_type) and not isinstance(last_refreshed_at, datetime):
        last_refreshed_at = datetime.combine(last_refreshed_at, datetime.min.time(), tzinfo=timezone.utc)

    if last_refreshed_at.tzinfo is None:
        last_refreshed_at = last_refreshed_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_minutes = round((now - last_refreshed_at).total_seconds() / 60, 1)

    if age_minutes <= threshold:
        status = "FRESH"
        reason = f"Data is {age_minutes:.0f}min old (threshold: {threshold}min)"
        remediation = None
    elif age_minutes <= threshold * 2:
        status = "WARNING"
        reason = f"Data is {age_minutes:.0f}min old (threshold: {threshold}min)"
        remediation = "Consider refreshing the source data."
    else:
        status = "STALE"
        reason = f"Data is {age_minutes:.0f}min old (threshold: {threshold}min)"
        remediation = f"Refresh required. Data exceeds {threshold * 2}min staleness limit."

    return {
        "status": status,
        "last_refreshed_at": last_refreshed_at.isoformat(),
        "age_minutes": age_minutes,
        "threshold_minutes": threshold,
        "source": source,
        "domain": domain,
        "reason": reason,
        "remediation": remediation,
    }


def overall_status(freshness_items: List[Dict[str, Any]]) -> str:
    statuses = [f["status"] for f in freshness_items]
    critical_domains = {"driver_snapshot", "opportunity_engine", "assignment_queue"}
    critical_statuses = [f["status"] for f in freshness_items if f.get("domain") in critical_domains]

    if "STALE" in critical_statuses:
        return "STALE"
    if "STALE" in statuses:
        return "WARNING"
    if "WARNING" in statuses or "UNKNOWN" in critical_statuses:
        return "WARNING"
    if "UNKNOWN" in statuses:
        return "WARNING"
    return "FRESH"
