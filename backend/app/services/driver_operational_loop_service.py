"""
Driver Operational Loop Service — OLM1
Operational Loop Maturity: Loop Status, Next Action, Follow-up, QA, Operating Board.

Operational Loop:
  1. Detection → 2. Prioritization → 3. Campaign Creation → 4. CRM Export
  5. Execution → 6. Outcome Ingest → 7. Follow-up → 8. Effectiveness → 9. Learning Notes

Principles:
  - Deterministic rules only. NO AI, NO ML.
  - Drivers decide and measure. CRM executes contact.
  - Each campaign has traceable loop state.
  - No false causality claims.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

LOOP_STATUSES = [
    "DETECTED",
    "PRIORITIZED",
    "CAMPAIGN_DRAFT",
    "READY_FOR_CRM",
    "SENT_TO_CRM",
    "IN_EXECUTION",
    "OUTCOMES_RECEIVED",
    "FOLLOW_UP_PENDING",
    "MEASURED",
    "CLOSED",
    "NEEDS_REVIEW",
]

NEXT_ACTIONS = {
    "CREATE_CAMPAIGN": {
        "label": "Crear campaña",
        "reason": "Hay conductores priorizados sin campaña activa",
        "owner_type": "supervisor",
        "urgency": "medium",
    },
    "EXPORT_TO_CRM": {
        "label": "Exportar al CRM",
        "reason": "Campaña lista para enviar al equipo de contacto",
        "owner_type": "operator",
        "urgency": "high",
    },
    "IMPORT_OUTCOMES": {
        "label": "Importar resultados del contacto",
        "reason": "Campaña enviada al CRM, pendiente registrar respuestas",
        "owner_type": "operator",
        "urgency": "high",
    },
    "REVIEW_BAD_PHONES": {
        "label": "Revisar teléfonos incorrectos",
        "reason": "Hay conductores con teléfono inválido que requieren actualización de datos",
        "owner_type": "data_quality",
        "urgency": "medium",
    },
    "FOLLOW_UP_SECOND_ATTEMPT": {
        "label": "Segundo intento de contacto",
        "reason": "Conductores sin respuesta que aún pueden ser contactados",
        "owner_type": "operator",
        "urgency": "medium",
    },
    "WAIT_MEASUREMENT_WINDOW": {
        "label": "Esperar ventana de medición",
        "reason": "Los resultados del contacto necesitan tiempo para observar cambio en viajes",
        "owner_type": "system",
        "urgency": "low",
    },
    "REVIEW_EFFECTIVENESS": {
        "label": "Revisar resultado observado",
        "reason": "Ventana de medición cumplida, revisar si hubo cambio en comportamiento",
        "owner_type": "supervisor",
        "urgency": "medium",
    },
    "CLOSE_CAMPAIGN": {
        "label": "Cerrar campaña",
        "reason": "Campaña completamente medida y sin acciones pendientes",
        "owner_type": "supervisor",
        "urgency": "low",
    },
}

OPERATIONAL_LOOP_MODEL = {
    "stages": [
        {
            "stage": 1, "name": "Detection",
            "owner": "system",
            "input": "Serving facts (activity, lifecycle, segments)",
            "output": "Conductores identificados en queues accionables",
            "status_trigger": "DETECTED",
            "blocking_gaps": "Freshness de facts, cobertura de datos de actividad",
        },
        {
            "stage": 2, "name": "Prioritization",
            "owner": "system + supervisor",
            "input": "Queues accionables con scores",
            "output": "Conductores priorizados por urgencia y recuperabilidad",
            "status_trigger": "PRIORITIZED",
            "blocking_gaps": "Segment migration data, recoverability scoring",
        },
        {
            "stage": 3, "name": "Campaign Creation",
            "owner": "supervisor",
            "input": "Prioridades + filtros (país, ciudad, tipo)",
            "output": "Campaña creada con universo congelado",
            "status_trigger": "CAMPAIGN_DRAFT",
            "blocking_gaps": "Universo vacío, datos de teléfono insuficientes",
        },
        {
            "stage": 4, "name": "CRM Export",
            "owner": "operator",
            "input": "Campaña lista con miembros contactables",
            "output": "Lista exportada al CRM externo",
            "status_trigger": "READY_FOR_CRM",
            "blocking_gaps": "CRM no disponible, formato incorrecto",
        },
        {
            "stage": 5, "name": "Execution",
            "owner": "CRM / call center",
            "input": "Lista de conductores con teléfono y razón",
            "output": "Intentos de contacto registrados",
            "status_trigger": "IN_EXECUTION",
            "blocking_gaps": "CRM no reporta avance, equipo sin capacidad",
        },
        {
            "stage": 6, "name": "Outcome Ingest",
            "owner": "operator",
            "input": "Resultados del CRM (contactado, no responde, teléfono malo, etc.)",
            "output": "Outcomes registrados por conductor",
            "status_trigger": "OUTCOMES_RECEIVED",
            "blocking_gaps": "CRM no envía resultados, formato incompatible",
        },
        {
            "stage": 7, "name": "Follow-up",
            "owner": "operator + supervisor",
            "input": "Outcomes clasificados",
            "output": "Decisiones de segundo intento, revisión de datos, cierre",
            "status_trigger": "FOLLOW_UP_PENDING",
            "blocking_gaps": "Sin criterio claro para segundo intento",
        },
        {
            "stage": 8, "name": "Effectiveness",
            "owner": "supervisor",
            "input": "Viajes pre/post campaña por conductor",
            "output": "Cambio observado (lift), tasa de reactivación",
            "status_trigger": "MEASURED",
            "blocking_gaps": "Ventana de medición no cumplida, datos de viajes incompletos",
        },
        {
            "stage": 9, "name": "Learning Notes",
            "owner": "supervisor",
            "input": "Resultados medidos + contexto operativo",
            "output": "Decisión de repetir, pausar o cerrar",
            "status_trigger": "CLOSED",
            "blocking_gaps": "Sin revisión de supervisor",
        },
    ],
}


def get_operational_loop_model() -> dict:
    return {"status": "ok", "model": OPERATIONAL_LOOP_MODEL, "statuses": LOOP_STATUSES}


def derive_loop_status(campaign: dict, members_summary: dict = None) -> str:
    campaign_status = campaign.get("campaign_status", "DRAFT")
    crm_sync_status = campaign.get("crm_sync_status", "NOT_SYNCED")

    by_crm_status = members_summary.get("by_crm_status", {}) if members_summary else {}
    total = sum(by_crm_status.values()) if by_crm_status else 0
    pending = by_crm_status.get("PENDING", 0)
    no_response = by_crm_status.get("NO_RESPONSE", 0)
    bad_phone = by_crm_status.get("BAD_PHONE", 0)
    contacted = by_crm_status.get("CONTACTED", 0)
    returned = by_crm_status.get("RETURNED", 0)
    promised = by_crm_status.get("PROMISED_RETURN", 0)
    irrecoverable = by_crm_status.get("IRRECOVERABLE", 0)

    outcomes_received = contacted + no_response + bad_phone + returned + promised + irrecoverable
    has_effectiveness = campaign.get("_has_effectiveness", False)

    if campaign_status == "CANCELLED":
        return "CLOSED"

    if campaign_status == "COMPLETED" and has_effectiveness:
        return "MEASURED"

    if campaign_status == "COMPLETED":
        if outcomes_received > 0 and (no_response > 0 or promised > 0):
            return "FOLLOW_UP_PENDING"
        if outcomes_received > 0:
            return "MEASURED" if has_effectiveness else "OUTCOMES_RECEIVED"
        return "CLOSED"

    if campaign_status == "IN_EXECUTION":
        if outcomes_received > 0:
            return "OUTCOMES_RECEIVED"
        return "IN_EXECUTION"

    if campaign_status == "SENT_TO_CRM":
        return "SENT_TO_CRM"

    if campaign_status == "READY_FOR_CRM":
        return "READY_FOR_CRM"

    if campaign_status == "DRAFT":
        target = campaign.get("target_count", 0)
        if target > 0:
            return "CAMPAIGN_DRAFT"
        return "DETECTED"

    return "NEEDS_REVIEW"


def derive_next_human_action(campaign: dict, members_summary: dict = None) -> dict:
    loop_status = derive_loop_status(campaign, members_summary)
    by_crm_status = members_summary.get("by_crm_status", {}) if members_summary else {}
    no_response = by_crm_status.get("NO_RESPONSE", 0)
    bad_phone = by_crm_status.get("BAD_PHONE", 0)
    total = sum(by_crm_status.values()) if by_crm_status else 0

    attempts_threshold = 3

    if loop_status == "DETECTED":
        action_key = "CREATE_CAMPAIGN"
    elif loop_status == "PRIORITIZED":
        action_key = "CREATE_CAMPAIGN"
    elif loop_status == "CAMPAIGN_DRAFT":
        action_key = "EXPORT_TO_CRM"
    elif loop_status == "READY_FOR_CRM":
        action_key = "EXPORT_TO_CRM"
    elif loop_status == "SENT_TO_CRM":
        action_key = "IMPORT_OUTCOMES"
    elif loop_status == "IN_EXECUTION":
        action_key = "IMPORT_OUTCOMES"
    elif loop_status == "OUTCOMES_RECEIVED":
        if bad_phone > 0 and bad_phone > (total * 0.2):
            action_key = "REVIEW_BAD_PHONES"
        elif no_response > 0:
            action_key = "FOLLOW_UP_SECOND_ATTEMPT"
        else:
            action_key = "WAIT_MEASUREMENT_WINDOW"
    elif loop_status == "FOLLOW_UP_PENDING":
        if bad_phone > 0 and bad_phone > (total * 0.15):
            action_key = "REVIEW_BAD_PHONES"
        else:
            action_key = "FOLLOW_UP_SECOND_ATTEMPT"
    elif loop_status == "MEASURED":
        action_key = "REVIEW_EFFECTIVENESS"
    elif loop_status == "CLOSED":
        action_key = "CLOSE_CAMPAIGN"
    elif loop_status == "NEEDS_REVIEW":
        action_key = "REVIEW_EFFECTIVENESS"
    else:
        action_key = "CREATE_CAMPAIGN"

    action = NEXT_ACTIONS.get(action_key, NEXT_ACTIONS["CREATE_CAMPAIGN"]).copy()
    action["action_key"] = action_key

    blocking_gap = None
    if loop_status == "SENT_TO_CRM":
        blocking_gap = "Esperando que el CRM reporte resultados"
    elif loop_status == "IN_EXECUTION":
        blocking_gap = "Campaña en ejecución en el CRM, pendiente de outcomes"
    elif loop_status == "OUTCOMES_RECEIVED" and bad_phone > 0:
        blocking_gap = f"{bad_phone} conductores con teléfono incorrecto"

    action["blocking_gap"] = blocking_gap
    action["loop_status"] = loop_status

    return action


def derive_loop_readiness(campaign: dict, members_summary: dict = None) -> dict:
    loop_status = derive_loop_status(campaign, members_summary)
    next_action = derive_next_human_action(campaign, members_summary)

    by_crm_status = members_summary.get("by_crm_status", {}) if members_summary else {}
    total = sum(by_crm_status.values()) if by_crm_status else 0
    pending = by_crm_status.get("PENDING", 0)
    with_phone = campaign.get("with_phone_count", 0)

    depends_on_crm = loop_status in ("SENT_TO_CRM", "IN_EXECUTION")
    can_measure = loop_status in ("OUTCOMES_RECEIVED", "FOLLOW_UP_PENDING", "MEASURED")

    missing = []
    if loop_status == "CAMPAIGN_DRAFT" and with_phone == 0:
        missing.append("Sin conductores con teléfono")
    if loop_status == "READY_FOR_CRM":
        missing.append("Pendiente exportar al CRM")
    if loop_status == "SENT_TO_CRM":
        missing.append("Esperando outcomes del CRM")
    if loop_status == "OUTCOMES_RECEIVED":
        missing.append("Ventana D+7 pendiente para medir")
    if loop_status == "FOLLOW_UP_PENDING":
        missing.append("Conductores sin respuesta necesitan segundo intento")

    human_summary = _build_human_summary(loop_status, campaign, by_crm_status)

    return {
        "loop_status": loop_status,
        "loop_status_label": _status_label(loop_status),
        "current_stage": _stage_number(loop_status),
        "total_stages": 9,
        "missing": missing,
        "next_action": next_action,
        "depends_on_crm": depends_on_crm,
        "can_measure": can_measure,
        "human_summary": human_summary,
    }


def _status_label(status: str) -> str:
    labels = {
        "DETECTED": "Detectado",
        "PRIORITIZED": "Priorizado",
        "CAMPAIGN_DRAFT": "Borrador de campaña",
        "READY_FOR_CRM": "Lista para enviar al CRM",
        "SENT_TO_CRM": "Enviada al CRM",
        "IN_EXECUTION": "En ejecución",
        "OUTCOMES_RECEIVED": "Resultados recibidos",
        "FOLLOW_UP_PENDING": "Seguimiento pendiente",
        "MEASURED": "Medida",
        "CLOSED": "Cerrada",
        "NEEDS_REVIEW": "Necesita revisión",
    }
    return labels.get(status, status)


def _stage_number(status: str) -> int:
    order = {
        "DETECTED": 1, "PRIORITIZED": 2, "CAMPAIGN_DRAFT": 3,
        "READY_FOR_CRM": 4, "SENT_TO_CRM": 5, "IN_EXECUTION": 5,
        "OUTCOMES_RECEIVED": 6, "FOLLOW_UP_PENDING": 7,
        "MEASURED": 8, "CLOSED": 9, "NEEDS_REVIEW": 8,
    }
    return order.get(status, 1)


def _build_human_summary(loop_status: str, campaign: dict, by_crm_status: dict) -> str:
    name = campaign.get("campaign_name", "Campaña")
    target = campaign.get("target_count", 0)

    if loop_status == "CAMPAIGN_DRAFT":
        return f"Campaña '{name}' con {target} conductores lista para revisar y enviar al CRM"
    elif loop_status == "READY_FOR_CRM":
        return f"Lista lista para enviar al CRM"
    elif loop_status == "SENT_TO_CRM":
        return f"Esperando outcomes del CRM"
    elif loop_status == "IN_EXECUTION":
        return f"CRM ejecutando contacto"
    elif loop_status == "OUTCOMES_RECEIVED":
        return f"Ventana D+7 pendiente para medir efectividad"
    elif loop_status == "FOLLOW_UP_PENDING":
        no_resp = by_crm_status.get("NO_RESPONSE", 0)
        return f"{no_resp} conductores sin respuesta necesitan seguimiento"
    elif loop_status == "MEASURED":
        return f"Campaña medida, revisar efectividad"
    elif loop_status == "CLOSED":
        return f"Campaña cerrada"
    elif loop_status == "NEEDS_REVIEW":
        return f"Campaña necesita revisión manual"
    return f"Campaña en estado {loop_status}"


def derive_follow_up(members: list) -> list:
    follow_ups = []
    for m in members:
        crm_status = m.get("crm_status", "PENDING")
        attempts = m.get("attempts_count", 0) or 0
        driver_id = m.get("driver_id", "")
        has_trips_after = m.get("has_trips_after", False)

        if crm_status == "NO_RESPONSE" and attempts < 3:
            follow_ups.append({
                "driver_id": driver_id,
                "follow_up_type": "FOLLOW_UP_PENDING",
                "reason": f"Sin respuesta, intento {attempts + 1} de 3",
                "action": "Reintentar contacto",
            })
        elif crm_status == "BAD_PHONE":
            follow_ups.append({
                "driver_id": driver_id,
                "follow_up_type": "DATA_QUALITY_REVIEW",
                "reason": "Teléfono incorrecto, actualizar datos",
                "action": "Revisar datos de contacto",
            })
        elif crm_status == "PROMISED_RETURN" and not has_trips_after:
            follow_ups.append({
                "driver_id": driver_id,
                "follow_up_type": "FOLLOW_UP_PENDING",
                "reason": "Prometió volver pero sin viajes D+7",
                "action": "Verificar cumplimiento",
            })
        elif crm_status == "RETURNED" and has_trips_after:
            follow_ups.append({
                "driver_id": driver_id,
                "follow_up_type": "RECOVERED_OBSERVED",
                "reason": "Volvió a viajar, recuperación confirmada",
                "action": "Ninguna (éxito observado)",
            })
        elif crm_status == "IRRECOVERABLE":
            follow_ups.append({
                "driver_id": driver_id,
                "follow_up_type": "CLOSED_IRRECOVERABLE",
                "reason": "Conductor irrecuperable",
                "action": "Cerrar caso",
            })

    return follow_ups


def get_campaign_loop_status(campaign_id: str) -> dict:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT campaign_id, campaign_name, campaign_type, campaign_status,
                       crm_sync_status, target_count, with_phone_count, without_phone_count,
                       created_at, updated_at
                FROM ops.driver_campaigns WHERE campaign_id = %(id)s
            """, {"id": campaign_id})
            campaign = cur.fetchone()
            if not campaign:
                return {"status": "error", "error": "Campaign not found"}

            cur.execute("""
                SELECT crm_status, COUNT(*) as cnt
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
                GROUP BY crm_status
            """, {"id": campaign_id})
            by_status = {r["crm_status"]: r["cnt"] for r in cur.fetchall()}

            cur.execute("""
                SELECT COUNT(*) as cnt FROM ops.driver_campaign_effectiveness
                WHERE campaign_id = %(id)s
            """, {"id": campaign_id})
            eff_row = cur.fetchone()
            has_effectiveness = (eff_row["cnt"] if eff_row else 0) > 0

            campaign["_has_effectiveness"] = has_effectiveness
            members_summary = {"by_crm_status": by_status}

            for ts_field in ("created_at", "updated_at"):
                if campaign.get(ts_field):
                    campaign[ts_field] = campaign[ts_field].isoformat()

            loop_status = derive_loop_status(campaign, members_summary)
            next_action = derive_next_human_action(campaign, members_summary)
            readiness = derive_loop_readiness(campaign, members_summary)

        return {
            "status": "ok",
            "campaign_id": campaign_id,
            "campaign_name": campaign.get("campaign_name"),
            "loop_status": loop_status,
            "loop_status_label": _status_label(loop_status),
            "next_action": next_action,
            "readiness": readiness,
            "members_by_crm_status": by_status,
            "has_effectiveness": has_effectiveness,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


def get_campaign_follow_up(campaign_id: str) -> dict:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT driver_id, crm_status, latest_outcome,
                       COALESCE(
                           (evidence_snapshot::jsonb->>'attempts_count')::int, 0
                       ) as attempts_count
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
                  AND crm_status IN ('NO_RESPONSE', 'BAD_PHONE', 'PROMISED_RETURN', 'RETURNED', 'IRRECOVERABLE')
            """, {"id": campaign_id})
            members = [dict(r) for r in cur.fetchall()]

        follow_ups = derive_follow_up(members)

        summary = {}
        for f in follow_ups:
            ft = f["follow_up_type"]
            summary[ft] = summary.get(ft, 0) + 1

        return {
            "status": "ok",
            "campaign_id": campaign_id,
            "total_follow_ups": len(follow_ups),
            "by_type": summary,
            "follow_ups": follow_ups[:100],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


def get_campaign_qa_checklist(campaign_id: str) -> dict:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT campaign_id, campaign_name, target_count, with_phone_count,
                       without_phone_count, campaign_status, crm_sync_status
                FROM ops.driver_campaigns WHERE campaign_id = %(id)s
            """, {"id": campaign_id})
            campaign = cur.fetchone()
            if not campaign:
                return {"status": "error", "error": "Campaign not found"}

            cur.execute("""
                SELECT crm_status, COUNT(*) as cnt
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
                GROUP BY crm_status
            """, {"id": campaign_id})
            by_status = {r["crm_status"]: r["cnt"] for r in cur.fetchall()}
            total = sum(by_status.values())

        target = campaign["target_count"] or 0
        with_phone = campaign["with_phone_count"] or 0
        no_response = by_status.get("NO_RESPONSE", 0)
        bad_phone = by_status.get("BAD_PHONE", 0)
        returned = by_status.get("RETURNED", 0)
        irrecoverable = by_status.get("IRRECOVERABLE", 0)
        pending = by_status.get("PENDING", 0)
        contacted = by_status.get("CONTACTED", 0)
        promised = by_status.get("PROMISED_RETURN", 0)

        checklist = [
            {
                "question": "¿El universo tiene sentido?",
                "answer": "Sí" if target >= 5 else "Revisar (menos de 5 conductores)",
                "ok": target >= 5,
                "detail": f"{target} conductores en campaña",
            },
            {
                "question": "¿Hay suficientes teléfonos?",
                "answer": "Sí" if with_phone >= (target * 0.5) else "No (cobertura < 50%)",
                "ok": with_phone >= (target * 0.5) if target > 0 else False,
                "detail": f"{with_phone}/{target} con teléfono ({round(with_phone * 100 / max(1, target))}%)",
            },
            {
                "question": "¿La prioridad está bien?",
                "answer": "Revisión manual requerida",
                "ok": None,
                "detail": "Verificar que los conductores priorizados corresponden al objetivo",
            },
            {
                "question": "¿El CRM recibió la lista?",
                "answer": "Sí" if campaign["crm_sync_status"] in ("SYNCED", "PARTIAL") else "No",
                "ok": campaign["crm_sync_status"] in ("SYNCED", "PARTIAL"),
                "detail": f"Estado CRM: {campaign['crm_sync_status']}",
            },
            {
                "question": "¿Se registraron outcomes?",
                "answer": "Sí" if (total - pending) > 0 else "No",
                "ok": (total - pending) > 0,
                "detail": f"{total - pending}/{total} con resultado",
            },
            {
                "question": "¿Cuántos necesitan segundo intento?",
                "answer": str(no_response + promised),
                "ok": None,
                "detail": f"Sin respuesta: {no_response}, Prometió volver: {promised}",
            },
            {
                "question": "¿Cuántos volvieron a viajar?",
                "answer": str(returned),
                "ok": returned > 0 if (contacted + returned) > 0 else None,
                "detail": f"{returned} conductores con viajes post-contacto",
            },
            {
                "question": "¿Cuántos son irrecuperables?",
                "answer": str(irrecoverable),
                "ok": None,
                "detail": f"{irrecoverable} marcados como irrecuperables",
            },
            {
                "question": "¿Se debe repetir campaña?",
                "answer": "Evaluar" if no_response > (total * 0.3) else "No necesario",
                "ok": None,
                "detail": f"Tasa sin respuesta: {round(no_response * 100 / max(1, total))}%",
            },
        ]

        return {
            "status": "ok",
            "campaign_id": campaign_id,
            "campaign_name": campaign["campaign_name"],
            "checklist": checklist,
            "summary": {
                "total_checks": len(checklist),
                "passed": sum(1 for c in checklist if c["ok"] is True),
                "failed": sum(1 for c in checklist if c["ok"] is False),
                "manual_review": sum(1 for c in checklist if c["ok"] is None),
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


def get_operating_board() -> dict:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT c.campaign_id, c.campaign_name, c.campaign_type,
                       c.campaign_status, c.crm_sync_status,
                       c.target_count, c.with_phone_count,
                       c.country, c.city, c.created_at, c.updated_at,
                       COALESCE(
                           (SELECT COUNT(*) FROM ops.driver_campaign_effectiveness e
                            WHERE e.campaign_id = c.campaign_id), 0
                       ) as effectiveness_count
                FROM ops.driver_campaigns c
                WHERE c.campaign_status != 'CANCELLED'
                ORDER BY c.updated_at DESC
                LIMIT 200
            """)
            campaigns = cur.fetchall()

            cur.execute("""
                SELECT campaign_id, crm_status, COUNT(*) as cnt
                FROM ops.driver_campaign_members
                GROUP BY campaign_id, crm_status
            """)
            member_rows = cur.fetchall()

        member_map = {}
        for r in member_rows:
            cid = str(r["campaign_id"])
            if cid not in member_map:
                member_map[cid] = {}
            member_map[cid][r["crm_status"]] = r["cnt"]

        groups = {
            "ready_for_crm": [],
            "in_execution": [],
            "waiting_outcomes": [],
            "follow_up_needed": [],
            "waiting_measurement": [],
            "measured": [],
            "needs_review": [],
        }

        for c in campaigns:
            cid = str(c["campaign_id"])
            by_status = member_map.get(cid, {})
            c["_has_effectiveness"] = (c.get("effectiveness_count", 0) or 0) > 0
            members_summary = {"by_crm_status": by_status}
            loop_status = derive_loop_status(dict(c), members_summary)

            for ts_field in ("created_at", "updated_at"):
                if c.get(ts_field):
                    c[ts_field] = c[ts_field].isoformat()

            item = {
                "campaign_id": cid,
                "campaign_name": c["campaign_name"],
                "campaign_type": c["campaign_type"],
                "loop_status": loop_status,
                "loop_status_label": _status_label(loop_status),
                "target_count": c["target_count"],
                "with_phone_count": c["with_phone_count"],
                "country": c.get("country"),
                "city": c.get("city"),
                "next_action": derive_next_human_action(dict(c), members_summary),
                "updated_at": c.get("updated_at"),
            }

            if loop_status in ("CAMPAIGN_DRAFT", "READY_FOR_CRM"):
                groups["ready_for_crm"].append(item)
            elif loop_status in ("SENT_TO_CRM", "IN_EXECUTION"):
                groups["in_execution"].append(item)
            elif loop_status == "OUTCOMES_RECEIVED":
                groups["waiting_outcomes"].append(item)
            elif loop_status == "FOLLOW_UP_PENDING":
                groups["follow_up_needed"].append(item)
            elif loop_status == "MEASURED":
                groups["measured"].append(item)
            elif loop_status == "NEEDS_REVIEW":
                groups["needs_review"].append(item)
            else:
                groups["waiting_measurement"].append(item)

        total_active = sum(len(v) for v in groups.values())

        return {
            "status": "ok",
            "total_active_campaigns": total_active,
            "groups": groups,
            "group_counts": {k: len(v) for k, v in groups.items()},
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300], "groups": {}, "group_counts": {}}
