"""
YEGO Lima Growth — Control Loop Auto-Sync Service (LG-CTRL-HOTFIX-1E)

Syncs assignment_queue READY drivers to control_loop_state.
Only inserts NEW drivers with state='READY'. Never overwrites advanced states.
Using existing table schema (id uuid PK, driver_profile_id text).
"""
from __future__ import annotations

import logging
from typing import Any, Dict
from uuid import uuid4

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_QUEUE = "growth.yego_lima_assignment_queue"
TABLE_CL = "growth.yego_lima_control_loop_state"


def sync_assignment_queue_to_control_loop(date_str: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE_CL} "
            f"(id, driver_profile_id, current_state, previous_state, "
            f" state_changed_at, created_at, updated_at) "
            f"SELECT gen_random_uuid(), q.driver_id, 'READY', NULL, "
            f" now(), now(), now() "
            f"FROM {TABLE_QUEUE} q "
            f"WHERE q.assignment_date = %(d)s "
            f"  AND q.queue_status = 'READY' "
            f"  AND q.driver_id IS NOT NULL "
            f"  AND NOT EXISTS ("
            f"    SELECT 1 FROM {TABLE_CL} cl "
            f"    WHERE cl.driver_profile_id = q.driver_id "
            f"      AND cl.created_at::date = %(d)s::date"
            f"  )",
            {"d": date_str}
        )
        inserted = cur.rowcount

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_CL} "
            f"WHERE current_state = 'READY' AND created_at::date = %(d)s::date",
            {"d": date_str}
        )
        total_ready = cur.fetchone()[0] or 0

        conn.commit()

    result = {
        "date": date_str,
        "inserted": inserted,
        "skipped": total_ready - inserted if total_ready > 0 else 0,
        "total_ready": total_ready,
    }
    logger.info("Control loop sync %s: inserted=%d skipped=%d total=%d",
                date_str, inserted, result["skipped"], total_ready)
    return result
