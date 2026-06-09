"""
YEGO Lima Growth — Today's Action Plan Service (LG-UX-R2.6)
Deterministic rules. No AI. Uses existing operational data.
"""
from __future__ import annotations
import logging
from typing import Any, Dict
from app.db.connection import get_db
from app.services.yego_lima_program_display_service import get_display_name

logger = logging.getLogger(__name__)


def get_todays_action_plan(date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        # 1. Get operational truth for NOT_GENERATED detection
        kpi_status = {}
        kpi_checks = [
            ("eligible_total", "growth.yango_lima_program_eligibility_daily", "eligibility_date"),
            ("prioritized_total", "growth.yango_lima_prioritized_opportunity_daily", "opportunity_date"),
            ("actionable_today", "growth.yango_lima_prioritized_opportunity_daily", "opportunity_date", "is_actionable_today = true"),
            ("queue_total", "growth.yego_lima_assignment_queue", "assignment_date"),
        ]
        not_generated = 0
        for key, table, col, *filt in kpi_checks:
            f = f" AND {filt[0]}" if filt else ""
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = %(d)s{f}", {"d": date})
                cnt = cur.fetchone()[0] or 0
                cur.execute(f"SELECT MAX({col}) FROM {table}")
                latest = str(cur.fetchone()[0]) if cur.fetchone()[0] else None
                kpi_status[key] = cnt
                if cnt == 0 and latest and latest < date:
                    not_generated += 1
            except Exception:
                kpi_status[key] = -1

        # 2. Queue status
        cur.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN queue_status = 'EXPORTED' THEN 1 ELSE 0 END)
            FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s
        """, {"d": date})
        q = cur.fetchone()
        queue_total = q[0] or 0
        queue_ready = q[1] or 0
        queue_held = q[2] or 0
        queue_exported = q[3] or 0

        # 3. Capacity
        cur.execute("SELECT daily_action_capacity FROM growth.yango_lima_opportunity_policy_config WHERE is_active = true LIMIT 1")
        cap_row = cur.fetchone()
        capacity = cap_row[0] if cap_row else 500

        # 4. Per-program data
        programs = []

        for prog in ["PROGRAM_CHURN_PREVENTION", "PROGRAM_ACTIVE_GROWTH", "PROGRAM_14_90", "PROGRAM_HIGH_VALUE_RECOVERY"]:
            name = get_display_name(prog)
            cur.execute("""
                SELECT COUNT(*) FROM growth.yango_lima_program_eligibility_daily
                WHERE program_code = %(p)s AND eligibility_date = %(d)s AND eligible_flag = true
            """, {"p": prog, "d": date})
            eligible = cur.fetchone()[0] or 0
            cur.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END)
                FROM growth.yango_lima_prioritized_opportunity_daily
                WHERE selected_program_code = %(p)s AND opportunity_date = %(d)s
            """, {"p": prog, "d": date})
            pr = cur.fetchone()
            prioritized = pr[0] or 0
            actionable = pr[1] or 0
            cur.execute("""
                SELECT COUNT(*), SUM(CASE WHEN queue_status='READY' THEN 1 ELSE 0 END)
                FROM growth.yego_lima_assignment_queue
                WHERE program_code = %(p)s AND assignment_date = %(d)s
            """, {"p": prog, "d": date})
            qr = cur.fetchone()
            pg_queue = qr[0] or 0

            if eligible == 0 and not_generated > 0:
                pstatus = "NOT_GENERATED"
            elif pg_queue == 0 and eligible > 0:
                pstatus = "NEEDS_QUEUE"
            elif pg_queue > 0 and queue_ready > 0:
                pstatus = "HEALTHY"
            else:
                pstatus = "WARNING"

            programs.append({
                "program_code": prog,
                "program_name": name,
                "status": pstatus,
                "eligible": eligible,
                "prioritized": prioritized,
                "actionable": actionable,
                "queue": pg_queue,
                "recommended_take": min(actionable, capacity) if actionable > 0 and pg_queue == 0 else 0,
            })

        # 5. Determine overall status
        if not_generated >= 3:
            status = "NEEDS_PIPELINE"
            headline = "Ejecutar pipeline diario"
            next_action = {"code": "RUN_PIPELINE", "label": "Ejecutar Pipeline", "reason": "No hay datos generados para hoy."}
        elif kpi_status.get("prioritized_total", 0) > 0 and queue_total == 0:
            status = "NEEDS_QUEUE"
            headline = "Construir cola de asignacion"
            next_action = {"code": "BUILD_QUEUE", "label": "Construir Cola", "reason": f"Hay {kpi_status['prioritized_total']} priorizados sin cola."}
        elif queue_ready > 0:
            status = "READY_TO_EXPORT"
            headline = f"Exportar {queue_ready} contactos READY"
            next_action = {"code": "EXPORT_READY", "label": "Exportar READY", "reason": f"{queue_ready} listos para exportar."}
        elif queue_exported > 0:
            status = "COMPLETE"
            headline = "Ciclo operativo completado"
            next_action = {"code": "NONE", "label": "Revisar configuracion", "reason": "El ciclo de hoy ya fue ejecutado."}
        else:
            status = "WARNING"
            headline = "Verificar estado operacional"
            next_action = {"code": "REVIEW_WARNINGS", "label": "Revisar Warnings", "reason": "Estado parcial. Revisar warnings."}

        warnings = []
        if queue_held > 0:
            warnings.append(f"{queue_held} drivers retenidos (HELD)")
        if not_generated > 0:
            warnings.append(f"{not_generated} capas NOT_GENERATED")

    return {
        "date": date,
        "status": status,
        "headline": headline,
        "summary": headline,
        "next_action": next_action,
        "capacity": {
            "daily_action_capacity": capacity,
            "queue_ready": queue_ready,
            "coverage_rate": round(queue_ready / capacity, 2) if capacity > 0 else 0,
            "gap": max(0, capacity - queue_ready),
        },
        "programs": programs,
        "queue": {
            "ready": queue_ready,
            "held": queue_held,
            "exported": queue_exported,
            "pending": max(0, (kpi_status.get("prioritized_total", 0) or 0) - queue_total),
        },
        "warnings": warnings,
    }
