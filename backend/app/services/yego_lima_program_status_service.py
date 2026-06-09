"""
YEGO Lima Growth — Program Operational Status Service (LG-UX-R2.4)

Returns per-program operational status with full pipeline visibility.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from app.db.connection import get_db

logger = logging.getLogger(__name__)

PROGRAMS = ["PROGRAM_CHURN_PREVENTION", "PROGRAM_ACTIVE_GROWTH", "PROGRAM_14_90", "PROGRAM_HIGH_VALUE_RECOVERY"]


def get_program_operational_status(date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        programs = []

        for prog in PROGRAMS:
            # Eligible
            cur.execute("""
                SELECT COUNT(*) FROM growth.yango_lima_program_eligibility_daily
                WHERE program_code = %(p)s AND eligibility_date = %(d)s AND eligible_flag = true
            """, {"p": prog, "d": date})
            eligible = cur.fetchone()[0] or 0

            # Prioritized
            cur.execute("""
                SELECT COUNT(*), SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END)
                FROM growth.yango_lima_prioritized_opportunity_daily
                WHERE selected_program_code = %(p)s AND opportunity_date = %(d)s
            """, {"p": prog, "d": date})
            pri_row = cur.fetchone()
            prioritized = pri_row[0] or 0
            actionable = pri_row[1] or 0

            # Queue
            cur.execute("""
                SELECT COUNT(*),
                       SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END)
                FROM growth.yego_lima_assignment_queue
                WHERE program_code = %(p)s AND assignment_date = %(d)s
            """, {"p": prog, "d": date})
            q_row = cur.fetchone()
            queue_total = q_row[0] or 0
            queue_ready = q_row[1] or 0
            queue_held = q_row[2] or 0

            # Exported
            cur.execute("""
                SELECT COUNT(*) FROM growth.yego_lima_assignment_queue
                WHERE program_code = %(p)s AND queue_status = 'EXPORTED'
            """, {"p": prog})
            exported = cur.fetchone()[0] or 0

            # Latest data date
            cur.execute("""
                SELECT MAX(eligibility_date) FROM growth.yango_lima_program_eligibility_daily
                WHERE program_code = %(p)s
            """, {"p": prog})
            latest_date = cur.fetchone()[0]

            # Determine status
            latest_str = str(latest_date) if latest_date else None
            
            if eligible == 0 and latest_str and latest_str < date:
                status = "NOT_GENERATED"
                explanation = f"No se ha generado para {date}. Ultima fecha: {latest_str}."
                operational = "WARNING"
            elif eligible == 0:
                status = "EMPTY"
                explanation = "No hay conductores elegibles para este programa."
                operational = "WARNING"
            elif queue_total == 0 and eligible > 0:
                status = "NO_QUEUE"
                explanation = f"Hay {eligible} elegibles pero la cola no se ha construido."
                operational = "WARNING"
            elif eligible > 0 and prioritized > 0 and queue_total > 0:
                status = "HEALTHY"
                explanation = "Pipeline completo: elegibles, priorizados, y en cola."
                operational = "HEALTHY"
            elif exported > 0:
                status = "EXPORTED"
                explanation = f"Programa con {exported} conductores exportados."
                operational = "HEALTHY"
            else:
                status = "WARNING"
                explanation = "Estado parcial. Verificar pipeline."
                operational = "WARNING"

            programs.append({
                "program_code": prog,
                "program_name": prog.replace("PROGRAM_", "").replace("_", " ").title(),
                "eligible_total": eligible,
                "prioritized_total": prioritized,
                "actionable_today": actionable,
                "queue_total": queue_total,
                "queue_ready": queue_ready,
                "queue_held": queue_held,
                "exported_total": exported,
                "latest_data_date": latest_str,
                "freshness_status": status,
                "operational_status": operational,
                "explanation": explanation,
                "recommended_action": "Ejecutar pipeline diario" if status == "NOT_GENERATED" else (
                    "Construir cola de asignacion" if status == "NO_QUEUE" else None
                ),
            })

        # Sort: CRITICAL first
        severity = {"CRITICAL": 0, "WARNING": 1, "HEALTHY": 2}
        programs.sort(key=lambda p: severity.get(p["operational_status"], 3))

        # Summary counts
        healthy = sum(1 for p in programs if p["operational_status"] == "HEALTHY")
        warning = sum(1 for p in programs if p["operational_status"] == "WARNING")
        critical = sum(1 for p in programs if p["operational_status"] == "CRITICAL")

    return {
        "date": date,
        "programs": programs,
        "total_programs": len(programs),
        "healthy": healthy,
        "warning": warning,
        "critical": critical,
    }
