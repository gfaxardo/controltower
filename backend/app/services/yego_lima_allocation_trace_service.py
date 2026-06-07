"""
YEGO Lima Growth — Capacity Allocation Trace Service (LG-UX-R2.8A)

Traces exactly how capacity flows from actionable drivers to assigned channels.
Deterministic. Consumes existing services. NO new tables. NO new queries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.yego_lima_priority_allocation_service import get_priority_allocation
from app.services.yego_lima_channel_allocation_service import get_channel_allocation
from app.services.yego_lima_capacity_service import get_capacity_config
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


def get_allocation_trace(date: str) -> Dict[str, Any]:
    prio = get_priority_allocation(date)
    chan_alloc = get_channel_allocation(date)
    cap = get_capacity_config(date)

    total_capacity = cap.get("total_capacity", 0)
    total_actionable = prio.get("total_opportunities", 0)
    total_allocated = prio.get("total_allocated", 0)
    total_unassigned = max(0, total_actionable - total_allocated)

    # ── Allocation order (step by step) ──
    allocation_order = []
    for p in prio.get("programs", []):
        prog_code = p.get("program_code", "")
        prog_name = p.get("program_name", prog_code)
        rank = p.get("priority_rank", 999)
        available = p.get("available_opportunities", 0)
        allocated = p.get("allocated_capacity", 0)
        unmet = p.get("unmet_opportunities", 0)

        prog_chan = next(
            (cp for cp in chan_alloc.get("programs", []) if cp.get("program_code") == prog_code), {}
        )
        ch_allocations = prog_chan.get("channel_allocations", [])

        step = len(allocation_order)
        for ca in ch_allocations:
            step += 1
            ch_name = ca.get("channel_name", "")
            ch_assigned = ca.get("allocated_capacity", 0)
            allocation_order.append({
                "step": step,
                "program_code": prog_code,
                "program_name": prog_name,
                "priority_rank": rank,
                "channel": ch_name,
                "requested": available,
                "assigned": ch_assigned,
                "rejected": 0,
                "reason": f"Capacidad asignada al canal '{ch_name}' en orden de preferencia",
                "remaining_channel_capacity": 0,
                "remaining_program_demand": unmet,
            })

        if unmet > 0:
            step += 1
            allocation_order.append({
                "step": step,
                "program_code": prog_code,
                "program_name": prog_name,
                "priority_rank": rank,
                "channel": "UNASSIGNED",
                "requested": available,
                "assigned": 0,
                "rejected": unmet,
                "reason": f"Capacidad total agotada: {total_capacity} configurada para {total_actionable} accionables. {unmet} conductores sin canal.",
                "remaining_channel_capacity": 0,
                "remaining_program_demand": unmet,
            })

    # ── By program ──
    programs_section = []
    for p in prio.get("programs", []):
        prog_code = p.get("program_code", "")
        prog_name = p.get("program_name", prog_code)
        available = p.get("available_opportunities", 0)
        allocated = p.get("allocated_capacity", 0)
        unmet = p.get("unmet_opportunities", 0)
        share = round(allocated / total_capacity * 100, 1) if total_capacity > 0 else 0

        reason = ""
        if unmet > 0:
            reason = f"{unmet} conductores sin asignar: la capacidad total ({total_capacity}) es insuficiente"
        elif allocated == 0:
            reason = f"Capacidad agotada por programas de mayor prioridad"
        else:
            reason = f"Asignacion completa: {allocated}/{available}"

        programs_section.append({
            "program_code": prog_code,
            "program_name": prog_name,
            "priority_rank": p.get("priority_rank", 999),
            "actionable": available,
            "assigned": allocated,
            "unassigned": unmet,
            "capacity_share_pct": share,
            "reason": reason,
            "channels_used": [
                ca.get("channel_name", "") for ca in
                (next((cp for cp in chan_alloc.get("programs", []) if cp.get("program_code") == prog_code), {}).get("channel_allocations", []))
            ],
        })

    # ── By channel (from queue reality) ──
    channels_section = []
    for ch in cap.get("channels", []):
        db_name = ch.get("channel", "")
        configured = ch.get("channel_capacity", 0)

        # Which programs filled this channel?
        filled_by = []
        for cp in chan_alloc.get("programs", []):
            for ca in cp.get("channel_allocations", []):
                if ca.get("channel_name") == db_name:
                    filled_by.append({
                        "program_code": cp.get("program_code", ""),
                        "program_name": cp.get("program_name", ""),
                        "assigned": ca.get("allocated_capacity", 0),
                    })

        # From macro alloc
        ch_info = next((c for c in chan_alloc.get("channels", []) if c.get("channel_name") == db_name), {})
        macro_assigned = ch_info.get("allocated_capacity", 0)
        utilization = ch_info.get("utilization_rate", 0) * 100

        channels_section.append({
            "channel": db_name,
            "configured_capacity": configured,
            "macro_assigned": macro_assigned,
            "utilization_pct": round(utilization, 1),
            "filled_by_programs": filled_by,
            "unassigned_pressure": max(0, prio.get("total_opportunities", 0) - total_capacity) if utilization >= 100 else 0,
        })

    # ── Queue-level assignment snapshot ──
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT COUNT(*) as cnt FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s "
            "AND assigned_channel IS NOT NULL AND assigned_channel != 'UNASSIGNED'",
            {"d": date}
        )
        queue_assigned = _safe_int(cur.fetchone()["cnt"])
        cur.execute(
            "SELECT COUNT(*) as cnt FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s "
            "AND (assigned_channel IS NULL OR assigned_channel = 'UNASSIGNED')",
            {"d": date}
        )
        queue_unassigned = _safe_int(cur.fetchone()["cnt"])

    # ── Explanation ──
    explanation = _build_allocation_explanation(programs_section, channels_section, total_capacity, total_actionable, queue_unassigned)
    remediation = _build_allocation_remediation(channels_section, total_capacity, total_actionable)

    return {
        "date": date,
        "total_actionable": total_actionable,
        "total_capacity": total_capacity,
        "assigned_total": total_allocated,
        "unassigned_total": total_unassigned,
        "allocation_order": allocation_order,
        "by_program": programs_section,
        "by_channel": channels_section,
        "queue_reality": {
            "queue_assigned": queue_assigned,
            "queue_unassigned": queue_unassigned,
        },
        "explanation": explanation,
        "remediation": remediation,
    }


def _build_allocation_explanation(
    programs: list, channels: list, capacity: int, actionable: int, unassigned: int
) -> str:
    if unassigned == 0:
        return f"Capacidad suficiente: {capacity} >= {actionable} accionables. Todos los conductores tienen canal asignado."

    full_channels = [c for c in channels if c.get("utilization_pct", 0) >= 100]
    failed_programs = [p for p in programs if p.get("unassigned", 0) > 0]

    parts = [
        f"Capacidad insuficiente: {capacity} configurada para {actionable} accionables ({unassigned} sin canal).",
    ]

    if full_channels:
        names = ", ".join(c["channel"] for c in full_channels)
        parts.append(f"Canales llenos: {names}.")

    if failed_programs:
        for fp in failed_programs:
            parts.append(f"Programa '{fp['program_name']}' tiene {fp['unassigned']} conductores sin canal.")

    parts.append("Los programas compiten por capacidad limitada. El orden de prioridad determina quien recibe capacidad primero.")

    return " ".join(parts)


def _build_allocation_remediation(
    channels: list, capacity: int, actionable: int
) -> str:
    gap = max(0, actionable - capacity)
    full_channels = [c for c in channels if c.get("utilization_pct", 0) >= 100]

    options = []
    if full_channels:
        options.append(f"Aumentar capacidad en canales llenos: {', '.join(c['channel'] for c in full_channels)}")
    options.append(f"Reducir daily_action_capacity de {actionable} a {capacity}")
    if gap > 0:
        options.append(f"Aumentar capacidad total en al menos {gap} para cubrir el gap")

    return ". ".join(options) + "."
