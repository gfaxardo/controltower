"""
Queue Operational Summary Service — LG-UX-R2.5

Lightweight summary endpoint for Execution Queue.
Returns totals, breakdowns, hold reasons, export summary.
Does NOT return full driver list.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.services.freshness_service import compute_freshness

logger = logging.getLogger(__name__)


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


def get_queue_summary(date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check if queue exists for this date
        cur.execute(
            "SELECT COUNT(*) as cnt FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s",
            {"d": date},
        )
        exists = _safe_int(cur.fetchone()["cnt"]) > 0

        if not exists:
            return {
                "date": date,
                "status": "NOT_BUILT",
                "totals": {"ready": 0, "held": 0, "exported": 0, "total": 0, "not_built": 1},
                "by_program": [],
                "by_channel": [],
                "hold_reasons": [],
                "export_summary": {"last_export_at": None, "campaigns_count": 0, "contacts_sent": 0, "contacts_inserted": 0, "failed_count": 0},
                "freshness": compute_freshness("assignment_queue", None, "growth.yango_lima_assignment_queue"),
                "explanation": "La cola no ha sido construida para esta fecha. Usa 'Construir Cola' para generarla.",
                "remediation": "POST /assignment-queue/build para generar la cola del dia.",
            }

        # Totals
        cur.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) as ready, "
            "SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END) as held "
            "FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s",
            {"d": date},
        )
        totals_row = cur.fetchone()
        total = _safe_int(totals_row["total"])
        ready = _safe_int(totals_row["ready"])
        held = _safe_int(totals_row["held"])

        # By program
        cur.execute(
            "SELECT program_code, COUNT(*) as total, "
            "SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) as ready, "
            "SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END) as held "
            "FROM growth.yango_lima_assignment_queue WHERE assignment_date = %(d)s "
            "GROUP BY program_code ORDER BY total DESC",
            {"d": date},
        )
        by_program = [dict(r) for r in cur.fetchall()]

        # By channel
        cur.execute(
            "SELECT assigned_channel as channel, COUNT(*) as total, "
            "SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) as ready, "
            "SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END) as held "
            "FROM growth.yango_lima_assignment_queue WHERE assignment_date = %(d)s "
            "GROUP BY assigned_channel ORDER BY total DESC",
            {"d": date},
        )
        by_channel = [dict(r) for r in cur.fetchall()]

        # Hold reasons
        hold_reasons = []
        if held > 0:
            cur.execute(
                "SELECT COUNT(*) as cnt FROM growth.yango_lima_assignment_queue "
                "WHERE assignment_date = %(d)s AND queue_status = 'HELD' AND (phone IS NULL OR phone = '')",
                {"d": date},
            )
            no_phone = _safe_int(cur.fetchone()["cnt"])
            if no_phone > 0:
                hold_reasons.append({"reason": "Sin telefono", "count": no_phone, "remediation": "Verificar datos de contacto del conductor"})

            cur.execute(
                "SELECT COUNT(*) as cnt FROM growth.yango_lima_assignment_queue "
                "WHERE assignment_date = %(d)s AND queue_status = 'HELD' AND (assigned_channel IS NULL OR assigned_channel = 'UNASSIGNED')",
                {"d": date},
            )
            no_channel = _safe_int(cur.fetchone()["cnt"])
            if no_channel > 0:
                hold_reasons.append({"reason": "Sin canal asignado", "count": no_channel, "remediation": "Ejecutar channel allocation para asignar canales"})

        # Export summary
        cur.execute(
            "SELECT MAX(exported_at) as last_export_at, COUNT(*) as campaigns, "
            "SUM(contacts_sent) as sent, SUM(contacts_inserted) as inserted, "
            "SUM(CASE WHEN export_status = 'failed' THEN 1 ELSE 0 END) as failed "
            "FROM growth.yango_lima_loopcontrol_campaign_export "
            "WHERE opportunity_date = %(d)s",
            {"d": date},
        )
        export_row = cur.fetchone()

        exported = _safe_int(export_row["campaigns"]) if export_row else 0

        # Determine status
        if total == 0:
            status = "EMPTY"
        elif ready > 0:
            status = "READY"
        elif held > 0:
            status = "HELD"
        elif exported > 0:
            status = "EXPORTED"
        else:
            status = "UNKNOWN"

    return {
        "date": date,
        "status": status,
        "totals": {
            "ready": ready,
            "held": held,
            "exported": exported,
            "total": total,
            "not_built": 0,
        },
        "by_program": by_program,
        "by_channel": by_channel,
        "hold_reasons": hold_reasons,
        "export_summary": {
            "last_export_at": str(export_row["last_export_at"]) if export_row and export_row["last_export_at"] else None,
            "campaigns_count": exported,
            "contacts_sent": _safe_int(export_row["sent"]) if export_row else 0,
            "contacts_inserted": _safe_int(export_row["inserted"]) if export_row else 0,
            "failed_count": _safe_int(export_row["failed"]) if export_row else 0,
        },
        "freshness": compute_freshness("assignment_queue", None, "growth.yango_lima_assignment_queue"),
        "explanation": _build_explanation(status, ready, held, exported, total),
        "remediation": _build_remediation(status),
    }


def _build_explanation(status: str, ready: int, held: int, exported: int, total: int) -> str:
    if status == "EMPTY":
        return "La cola fue construida pero no contiene registros para esta fecha."
    if status == "NOT_BUILT":
        return "La cola no ha sido construida para esta fecha."
    if status == "READY":
        return f"Hay {ready} conductores listos para exportar, {held} retenidos. Total en cola: {total}."
    if status == "HELD":
        return f"Todos los {held} conductores estan retenidos. Revisa las razones de retencion."
    if status == "EXPORTED":
        return f"Se exportaron {exported} campanas. La cola esta procesada para esta fecha."
    return "Estado de cola indeterminado."


def _build_remediation(status: str) -> Optional[str]:
    if status == "NOT_BUILT":
        return "Usa el boton 'Construir Cola' para generar la cola del dia."
    if status == "EMPTY":
        return "Verifica que haya conductores accionables y ejecuta 'Construir Cola' de nuevo."
    if status == "HELD":
        return "Revisa las razones de retencion: telefonos faltantes o canales no asignados."
    if status == "READY":
        return "Usa 'Exportar READY' para enviar a LoopControl."
    return None
