"""
YEGO Lima Growth — Today's Action Plan Service (LG-UX-R2.6)

Transforms operational data into actionable daily plan.
Deterministic only. No AI. No forecast. No prediction.

Consumes existing services:
  - get_operational_summary()
  - get_queue_summary()
  - get_programs_summary()
  - get_capacity_config()

NO new tables. NO duplicate logic. NO new queries.
"""
from __future__ import annotations

import logging
from datetime import date as DateType
from typing import Any, Dict, List, Optional

from app.services.yego_lima_operational_summary_service import get_operational_summary
from app.services.yego_lima_queue_summary_service import get_queue_summary
from app.services.yego_lima_programs_summary_service import get_programs_summary
from app.services.yego_lima_capacity_service import get_capacity_config
from app.services.freshness_service import compute_freshness

logger = logging.getLogger(__name__)


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


def get_today_action_plan(date: str) -> Dict[str, Any]:
    op = get_operational_summary(date)
    qs = get_queue_summary(date)
    programs_data = get_programs_summary(date)
    capacity_data = get_capacity_config(date)

    universe_total = _safe_int(op.get("universe_total"))
    eligible_total = _safe_int(op.get("eligible_total"))
    prioritized_total = _safe_int(op.get("prioritized_total"))
    actionable_today = _safe_int(op.get("actionable_today"))
    daily_action_capacity = _safe_int(op.get("daily_action_capacity"))
    capacity_total = _safe_int(capacity_data.get("total_capacity", 0))
    channels = capacity_data.get("channels", [])

    queue_total = _safe_int(qs.get("totals", {}).get("total", op.get("queue_total")))
    queue_ready = _safe_int(qs.get("totals", {}).get("ready", op.get("queue_ready")))
    queue_held = _safe_int(qs.get("totals", {}).get("held", op.get("queue_held")))
    queue_exported = _safe_int(qs.get("totals", {}).get("exported", 0))

    queue_status = qs.get("status", "UNKNOWN")
    hold_reasons = qs.get("hold_reasons", [])

    programs = programs_data.get("programs", [])

    # ── Operational Status ──
    if queue_status == "NOT_BUILT":
        operational_status = "QUEUE_NOT_BUILT"
    elif queue_status == "EMPTY":
        operational_status = "QUEUE_EMPTY"
    elif queue_ready > 0 and queue_held == 0:
        operational_status = "READY_TO_EXPORT"
    elif queue_ready > 0 and queue_held > 0:
        operational_status = "READY_WITH_BLOCKERS"
    elif queue_held > 0 and queue_ready == 0:
        operational_status = "ALL_HELD"
    elif queue_exported > 0 and queue_total == 0:
        operational_status = "ALL_EXPORTED"
    else:
        operational_status = "IDLE"

    # ── Capacity ──
    capacity_available = capacity_total
    capacity_configured = len([ch for ch in channels if (ch.get("agents", 0) or 0) > 0])
    utilization_pct = round((actionable_today / capacity_total * 100), 1) if capacity_total > 0 else 0
    capacity_gap = actionable_today - capacity_total

    ch_utilization = qs.get("channel_utilization", [])
    channel_details = []
    for ch in channels:
        db_name = ch.get("channel", "")
        cap_val = ch.get("channel_capacity", 0)
        assigned = 0
        ready_ch = 0
        for cu in ch_utilization:
            if cu.get("channel") == db_name:
                assigned = cu.get("assigned_in_queue", 0)
                ready_ch = cu.get("ready_in_queue", 0)
                break
        available_ch = max(0, cap_val - assigned)
        channel_details.append({
            "channel": db_name,
            "agents": ch.get("agents", 0),
            "capacity_per_agent": ch.get("capacity_per_agent", 0),
            "channel_capacity": cap_val,
            "assigned_in_queue": assigned,
            "ready_in_queue": ready_ch,
            "available_capacity": available_ch,
            "utilization_pct": round(assigned / cap_val * 100, 1) if cap_val > 0 else 0,
            "is_full": assigned >= cap_val,
        })

    # Add UNASSIGNED if present
    for cu in ch_utilization:
        if cu.get("channel") == "UNASSIGNED" and cu.get("assigned_in_queue", 0) > 0:
            channel_details.append({
                "channel": "UNASSIGNED",
                "agents": 0,
                "capacity_per_agent": 0,
                "channel_capacity": 0,
                "assigned_in_queue": cu.get("assigned_in_queue", 0),
                "ready_in_queue": 0,
                "available_capacity": 0,
                "utilization_pct": 0,
                "is_full": False,
            })

    capacity_block = {
        "available": capacity_total,
        "configured": capacity_configured,
        "utilization_pct": utilization_pct,
        "channels": channel_details,
    }

    # ── Workload ──
    workload = {
        "ready": queue_ready,
        "held": queue_held,
        "exported": queue_exported,
        "total": queue_total,
        "queue_status": queue_status,
    }

    # ── Gap ──
    gap = {
        "available_capacity": capacity_total,
        "missing_capacity": max(0, actionable_today - capacity_total),
        "excess_capacity": max(0, capacity_total - actionable_today),
        "actionable_total": actionable_today,
        "gap_description": (
            f"Capacidad insuficiente: {actionable_today - capacity_total} accionables exceden la capacidad de {capacity_total}"
            if capacity_total < actionable_today else
            f"Capacidad suficiente: {capacity_total} >= {actionable_today} accionables"
        ),
    }

    # ── Priorities (top 3 programs by actionable + queued) ──
    priorities = _build_priorities(programs, queue_ready, queue_held)

    # ── Blockers ──
    blockers = _build_blockers(hold_reasons, queue_held, capacity_gap, queue_status, programs, channel_details)

    # ── Recommended Actions ──
    recommended_actions = _build_actions(
        operational_status, queue_ready, queue_held, capacity_total,
        actionable_today, capacity_gap, hold_reasons, priorities,
        queue_status, daily_action_capacity
    )

    # ── Freshness ──
    freshness = op.get("freshness", {})

    # ── Explainability map ──
    explainability = op.get("explainability", {})

    return {
        "date": date,
        "freshness": freshness,
        "operational_status": operational_status,
        "capacity": capacity_block,
        "workload": workload,
        "gap": gap,
        "priorities": priorities,
        "blockers": blockers,
        "recommended_actions": recommended_actions,
        "explainability": explainability,
        "pipeline_summary": {
            "universe_total": universe_total,
            "eligible_total": eligible_total,
            "prioritized_total": prioritized_total,
            "actionable_today": actionable_today,
            "daily_action_capacity": daily_action_capacity,
        },
    }


