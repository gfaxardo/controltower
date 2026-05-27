"""
Driver Serving Freshness Service — SH3
Control Foundation: Fact Consumption Hardening

Centralized freshness checker for all driver serving facts.
Used by endpoints to determine if facts are ready for consumption.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 10000
FACT_NAMES = [
    "driver_weekly_segment_fact",
    "driver_segment_migration_fact",
    "driver_operational_priority_fact",
    "driver_supply_overview_weekly_fact",
]


def check_fact_freshness(fact_name: str) -> dict:
    """Check if a specific serving fact exists and is fresh."""
    if fact_name not in FACT_NAMES and fact_name != "driver_serving_freshness_fact":
        return {
            "fact_name": fact_name,
            "exists": False,
            "freshness_status": "unknown",
            "row_count": 0,
            "max_operational_period": None,
            "refreshed_at": None,
            "remediation": "Fact name not recognized",
            "ready": False,
        }

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET LOCAL statement_timeout = '10000'")

            cur.execute("""
                SELECT freshness_status, refreshed_at, max_operational_period, row_count, freshness_reason
                FROM ops.driver_serving_freshness_fact
                WHERE fact_name = %(name)s
            """, {"name": fact_name})
            row = cur.fetchone()

            if not row:
                return {
                    "fact_name": fact_name,
                    "exists": False,
                    "freshness_status": "blocked",
                    "row_count": 0,
                    "max_operational_period": None,
                    "refreshed_at": None,
                    "remediation": f"Fact {fact_name} not found in freshness registry. Run refresh_driver_supply_facts.py",
                    "ready": False,
                }

            status = row["freshness_status"]
            ready = status == "fresh"
            remediation = ""
            if not ready:
                remediation = f"Fact is {status}. Run refresh_driver_supply_facts.py to refresh."

            return {
                "fact_name": fact_name,
                "exists": True,
                "freshness_status": status,
                "row_count": row["row_count"] or 0,
                "max_operational_period": row["max_operational_period"].isoformat()[:10] if row.get("max_operational_period") else None,
                "refreshed_at": row["refreshed_at"].isoformat() if row.get("refreshed_at") else None,
                "freshness_reason": row["freshness_reason"],
                "remediation": remediation,
                "ready": ready,
            }
    except Exception as e:
        logger.warning("Freshness check failed for %s: %s", fact_name, e)
        return {
            "fact_name": fact_name,
            "exists": False,
            "freshness_status": "blocked",
            "row_count": 0,
            "max_operational_period": None,
            "refreshed_at": None,
            "remediation": f"Could not verify {fact_name}: {str(e)[:100]}. Ensure DB is available and facts are refreshed.",
            "ready": False,
        }


def check_all_facts() -> dict:
    """Check freshness of all serving facts."""
    results = []
    for name in FACT_NAMES:
        results.append(check_fact_freshness(name))

    all_ready = all(r["ready"] for r in results)
    blocked = [r for r in results if r["freshness_status"] == "blocked"]
    stale = [r for r in results if r["freshness_status"] == "stale"]
    warning = [r for r in results if r["freshness_status"] == "warning"]

    return {
        "status": "ok" if all_ready else ("blocked" if blocked else "warning"),
        "all_ready": all_ready,
        "facts": results,
        "blocked_facts": [r["fact_name"] for r in blocked],
        "stale_facts": [r["fact_name"] for r in stale],
        "warning_facts": [r["fact_name"] for r in warning],
        "remediation": "Run refresh_driver_supply_facts.py to refresh all facts." if not all_ready else "",
    }


def require_fact(fact_name: str, allow_runtime: bool = False) -> dict:
    """
    Check if a fact is ready. If not, return blocking response.
    Used by endpoints to gate consumption.
    """
    freshness = check_fact_freshness(fact_name)
    if freshness["ready"]:
        return freshness

    if allow_runtime:
        return {**freshness, "runtime_fallback": True, "ready": True, "warning": "Using runtime fallback. Performance may degrade."}

    return freshness
