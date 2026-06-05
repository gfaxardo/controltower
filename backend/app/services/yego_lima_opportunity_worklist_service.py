"""
YEGO Lima Growth — Opportunity Worklist Service (LG-2.5A V1).

Generates an executive-ready flat list of actionable drivers
with enriched profile data and channel assignment from LG-2.4.

No campaign execution. No draft creation. No auto-export.
No impact measurement. No agent assignment.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.yego_lima_priority_allocation_service import get_priority_allocation
from app.services.yego_lima_channel_allocation_service import get_channel_allocation
from app.config.yego_lima_priority_registry import get_display_name

logger = logging.getLogger(__name__)

TABLE_OPPORTUNITY = "growth.yango_lima_prioritized_opportunity_daily"


def get_opportunity_worklist(
    date_str: str,
    program: Optional[str] = None,
    channel: Optional[str] = None,
    city: Optional[str] = None,
    park: Optional[str] = None,
) -> Dict[str, Any]:
    drivers = _fetch_actionable_drivers(date_str, program, city, park)

    if not drivers:
        return {"date": date_str, "total_records": 0, "records": []}

    channel_alloc = _get_channel_allocations_by_program(date_str)
    enriched = _enrich_and_assign(drivers, channel_alloc)

    if channel:
        enriched = [d for d in enriched if d.get("assigned_channel") == channel]

    return {
        "date": date_str,
        "total_records": len(enriched),
        "records": enriched,
    }


def _fetch_actionable_drivers(
    date_str: str,
    program: Optional[str],
    city: Optional[str],
    park: Optional[str],
) -> List[Dict[str, Any]]:
    conditions = ["o.opportunity_date = %(d)s", "o.is_actionable_today = true"]
    params: Dict[str, Any] = {"d": date_str}

    if program:
        conditions.append("o.selected_program_code = %(p)s")
        params["p"] = program
    if park:
        conditions.append("dp.park_name = %(park)s")
        params["park"] = park
    if city:
        conditions.append("dp.city = %(city)s")
        params["city"] = city

    where = " AND ".join(conditions)

    query = f"""
        SELECT
            o.driver_profile_id,
            o.selected_program_code,
            o.lifecycle_state,
            o.performance_state,
            o.retention_state,
            o.completed_orders_week,
            o.completed_orders_30d,
            o.distance_to_target,
            o.final_rank,
            o.productivity_bucket,
            o.value_tier,
            o.risk_tier,
            o.exclusion_reason,
            d.full_name AS driver_name,
            d.phone,
            d.park_id,
            dp.park_name,
            dp.city,
            s.last_trip_at
        FROM {TABLE_OPPORTUNITY} o
        LEFT JOIN public.drivers d
            ON d.driver_id = o.driver_profile_id
        LEFT JOIN dim.dim_park dp
            ON dp.park_id = d.park_id
        LEFT JOIN growth.yango_lima_driver_state_snapshot s
            ON s.driver_profile_id = o.driver_profile_id
           AND s.snapshot_date = o.opportunity_date
        WHERE {where}
        ORDER BY o.final_rank ASC
    """

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


def _get_channel_allocations_by_program(date_str: str) -> Dict[str, List[Dict[str, Any]]]:
    try:
        result = get_channel_allocation(date_str)
        allocations: Dict[str, List[Dict[str, Any]]] = {}
        for prog in result.get("programs", []):
            allocs = prog.get("channel_allocations", [])
            if allocs:
                allocations[prog["program_code"]] = allocs
        return allocations
    except Exception:
        logger.warning("Channel allocation unavailable for worklist", exc_info=True)
        return {}


def _enrich_and_assign(
    drivers: List[Dict[str, Any]],
    channel_alloc: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    counts_by_prog_ch: Dict[str, Dict[str, int]] = {}
    result = []

    for d in drivers:
        prog = d.get("selected_program_code", "")
        rank = d.get("final_rank", 999)

        assigned_channel = _assign_channel(prog, rank, channel_alloc, counts_by_prog_ch)
        reason = _build_opportunity_reason(d)

        result.append({
            "driver_id": d.get("driver_profile_id", ""),
            "driver_name": d.get("driver_name") or "Sin nombre",
            "phone": d.get("phone"),
            "program_code": prog,
            "program_name": get_display_name(prog),
            "priority_rank": _priority_from_code(prog),
            "assigned_channel": assigned_channel,
            "opportunity_reason": reason,
            "last_trip_date": _safe_date(d.get("last_trip_at")),
            "recent_trips": d.get("completed_orders_week") or 0,
            "country": "PE",
            "city": d.get("city") or "Lima",
            "park": d.get("park_name") or "Sin park",
            "lifecycle_state": d.get("lifecycle_state"),
            "productivity_bucket": d.get("productivity_bucket"),
            "final_rank": rank,
        })

    result.sort(key=lambda r: (
        r["priority_rank"],
        r["recent_trips"],
        r["driver_name"] or "",
    ))
    return result


def _assign_channel(
    prog: str,
    rank: int,
    channel_alloc: Dict[str, List[Dict[str, Any]]],
    counts: Dict[str, Dict[str, int]],
) -> str:
    allocs = channel_alloc.get(prog, [])
    if not allocs:
        return "UNASSIGNED"

    if prog not in counts:
        counts[prog] = {}

    offset = 0
    for ca in allocs:
        ch_code = ca.get("channel_code", "UNKNOWN")
        ch_cap = ca.get("allocated_capacity", 0)
        used = counts[prog].get(ch_code, 0)
        if used < ch_cap:
            counts[prog][ch_code] = used + 1
            return ch_code
        offset += ch_cap

    return "UNASSIGNED"


def _build_opportunity_reason(d: Dict[str, Any]) -> str:
    lifecycle = d.get("lifecycle_state", "")
    perf = d.get("performance_state", "")
    retention = d.get("retention_state", "")
    bucket = d.get("productivity_bucket", "")
    if d.get("exclusion_reason"):
        return d["exclusion_reason"]
    parts = [p for p in [lifecycle, perf, retention, bucket] if p]
    return " / ".join(parts) if parts else "Oportunidad priorizada"


def _priority_from_code(code: str) -> int:
    from app.config.yego_lima_priority_registry import PRIORITY_RANK
    return PRIORITY_RANK.get(code, 999)


def _safe_date(val):
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()[:10]
    return str(val)[:10]
