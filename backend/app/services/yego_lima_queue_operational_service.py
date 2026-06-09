"""
YEGO Lima Growth — Queue Operational Summary Service (LG-UX-R2.5)
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_QUEUE = "growth.yego_lima_assignment_queue"
TABLE_BUILD_LOG = "growth.yego_lima_queue_build_log"


def get_queue_operational_summary(date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        # Totals
        cur.execute(f"""
            SELECT COUNT(*),
                   SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN queue_status = 'EXPORTED' THEN 1 ELSE 0 END)
            FROM {TABLE_QUEUE} WHERE assignment_date = %(d)s
        """, {"d": date})
        r = cur.fetchone()
        queue_total = r[0] or 0
        ready = r[1] or 0
        held = r[2] or 0
        exported = r[3] or 0

        # By program
        cur.execute(f"""
            SELECT program_code, COUNT(*),
                   SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END)
            FROM {TABLE_QUEUE} WHERE assignment_date = %(d)s
            GROUP BY program_code ORDER BY COUNT(*) DESC
        """, {"d": date})
        by_program = [{"program": r[0], "total": r[1], "ready": r[2], "held": r[3]} for r in cur.fetchall()]

        # By channel
        cur.execute(f"""
            SELECT COALESCE(assigned_channel, 'UNASSIGNED'), COUNT(*)
            FROM {TABLE_QUEUE} WHERE assignment_date = %(d)s
            GROUP BY assigned_channel ORDER BY COUNT(*) DESC
        """, {"d": date})
        by_channel = [{"channel": r[0], "count": r[1]} for r in cur.fetchall()]

        # Last build
        last_build = None
        cur.execute(f"""
            SELECT assignment_batch_id, mode, created_count, ready_count, held_count,
                   override_reason, created_at
            FROM {TABLE_BUILD_LOG}
            WHERE assignment_date = %(d)s
            ORDER BY created_at DESC LIMIT 1
        """, {"d": date})
        r = cur.fetchone()
        if r:
            last_build = {
                "assignment_batch_id": str(r[0]),
                "mode": r[1],
                "created_count": r[2],
                "ready_count": r[3],
                "held_count": r[4],
                "override_reason": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
            }

        # Capacity context
        cur.execute("SELECT daily_action_capacity FROM growth.yango_lima_opportunity_policy_config WHERE is_active = true LIMIT 1")
        cap_row = cur.fetchone()
        capacity = cap_row[0] if cap_row else 0
        coverage = round(ready / capacity, 2) if capacity > 0 else 0

        # Warnings
        warnings = []
        if ready > capacity:
            warnings.append({"type": "CAPACITY_EXCEEDED", "message": f"READY ({ready}) exceeds capacity ({capacity})"})
        if held > 0:
            warnings.append({"type": "HELD_DRIVERS", "message": f"{held} drivers HELD (missing phone or channel)"})

        # Export info
        cur.execute(f"""
            SELECT COUNT(DISTINCT campaign_id_external), SUM(CASE WHEN exported_at IS NOT NULL THEN 1 ELSE 0 END)
            FROM {TABLE_QUEUE}
            WHERE assignment_date = %(d)s AND queue_status = 'EXPORTED'
        """, {"d": date})
        exp_r = cur.fetchone()
        campaigns = exp_r[0] or 0

    return {
        "date": date,
        "queue_total": queue_total,
        "ready": ready,
        "held": held,
        "exported": exported,
        "by_program": by_program,
        "by_channel": by_channel,
        "last_build": last_build,
        "capacity_context": {
            "capacity_total": capacity,
            "daily_action_capacity": capacity,
            "coverage_rate": coverage,
        },
        "export_context": {
            "campaigns_exported": campaigns,
        },
        "warnings": warnings,
    }
