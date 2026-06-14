"""
YEGO Lima Growth — Control Loop Auto-Sync Service

Original: sync_assignment_queue_to_control_loop (LG-CTRL-HOTFIX-1E)
New: sync_exclusive_worklist_to_control_loop (LG-PROG-EXCL-1F)

Syncs exportable drivers from exclusive_driver_worklist_daily
to control_loop_state using INSERT with NOT EXISTS guard.
Excludes Cemetery, Protected, No Data. Dry-run mode by default.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_QUEUE = "growth.yego_lima_assignment_queue"
TABLE_CL = "growth.yego_lima_control_loop_state"
TABLE_WORKLIST = "growth.yango_lima_exclusive_driver_worklist_daily"

DO_NOT_SYNC = {"CEMETERY_LONG_CHURNED", "PROTECTED_ALREADY_MEETING_GOAL", "NO_DATA_OR_NO_ACTION"}


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


def sync_exclusive_worklist_to_control_loop(
    generated_date: Optional[str] = None,
    dry_run: bool = True,
    assigned_universe_v1: Optional[str] = None,
    limit: Optional[int] = None,
    export_batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    if export_batch_id is None:
        export_batch_id = str(uuid4())

    with get_db() as conn:
        cur = conn.cursor()

        if generated_date is None:
            cur.execute(f"SELECT MAX(generated_date) FROM {TABLE_WORKLIST}")
            row = cur.fetchone()
            generated_date = str(row[0]) if row and row[0] else None

        if not generated_date:
            return {"ok": False, "error": "No worklist data found", "dry_run": dry_run}

        where = ["generated_date = %(d)s", "export_to_control_loop = true"]
        params = {"d": generated_date}
        if assigned_universe_v1:
            where.append("assigned_universe_v1 = %(u)s")
            params["u"] = assigned_universe_v1
        where_clause = " AND ".join(where)

        cur.execute(
            f"SELECT assigned_universe_v1, COUNT(*) FROM {TABLE_WORKLIST} "
            f"WHERE {where_clause} GROUP BY assigned_universe_v1 ORDER BY COUNT(*) DESC",
            params,
        )
        by_universe = [{"universe": r[0], "candidates": r[1]} for r in cur.fetchall()]

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_WORKLIST} WHERE {where_clause}", params)
        candidate_rows = cur.fetchone()[0]

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_CL} "
            f"WHERE created_at::date = %(d)s::date "
            f"AND program_code IS NOT NULL "
            f"AND program_code NOT IN ('CEMETERY_LONG_CHURNED', 'PROTECTED_ALREADY_MEETING_GOAL', 'NO_DATA_OR_NO_ACTION')",
            {"d": generated_date},
        )
        already_existing = cur.fetchone()[0]

        cur.execute(
            f"SELECT assigned_universe_v1, COUNT(*) FROM {TABLE_WORKLIST} "
            f"WHERE generated_date = %(d)s AND export_to_control_loop = true "
            f"AND assigned_universe_v1 IN ('CEMETERY_LONG_CHURNED','PROTECTED_ALREADY_MEETING_GOAL','NO_DATA_OR_NO_ACTION') "
            f"GROUP BY assigned_universe_v1",
            {"d": generated_date},
        )
        bad_rows = cur.fetchall()

        result = {
            "dry_run": dry_run,
            "generated_date": generated_date,
            "export_batch_id": export_batch_id,
            "candidate_rows": candidate_rows,
            "already_existing_rows": already_existing,
            "by_universe": by_universe,
            "do_not_sync_violations": [{"universe": r[0], "count": r[1]} for r in bad_rows] if bad_rows else [],
        }

        if dry_run:
            return result

        if bad_rows:
            result["ok"] = False
            result["error"] = "Do-Not-Sync universes in candidates. Aborting."
            return result

        limit_sql = f"LIMIT {int(limit)}" if limit else ""

        cur.execute(
            f"INSERT INTO {TABLE_CL} "
            f"(id, driver_profile_id, current_state, program_code, notes, "
            f" campaign_id_external, created_at, updated_at) "
            f"SELECT gen_random_uuid(), w.driver_profile_id, 'READY', "
            f" w.assigned_universe_v1, "
            f" COALESCE(w.reason_text, w.reason_code), "
            f" %(batch)s, "
            f" now(), now() "
            f"FROM {TABLE_WORKLIST} w "
            f"WHERE w.{where_clause} "
            f"  AND NOT EXISTS ("
            f"    SELECT 1 FROM {TABLE_CL} cl "
            f"    WHERE cl.driver_profile_id = w.driver_profile_id "
            f"      AND cl.created_at::date = %(d)s::date "
            f"      AND cl.program_code = w.assigned_universe_v1"
            f"  ) "
            f"ORDER BY w.priority_rank, w.driver_profile_id "
            f"{limit_sql}",
            {**params, "batch": export_batch_id},
        )
        inserted = cur.rowcount
        conn.commit()

        result["ok"] = True
        result["inserted_rows"] = inserted
        result["skipped_existing"] = max(0, candidate_rows - already_existing - inserted)

        logger.info("Worklist CL sync: batch=%s date=%s candidates=%d inserted=%d",
                     export_batch_id, generated_date, candidate_rows, inserted)
        return result
