"""
YEGO Lima Growth — Priority Allocation Service (LG-2.3 V1).

Deterministic allocation: assigns daily capacity to programs in priority order.
Imports priority rules from centralized registry.

Inputs:
  - opportunities: {program_code: count}
  - total_capacity: int

Process:
  - Sort programs by PRIORITY_RANK (ascending).
  - Allocate capacity sequentially until exhausted.
  - Each program gets min(available, remaining_capacity).

No AI. No scoring. No prediction.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

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
