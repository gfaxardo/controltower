"""
YEGO Lima Growth — Priority Allocation Service (LG-2.3 V2 — R2.8G).

Deterministic allocation: assigns daily capacity to programs in priority order.
Now supports policy-aware allocation (STRICT_PRIORITY, PROPORTIONAL, HYBRID).
Imports priority rules from centralized registry.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.yego_lima_capacity_service import get_capacity_config
from app.config.yego_lima_priority_registry import (
    PRIORITY_ORDER,
    get_display_name,
)

logger = logging.getLogger(__name__)

TABLE_PRIORITIZED = "growth.yango_lima_prioritized_opportunity_daily"


def allocate_capacity(
    opportunities: Dict[str, int],
    total_capacity: int,
) -> Dict[str, Any]:
    """
    Core allocation engine — deterministic, pure function.
    Takes raw inputs and returns allocation result.
    """
    programs = []
    remaining = total_capacity
    total_opportunities = 0
    total_allocated = 0

    for program_code, priority_rank in PRIORITY_ORDER:
        available = opportunities.get(program_code, 0)
        total_opportunities += available

        allocated = min(available, remaining)
        total_allocated += allocated
        remaining -= allocated
        unmet = available - allocated
        rate = allocated / available if available > 0 else 0

        programs.append({
            "program_code": program_code,
            "program_name": get_display_name(program_code),
            "priority_rank": priority_rank,
            "available_opportunities": available,
            "allocated_capacity": allocated,
            "unmet_opportunities": unmet,
            "allocation_rate": round(rate, 4),
        })

    coverage = total_capacity / total_opportunities if total_opportunities > 0 else 1.0
    unmet_total = max(0, total_opportunities - total_allocated)

    return {
        "total_capacity": total_capacity,
        "total_opportunities": total_opportunities,
        "total_allocated": total_allocated,
        "unmet_total": unmet_total,
        "remaining_capacity": remaining,
        "coverage_rate": round(coverage, 4),
        "programs": programs,
    }


def get_priority_allocation(date_str: str) -> Dict[str, Any]:
    """
    Full pipeline: fetches opportunities from DB, reads capacity config,
    runs allocation engine, returns complete result.
    """
    actionable_by_program = _get_actionable_counts(date_str)
    capacity_data = get_capacity_config(date_str)
    total_capacity = capacity_data.get("total_capacity", 0)

    result = allocate_capacity(actionable_by_program, total_capacity)
    result["date"] = date_str
    return result


def _get_actionable_counts(date_str: str) -> Dict[str, int]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT selected_program_code, COUNT(*) as cnt "
            f"FROM {TABLE_PRIORITIZED} "
            f"WHERE opportunity_date = %(d)s AND is_actionable_today = true "
            f"GROUP BY selected_program_code",
            {"d": date_str},
        )
        rows = cur.fetchall()
        return {r["selected_program_code"]: r["cnt"] for r in rows}


# ── POLICY-AWARE ALLOCATION (R2.8G) ──

def allocate_capacity_with_policy(
    date: str,
) -> Dict[str, Any]:
    """
    Policy-aware allocation. Reads active policy and applies it.
    Falls back to STRICT_PRIORITY if no active policy exists.
    """
    actionable_by_program = _get_actionable_counts(date)
    capacity_data = get_capacity_config(date)
    total_capacity = capacity_data.get("total_capacity", 0)
    total_actionable = sum(actionable_by_program.values())

    policy_applied = False
    policy_id = None
    policy_version = None
    allocation_mode = "STRICT_PRIORITY"
    warnings: List[str] = []
    policy_programs = []

    try:
        from app.services.yego_lima_program_capacity_policy_service import get_active_policy
        policy = get_active_policy(date)
        if policy.get("active") and policy.get("programs"):
            policy_applied = True
            policy_programs = policy["programs"]
            if policy_programs:
                policy_id = policy_programs[0].get("id")
                policy_version = policy_programs[0].get("version")
                mode = policy_programs[0].get("allocation_mode", "STRICT_PRIORITY")
                if mode in ("STRICT_PRIORITY", "PROPORTIONAL", "HYBRID"):
                    allocation_mode = mode
    except Exception as e:
        warnings.append(f"Policy lookup failed: {e}. Using fallback STRICT_PRIORITY.")

    # Perform allocation
    programs = []
    remaining = total_capacity
    total_opportunities = 0
    total_allocated = 0

    if not policy_applied or allocation_mode == "STRICT_PRIORITY" or not policy_programs:
        # Fallback / STRICT_PRIORITY: use registry order
        for program_code, priority_rank in PRIORITY_ORDER:
            available = actionable_by_program.get(program_code, 0)
            total_opportunities += available
            allocated = min(available, remaining)
            total_allocated += allocated
            remaining -= allocated
            unmet = available - allocated
            programs.append({
                "program_code": program_code,
                "program_name": get_display_name(program_code),
                "priority_rank": priority_rank,
                "available_opportunities": available,
                "allocated_capacity": allocated,
                "unmet_opportunities": unmet,
                "allocation_rate": round(allocated / available, 4) if available > 0 else 0,
            })
    else:
        # Policy-driven allocation
        pp_sorted = sorted(policy_programs, key=lambda p: p.get("priority_rank", 999))
        for pp in pp_sorted:
            code = pp.get("program_code", "")
            rank = pp.get("priority_rank", 999)
            mode = pp.get("allocation_mode", "STRICT_PRIORITY")
            enabled = pp.get("is_enabled", True)
            min_cap = pp.get("min_daily_capacity")
            max_cap = pp.get("max_daily_capacity")
            target_pct = pp.get("target_share_pct")

            avail = actionable_by_program.get(code, 0)
            total_opportunities += avail
            allocated = 0

            if not enabled:
                programs.append({"program_code": code, "program_name": get_display_name(code),
                                 "priority_rank": rank, "available_opportunities": avail,
                                 "allocated_capacity": 0, "unmet_opportunities": avail,
                                 "allocation_rate": 0})
                continue

            if mode == "STRICT_PRIORITY":
                allocated = min(avail, remaining)
            elif mode == "PROPORTIONAL":
                share = avail / max(1, total_actionable) if target_pct is None else target_pct / 100
                allocated = min(avail, max(1, int(total_capacity * share)))
            elif mode == "HYBRID":
                max_from_pct = int(total_capacity * (target_pct / 100)) if target_pct else total_capacity
                if max_cap: max_from_pct = min(max_from_pct, max_cap)
                allocated = min(avail, remaining, max_from_pct)

            if max_cap: allocated = min(allocated, max_cap)
            if min_cap and avail > 0: allocated = max(allocated, min(min_cap, avail))
            allocated = min(allocated, remaining)
            remaining -= allocated
            total_allocated += allocated

            programs.append({
                "program_code": code,
                "program_name": get_display_name(code),
                "priority_rank": rank,
                "available_opportunities": avail,
                "allocated_capacity": allocated,
                "unmet_opportunities": max(0, avail - allocated),
                "allocation_rate": round(allocated / avail, 4) if avail > 0 else 0,
            })

    unmet_total = max(0, total_opportunities - total_allocated)
    coverage = total_capacity / total_opportunities if total_opportunities > 0 else 1.0

    return {
        "date": date,
        "total_capacity": total_capacity,
        "total_opportunities": total_opportunities,
        "total_allocated": total_allocated,
        "unmet_total": unmet_total,
        "remaining_capacity": remaining,
        "coverage_rate": round(coverage, 4),
        "programs": programs,
        "policy_applied": policy_applied,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "allocation_mode": allocation_mode,
        "warnings": warnings,
    }
