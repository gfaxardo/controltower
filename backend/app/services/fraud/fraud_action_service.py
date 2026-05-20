"""Fase 1F — Action Service.

Genera payload de acciones futuras y registra audit log.
NO ejecuta API externa real. Soporta solo preview y manual-log.
"""
from datetime import datetime
from app.db.connection import get_db
from psycopg2.extras import Json

ACTION_TYPES = [
    "disable_autocobro",
    "enable_autocobro",
    "disconnect_driver",
    "reconnect_driver",
    "hold_bonus",
    "release_bonus",
    "mark_trusted",
    "mark_restricted",
]


def preview_action(driver_id, park_id=None, case_id=None, action_type=None, reason=None, actor=None):
    """Genera preview de accion. NO ejecuta accion externa. Registra audit log."""
    if action_type not in ACTION_TYPES:
        raise ValueError(f"action_type invalido: {action_type}. Permitidos: {ACTION_TYPES}")

    payload = {
        "driver_id": driver_id,
        "park_id": park_id,
        "action_type": action_type,
        "reason": reason or {},
        "mode": "preview",
        "external_execution": False,
    }

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fraud.action_audit_log
                (case_id, driver_id, park_id, action_type, action_mode, action_status,
                 payload, result, created_by, created_at)
            VALUES (%s, %s, %s, %s, 'preview', 'previewed', %s, %s, %s, now())
            RETURNING id
        """, (
            case_id, driver_id, park_id, action_type,
            Json(payload),
            Json({"status": "previewed", "message": "Accion no ejecutada - solo preview"}),
            actor or "system",
        ))
        r = cur.fetchone()
        conn.commit()
        cur.close()

    return {
        "audit_id": r[0] if r else None,
        "action_type": action_type,
        "mode": "preview",
        "status": "previewed",
        "payload": payload,
        "warning": "Esta accion NO fue ejecutada. Es solo un preview.",
    }


def manual_log_action(driver_id, park_id=None, case_id=None, action_type=None,
                      result=None, comment=None, actor=None):
    """Registra una accion ya ejecutada manualmente fuera del sistema."""
    if action_type not in ACTION_TYPES:
        raise ValueError(f"action_type invalido: {action_type}")

    payload = {
        "driver_id": driver_id,
        "park_id": park_id,
        "action_type": action_type,
        "result": result,
        "comment": comment,
        "mode": "manual",
    }

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fraud.action_audit_log
                (case_id, driver_id, park_id, action_type, action_mode, action_status,
                 payload, result, created_by, created_at)
            VALUES (%s, %s, %s, %s, 'manual', 'executed', %s, %s, %s, now())
            RETURNING id
        """, (
            case_id, driver_id, park_id, action_type,
            Json(payload),
            Json({"status": "executed", "message": "Registrada como accion manual externa"}),
            actor or "system",
        ))
        r = cur.fetchone()
        conn.commit()
        cur.close()

    return {
        "audit_id": r[0] if r else None,
        "action_type": action_type,
        "mode": "manual",
        "status": "executed",
        "payload": payload,
    }