def _build_priorities(
    programs: List[Dict[str, Any]],
    queue_ready: int,
    queue_held: int,
) -> List[Dict[str, Any]]:
    scored = []
    for p in programs:
        eligible = _safe_int(p.get("eligible_total"))
        actionable = _safe_int(p.get("actionable_today"))
        queued = _safe_int(p.get("queued_total"))
        prioritized = _safe_int(p.get("prioritized_total"))
        code = p.get("program_code", "")
        name = p.get("program_name", code)
        rank = p.get("priority_rank", 999)

        if queued == 0 and actionable == 0:
            continue

        score = (actionable * 3) + (queued * 2) + eligible
        reason_parts = []
        if eligible > 0:
            reason_parts.append(f"{eligible} elegibles")
        if actionable > 0:
            reason_parts.append(f"{actionable} accionables")
        if queued > 0:
            reason_parts.append(f"{queued} en cola")

        scored.append({
            "rank": rank,
            "program_code": code,
            "program_name": name,
            "eligible_total": eligible,
            "prioritized_total": prioritized,
            "actionable_today": actionable,
            "queued_total": queued,
            "score": score,
            "reason": ", ".join(reason_parts) if reason_parts else "Sin actividad",
            "is_priority": actionable > 0,
        })

    scored.sort(key=lambda x: (0 if x["is_priority"] else 1, x["rank"]))
    top3 = scored[:3]

    for i, p in enumerate(top3):
        p["priority_position"] = i + 1

    return top3


