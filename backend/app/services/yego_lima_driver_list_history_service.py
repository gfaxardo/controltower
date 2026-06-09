"""
YEGO Lima Growth — Driver List History Service (LG-INFRA-R1.5)

Records an immutable trace of every driver's presence in operational lists.
Never deletes. Never overwrites exported records.
"""
from __future__ import annotations

import json
import logging
from datetime import date as DateType, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_HISTORY = "growth.yego_lima_driver_list_history"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"


def _now():
    return datetime.now(timezone.utc)


def snapshot_queue_to_history(
    action_date: str,
    source_run_id: Optional[str] = None,
    policy_id: Optional[str] = None,
    policy_version: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Copy all queue entries for action_date into the immutable history table.
    Idempotent per (action_date, driver_profile_id, queue_id).
    """
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(f"""
            INSERT INTO {TABLE_HISTORY} (
                action_date, operational_data_date, driver_profile_id,
                program_code, program_name, priority_rank, queue_status,
                assigned_channel, queue_id, campaign_id_external,
                export_batch_id, assignment_batch_id, exported_at,
                action_status, source_run_id, policy_id, policy_version,
                snapshot_date, evidence_json
            )
            SELECT
                assignment_date,
                assignment_date,
                driver_id,
                program_code,
                program_name,
                priority_rank,
                queue_status,
                assigned_channel,
                id,
                campaign_id_external,
                export_batch_id,
                assignment_batch_id,
                exported_at,
                CASE
                    WHEN queue_status = 'EXPORTED' THEN 'EXPORTED'
                    WHEN queue_status = 'READY' THEN 'QUEUED'
                    WHEN queue_status = 'HELD' THEN 'HELD'
                    ELSE queue_status
                END,
                %(rid)s::uuid,
                %(pid)s::uuid,
                %(pver)s::integer,
                assignment_date,
                jsonb_build_object(
                    'snapshot_ts', now(),
                    'source', 'queue_snapshot',
                    'run_id', %(rid)s
                )
            FROM {TABLE_QUEUE}
            WHERE assignment_date = %(d)s
            ON CONFLICT (action_date, driver_profile_id, queue_id) DO UPDATE SET
                queue_status = EXCLUDED.queue_status,
                campaign_id_external = EXCLUDED.campaign_id_external,
                exported_at = EXCLUDED.exported_at,
                action_status = EXCLUDED.action_status,
                evidence_json = EXCLUDED.evidence_json
        """, {
            "d": action_date,
            "rid": source_run_id or str(uuid4()),
            "pid": policy_id,
            "pver": policy_version,
        })

        inserted = cur.rowcount
        conn.commit()

    return {
        "action_date": action_date,
        "rows_snapshotted": inserted,
        "source_run_id": source_run_id,
    }


def get_driver_list_history(
    action_date: Optional[str] = None,
    driver_profile_id: Optional[str] = None,
    program_code: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Query driver list history with optional filters.
    """
    with get_db() as conn:
        cur = conn.cursor()

        where = []
        params: Dict[str, Any] = {"lim": min(limit, 1000), "off": offset}

        if action_date:
            where.append("action_date = %(d)s")
            params["d"] = action_date
        if driver_profile_id:
            where.append("driver_profile_id = %(did)s")
            params["did"] = driver_profile_id
        if program_code:
            where.append("program_code = %(pc)s")
            params["pc"] = program_code

        where_clause = "WHERE " + " AND ".join(where) if where else ""

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_HISTORY} {where_clause}",
            params
        )
        total = cur.fetchone()[0] or 0

        cur.execute(
            f"""
            SELECT history_id, action_date, driver_profile_id, program_code,
                   priority_rank, queue_status, assigned_channel, queue_id,
                   campaign_id_external, exported_at, action_status,
                   source_run_id, created_at
            FROM {TABLE_HISTORY}
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %(lim)s OFFSET %(off)s
            """,
            params
        )
        rows = cur.fetchall()
        records = []
        for r in rows:
            records.append({
                "history_id": str(r[0]),
                "action_date": str(r[1]),
                "driver_profile_id": r[2],
                "program_code": r[3],
                "priority_rank": r[4],
                "queue_status": r[5],
                "assigned_channel": r[6],
                "queue_id": str(r[7]) if r[7] else None,
                "campaign_id_external": r[8],
                "exported_at": r[9].isoformat() if r[9] else None,
                "action_status": r[10],
                "source_run_id": str(r[11]) if r[11] else None,
                "created_at": r[12].isoformat() if r[12] else None,
            })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "records": records,
    }


def get_history_summary(action_date: str) -> Dict[str, Any]:
    """
    Summary of driver list history for a date.
    """
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_HISTORY} WHERE action_date = %(d)s",
            {"d": action_date}
        )
        total = cur.fetchone()[0] or 0

        cur.execute(
            f"""
            SELECT queue_status, COUNT(*) as cnt
            FROM {TABLE_HISTORY}
            WHERE action_date = %(d)s
            GROUP BY queue_status
            ORDER BY cnt DESC
            """,
            {"d": action_date}
        )
        by_status = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute(
            f"""
            SELECT program_code, COUNT(*) as cnt
            FROM {TABLE_HISTORY}
            WHERE action_date = %(d)s
            GROUP BY program_code
            ORDER BY cnt DESC
            """,
            {"d": action_date}
        )
        by_program = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute(
            f"SELECT MAX(created_at) FROM {TABLE_HISTORY} WHERE action_date = %(d)s",
            {"d": action_date}
        )
        last_snapshot = cur.fetchone()[0]

    return {
        "action_date": action_date,
        "total_drivers_tracked": total,
        "by_status": by_status,
        "by_program": by_program,
        "last_snapshot_at": last_snapshot.isoformat() if last_snapshot else None,
    }
