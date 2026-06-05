"""
YEGO Lima Growth — Channel Allocation Service (LG-2.4 V1).

Takes priority allocation output (LG-2.3) and distributes each program's
allocated capacity across operational channels using preference rules.

Input:
  - priority_allocation: output from get_priority_allocation()
  - channel_capacity: per-channel capacity from get_capacity_config()

Process:
  - For each program, iterate preferred channels in order.
  - Assign min(remaining_program, remaining_channel) to each channel.
  - Track channel utilization.

No AI. No scoring. No individual driver assignment.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.yego_lima_priority_allocation_service import get_priority_allocation
from app.services.yego_lima_capacity_service import get_capacity_config
from app.config.yego_lima_channel_registry import (
    CANONICAL_CHANNEL_CODES,
    get_channel_preference,
    get_channel_display_name,
    resolve_db_channel_to_code,
)

logger = logging.getLogger(__name__)


def allocate_to_channels(
    program_allocations: List[Dict[str, Any]],
    channel_capacities: Dict[str, int],
) -> Dict[str, Any]:
    """
    Core engine — deterministic, pure function.
    Distributes program allocations across channels by preference order.
    """
    remaining_by_channel = dict(channel_capacities)
    total_channel_capacity = sum(channel_capacities.values())

    programs = []
    total_allocated = 0

    for prog in program_allocations:
        allocated = prog.get("allocated_capacity", 0)
        remaining = allocated
        channel_entries = []

        for channel_code in get_channel_preference(prog.get("program_code", "")):
            chan_avail = remaining_by_channel.get(channel_code, 0)
            assigned = min(remaining, chan_avail)
            if assigned > 0:
                channel_entries.append({
                    "channel_code": channel_code,
                    "channel_name": get_channel_display_name(channel_code),
                    "allocated_capacity": assigned,
                })
                remaining_by_channel[channel_code] = chan_avail - assigned
                remaining -= assigned
                total_allocated += assigned

        programs.append({
            "program_code": prog.get("program_code"),
            "program_name": prog.get("program_name"),
            "priority_rank": prog.get("priority_rank"),
            "program_allocated_capacity": allocated,
            "channel_allocations": channel_entries,
            "unassigned_capacity": remaining,
        })

    channels = []
    for code in CANONICAL_CHANNEL_CODES:
        original = channel_capacities.get(code, 0)
        remaining = remaining_by_channel.get(code, 0)
        used = original - remaining
        channels.append({
            "channel_code": code,
            "channel_name": get_channel_display_name(code),
            "total_capacity": original,
            "allocated_capacity": used,
            "remaining_capacity": remaining,
            "utilization_rate": round(used / original, 4) if original > 0 else 0,
        })

    unassigned = sum(p["unassigned_capacity"] for p in programs)
    total_priority_allocated = sum(p.get("allocated_capacity", 0) for p in program_allocations)

    return {
        "total_channel_capacity": total_channel_capacity,
        "total_priority_allocated": total_priority_allocated,
        "total_channel_allocated": total_allocated,
        "unassigned_capacity": unassigned,
        "channels": channels,
        "programs": programs,
    }


def get_channel_allocation(date_str: str) -> Dict[str, Any]:
    """
    Full pipeline: fetches priority allocation, reads channel capacity,
    runs channel allocation engine, returns complete result.
    """
    priority_result = get_priority_allocation(date_str)
    capacity_data = get_capacity_config(date_str)

    channel_capacities: Dict[str, int] = {}
    for ch in capacity_data.get("channels", []):
        code = resolve_db_channel_to_code(ch["channel"])
        channel_capacities[code] = ch.get("channel_capacity", 0)

    result = allocate_to_channels(
        priority_result.get("programs", []),
        channel_capacities,
    )
    result["date"] = date_str
    result["total_capacity"] = priority_result.get("total_capacity", 0)
    return result