def _build_blockers(
    hold_reasons: List[Dict[str, Any]],
    queue_held: int,
    capacity_gap: int,
    queue_status: str,
    programs: List[Dict[str, Any]],
    channel_details: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    blockers = []

    if queue_status == "NOT_BUILT":
        blockers.append({
            "blocker": "QUEUE_NOT_BUILT",
            "severity": "HIGH",
            "count": 1,
            "description": "La cola no ha sido construida para hoy",
            "remediation": "Ejecutar 'Construir Cola' desde Execution Queue",
            "action_required": True,
        })
        return blockers

    for hr in hold_reasons:
        reason = hr.get("reason", "")
        count = _safe_int(hr.get("count"))
        remediation = hr.get("remediation", "")
        if count > 0:
            blockers.append({
                "blocker": reason.upper().replace(" ", "_"),
                "severity": "HIGH" if count > 100 else "MEDIUM",
                "count": count,
                "description": f"{count} conductores retenidos: {reason}",
                "remediation": remediation,
                "action_required": True,
            })

    # Per-channel capacity blockers: detect full channels
    if channel_details:
        for cd in channel_details:
            if cd.get("is_full") and cd.get("channel") != "UNASSIGNED":
                ch_name = cd.get("channel", "")
                ch_cap = cd.get("channel_capacity", 0)
                blockers.append({
                    "blocker": f"CHANNEL_FULL_{cd.get('channel', '').upper().replace(' ', '_').replace('/', '_')}",
                    "severity": "MEDIUM",
                    "count": ch_cap,
                    "description": f"Canal '{ch_name}' lleno ({cd.get('assigned_in_queue', 0)}/{ch_cap}). No acepta mas conductores.",
                    "remediation": f"Aumentar capacidad del canal '{ch_name}' en Configuracion",
                    "action_required": False,
                })

    if capacity_gap > 0:
        blockers.append({
            "blocker": "CAPACITY_GAP",
            "severity": "HIGH" if capacity_gap > 100 else "MEDIUM",
            "count": capacity_gap,
            "description": f"Hay {capacity_gap} accionables sin capacidad operativa",
            "remediation": "Aumentar capacidad en Configuracion o ajustar daily_action_capacity",
            "action_required": True,
        })

    # Check programs with no data
    for p in programs:
        if _safe_int(p.get("eligible_total")) == 0 and _safe_int(p.get("actionable_today")) == 0:
            continue
        if _safe_int(p.get("queued_total")) == 0 and _safe_int(p.get("actionable_today")) > 0:
            blockers.append({
                "blocker": f"PROGRAM_NOT_QUEUED_{p.get('program_code', 'UNKNOWN')}",
                "severity": "LOW",
                "count": _safe_int(p.get("actionable_today")),
                "description": f"{p.get('program_name', '?')}: {p.get('actionable_today')} accionables, 0 en cola",
                "remediation": "Construir cola para incluir estos conductores",
                "action_required": False,
            })

    return blockers


def _build_actions(
    operational_status: str,
    queue_ready: int,
    queue_held: int,
    capacity_total: int,
    actionable_today: int,
    capacity_gap: int,
    hold_reasons: List[Dict[str, Any]],
    priorities: List[Dict[str, Any]],
    queue_status: str,
    daily_action_capacity: int,
) -> List[Dict[str, Any]]:
    actions = []

    if queue_status == "NOT_BUILT":
        actions.append({
            "priority": 1,
            "action": "Construir Cola de Asignacion",
            "reason": "La cola no ha sido construida para la fecha actual. Sin cola no hay trabajo asignable.",
            "expected_effect": f"Generar cola con hasta {daily_action_capacity} conductores accionables",
            "action_type": "BUILD",
            "blocker": "QUEUE_NOT_BUILT",
        })
        return actions

    # RULE 1: READY > 0 → Export
    if queue_ready > 0:
        effect = f"Enviar {queue_ready} conductores a LoopControl para gestion"
        if queue_ready > capacity_total:
            effect += f" (requiere {queue_ready // capacity_total + 1} tandas por capacidad insuficiente)"

        actions.append({
            "priority": 1,
            "action": f"Exportar {queue_ready} conductores READY",
            "reason": f"Hay {queue_ready} conductores listos con telefono y canal asignado esperando exportacion",
            "expected_effect": effect,
            "action_type": "EXPORT",
            "count": queue_ready,
        })

    # RULE 2: HELD > 0 → Resolve
    if queue_held > 0:
        for hr in hold_reasons:
            reason = hr.get("reason", "")
            count = _safe_int(hr.get("count"))
            remediation = hr.get("remediation", "")
            if count > 0:
                actions.append({
                    "priority": 2 if queue_ready > 0 else 1,
                    "action": f"Resolver {count} HELD: {reason}",
                    "reason": f"{count} conductores retenidos por '{reason}'",
                    "expected_effect": f"Liberar {count} conductores a estado READY para exportacion",
                    "action_type": "RESOLVE",
                    "count": count,
                    "remediation": remediation,
                })

    # RULE 3: HELD by unassigned channel → Assign channel
    for hr in hold_reasons:
        if "canal" in (hr.get("reason", "") or "").lower():
            count = _safe_int(hr.get("count"))
            if count > 0:
                actions.append({
                    "priority": 3 if queue_ready > 0 else 2,
                    "action": f"Asignar canal a {count} conductores HELD",
                    "reason": f"{count} conductores no tienen canal asignado",
                    "expected_effect": f"Habilitar {count} conductores para exportacion a LoopControl",
                    "action_type": "ASSIGN_CHANNEL",
                    "count": count,
                })

    # RULE 4: Identify priority program
    if priorities:
        top = priorities[0]
        if top.get("actionable_today", 0) > 0:
            actions.append({
                "priority": 4,
                "action": f"Priorizar Programa: {top.get('program_name', top.get('program_code', ''))}",
                "reason": f"Programa con mayor prioridad operativa. {top.get('reason', '')}",
                "expected_effect": f"Gestionar {top.get('actionable_today', 0)} conductores del programa prioritario",
                "action_type": "PRIORITIZE",
                "program": top.get("program_code"),
                "count": top.get("actionable_today", 0),
            })

    # RULE 5: READY > Capacity
    if queue_ready > capacity_total and queue_ready > 0:
        needed_tandas = queue_ready // capacity_total + 1
        actions.append({
            "priority": 5,
            "action": f"Ejecutar export en {needed_tandas} tandas (READY={queue_ready} > Capacity={capacity_total})",
            "reason": f"Capacidad diaria ({capacity_total}) es menor que los READY ({queue_ready})",
            "expected_effect": f"Exportar todos los {queue_ready} READY en {needed_tandas} tandas",
            "action_type": "SCALE",
            "count": queue_ready,
        })

    # RULE 6: READY < Capacity → Idle capacity
    if queue_ready < capacity_total and queue_ready > 0:
        idle = capacity_total - queue_ready
        actions.append({
            "priority": 6,
            "action": f"Capacidad ociosa: {idle} slots disponibles",
            "reason": f"Capacidad ({capacity_total}) > READY ({queue_ready}). {idle} slots sin utilizar.",
            "expected_effect": "Aumentar daily_action_capacity o construir mas cola para aprovechar capacidad",
            "action_type": "NOTICE",
            "count": idle,
        })

    # RULE: Capacity gap warning
    if capacity_gap > 0:
        actions.append({
            "priority": 7,
            "action": f"Ajustar capacidad: {capacity_gap} accionables exceden la capacidad",
            "reason": f"daily_action_capacity permite {actionable_today} accionables pero solo hay capacidad para {capacity_total}",
            "expected_effect": f"Reducir daily_action_capacity de {daily_action_capacity} a {capacity_total} o aumentar capacidad",
            "action_type": "ADJUST",
            "count": capacity_gap,
        })

    return actions
