"""
Driver Workflow Service — FASE D5
Control Foundation: Operational Execution Loop

State machine (deterministic):
  UNASSIGNED → ASSIGNED → IN_PROGRESS → {CONTACTED, NO_RESPONSE, RECOVERED, CLOSED}
  Any state → BLOCKED (if phone invalid or data stale)
  Any state → CLOSED

Tables:
  ops.driver_supply_workflow   — workflow state per driver+queue
  ops.driver_supply_action_log — immutable action history

Principles:
  - Every action traceable (actor + timestamp + previous_status)
  - Deterministic transitions validated
  - No auto-transitions, no IA, no BPM
  - Lightweight: one row per driver-queue pair
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 15000

WORKFLOW_STATUSES = [
    "UNASSIGNED", "ASSIGNED", "IN_PROGRESS",
    "CONTACTED", "NO_RESPONSE", "RECOVERED",
    "CLOSED", "BLOCKED",
]

TRANSITIONS = {
    "UNASSIGNED": ["ASSIGNED", "BLOCKED"],
    "ASSIGNED": ["IN_PROGRESS", "UNASSIGNED", "BLOCKED", "CLOSED"],
    "IN_PROGRESS": ["CONTACTED", "NO_RESPONSE", "RECOVERED", "CLOSED", "BLOCKED", "ASSIGNED"],
    "CONTACTED": ["IN_PROGRESS", "RECOVERED", "NO_RESPONSE", "CLOSED"],
    "NO_RESPONSE": ["IN_PROGRESS", "CLOSED", "BLOCKED"],
    "RECOVERED": ["CLOSED", "IN_PROGRESS"],
    "CLOSED": [],
    "BLOCKED": ["ASSIGNED", "CLOSED"],
}

ACTION_TYPES = [
    "CALL_ATTEMPT", "WHATSAPP_SENT", "DRIVER_CONTACTED",
    "FOLLOW_UP", "DRIVER_RECOVERED", "NO_RESPONSE",
    "INVALID_PHONE", "CLOSED_CASE", "ASSIGNED", "NOTE",
]


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET LOCAL statement_timeout = %s", (str(int(timeout_ms)),))
    return c


def _safe_execute(cur, sql: str, params: dict = None) -> bool:
    try:
        cur.execute(sql, params or {})
        return True
    except Exception as e:
        logger.debug("workflow query failed: %s", e)
        return False


def create_workflow_schema():
    """Create workflow and action_log tables if not exist."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("CREATE SCHEMA IF NOT EXISTS ops;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ops.driver_supply_workflow (
                    workflow_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    queue_type VARCHAR(50) NOT NULL,
                    driver_id VARCHAR(128) NOT NULL,
                    workflow_status VARCHAR(20) NOT NULL DEFAULT 'UNASSIGNED',
                    assigned_owner VARCHAR(128),
                    assigned_at TIMESTAMPTZ,
                    last_action_at TIMESTAMPTZ,
                    latest_action_type VARCHAR(30),
                    latest_action_note TEXT,
                    latest_action_result TEXT,
                    latest_contact_channel VARCHAR(20),
                    resolution_reason TEXT,
                    resolution_outcome VARCHAR(20),
                    priority_snapshot VARCHAR(10),
                    lifecycle_snapshot VARCHAR(30),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(driver_id, queue_type)
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ops.driver_supply_action_log (
                    action_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    workflow_id UUID REFERENCES ops.driver_supply_workflow(workflow_id) ON DELETE CASCADE,
                    driver_id VARCHAR(128) NOT NULL,
                    action_type VARCHAR(30) NOT NULL,
                    action_note TEXT,
                    action_result TEXT,
                    action_channel VARCHAR(20),
                    action_actor VARCHAR(128) NOT NULL,
                    previous_status VARCHAR(20),
                    new_status VARCHAR(20),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            conn.commit()
            logger.info("ops.driver_supply_workflow and action_log tables verified.")
        except Exception as e:
            conn.rollback()
            logger.warning("create_workflow_schema: %s", e)
        finally:
            cur.close()


def validate_transition(current: str, target: str) -> bool:
    """Check if transition is allowed."""
    allowed = TRANSITIONS.get(current, [])
    return target in allowed


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Workflow CRUD ───────────────────────────────────────────────────────────


def get_or_create_workflow(driver_id: str, queue_type: str) -> dict | None:
    """Get existing workflow or create UNASSIGNED."""
    try:
        with get_db() as conn:
            cur = _cursor(conn)

            row = None
            cur.execute(
                "SELECT * FROM ops.driver_supply_workflow WHERE driver_id = %(did)s AND queue_type = %(qt)s LIMIT 1",
                {"did": driver_id, "qt": queue_type},
            )
            if cur.rowcount:
                row = cur.fetchone()

            if row:
                return dict(row)

            wf_id = str(uuid.uuid4())
            now = _now_iso()
            cur.execute(
                """
                INSERT INTO ops.driver_supply_workflow (workflow_id, queue_type, driver_id, workflow_status, created_at, updated_at)
                VALUES (%(wid)s, %(qt)s, %(did)s, 'UNASSIGNED', %(now)s, %(now)s)
                ON CONFLICT (driver_id, queue_type) DO UPDATE SET updated_at = %(now)s
                RETURNING *
                """,
                {"wid": wf_id, "qt": queue_type, "did": driver_id, "now": now},
            )
            new_row = cur.fetchone()
            conn.commit()
            return dict(new_row) if new_row else None
    except Exception as e:
        logger.warning("get_or_create_workflow failed: %s", e)
        return None


def assign_workflow(driver_id: str, queue_type: str, owner: str) -> dict | None:
    """Assign owner to workflow. Creates workflow if not exists."""
    wf = get_or_create_workflow(driver_id, queue_type)
    if not wf:
        return None
    return update_workflow_status(
        wf["workflow_id"], "ASSIGNED",
        action_type="ASSIGNED", actor=owner or "system",
        note=f"Assigned to {owner}",
    )


def update_workflow_status(
    workflow_id: str,
    new_status: str,
    action_type: str = "NOTE",
    action_note: str = "",
    action_result: str = "",
    action_channel: str = "manual",
    actor: str = "system",
) -> dict | None:
    """Update workflow status with transition validation."""
    try:
        with get_db() as conn:
            cur = _cursor(conn)

            cur.execute(
                "SELECT * FROM ops.driver_supply_workflow WHERE workflow_id = %(wid)s",
                {"wid": workflow_id},
            )
            wf = cur.fetchone()
            if not wf:
                return None

            current = wf["workflow_status"]
            if not validate_transition(current, new_status):
                return {
                    "error": "invalid_transition",
                    "current": current,
                    "target": new_status,
                    "allowed": TRANSITIONS.get(current, []),
                }

            now = _now_iso()

            # Update workflow
            cur.execute(
                """
                UPDATE ops.driver_supply_workflow
                SET workflow_status = %(ns)s,
                    assigned_owner = CASE WHEN %(ns)s = 'ASSIGNED' AND %(actor)s != 'system'
                        THEN COALESCE(assigned_owner, %(actor)s) ELSE assigned_owner END,
                    assigned_at = CASE WHEN %(ns)s = 'ASSIGNED' AND assigned_owner IS NULL
                        THEN %(now)s ELSE assigned_at END,
                    last_action_at = %(now)s,
                    latest_action_type = %(at)s,
                    latest_action_note = %(note)s,
                    latest_action_result = %(ar)s,
                    latest_contact_channel = %(ch)s,
                    updated_at = %(now)s
                WHERE workflow_id = %(wid)s
                RETURNING *
                """,
                {
                    "wid": workflow_id, "ns": new_status,
                    "at": action_type, "note": action_note or "", "ar": action_result or "",
                    "ch": action_channel, "actor": actor, "now": now,
                },
            )
            updated = cur.fetchone()

            # Log action
            _safe_execute(
                cur,
                """
                INSERT INTO ops.driver_supply_action_log
                (workflow_id, driver_id, action_type, action_note, action_result, action_channel,
                 action_actor, previous_status, new_status, created_at)
                VALUES (%(wid)s, %(did)s, %(at)s, %(note)s, %(ar)s, %(ch)s,
                        %(actor)s, %(prev)s, %(ns)s, %(now)s)
                """,
                {
                    "wid": workflow_id, "did": wf["driver_id"],
                    "at": action_type, "note": action_note or "", "ar": action_result or "",
                    "ch": action_channel, "actor": actor,
                    "prev": current, "ns": new_status, "now": now,
                },
            )

            conn.commit()
            return dict(updated) if updated else None
    except Exception as e:
        logger.warning("update_workflow_status failed: %s", e)
        return None


def log_action(
    workflow_id: str,
    driver_id: str,
    action_type: str,
    action_note: str = "",
    action_result: str = "",
    action_channel: str = "manual",
    actor: str = "system",
) -> dict | None:
    """Log an action without changing workflow status."""
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            now = _now_iso()
            aid = str(uuid.uuid4())
            _safe_execute(
                cur,
                """
                INSERT INTO ops.driver_supply_action_log
                (action_id, workflow_id, driver_id, action_type, action_note, action_result,
                 action_channel, action_actor, created_at)
                VALUES (%(aid)s, %(wid)s, %(did)s, %(at)s, %(note)s, %(ar)s,
                        %(ch)s, %(actor)s, %(now)s)
                """,
                {
                    "aid": aid, "wid": workflow_id, "did": driver_id,
                    "at": action_type, "note": action_note or "", "ar": action_result or "",
                    "ch": action_channel, "actor": actor, "now": now,
                },
            )
            conn.commit()
            return {"action_id": aid, "status": "logged"}
    except Exception as e:
        logger.warning("log_action failed: %s", e)
        return None


def get_workflow(workflow_id: str) -> dict | None:
    """Get full workflow with history."""
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute(
                "SELECT * FROM ops.driver_supply_workflow WHERE workflow_id = %(wid)s",
                {"wid": workflow_id},
            )
            wf = cur.fetchone()
            if not wf:
                return None

            cur.execute(
                "SELECT * FROM ops.driver_supply_action_log WHERE workflow_id = %(wid)s ORDER BY created_at DESC LIMIT 50",
                {"wid": workflow_id},
            )
            history = cur.fetchall() or []

            return {
                "workflow": dict(wf),
                "history": [dict(h) for h in history],
                "history_count": len(history),
            }
    except Exception as e:
        logger.warning("get_workflow failed: %s", e)
        return None


def list_workflows(
    owner: Optional[str] = None,
    status: Optional[str] = None,
    queue_type: Optional[str] = None,
    driver_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """List workflows with filters."""
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            conditions = ["1=1"]
            params = {}

            if owner:
                conditions.append("w.assigned_owner = %(owner)s")
                params["owner"] = owner
            if status:
                conditions.append("w.workflow_status = %(status)s")
                params["status"] = status
            if queue_type:
                conditions.append("w.queue_type = %(qt)s")
                params["qt"] = queue_type
            if driver_id:
                conditions.append("w.driver_id = %(did)s")
                params["did"] = driver_id

            where = " AND ".join(conditions)

            cur.execute(
                f"""
                SELECT w.*,
                       COALESCE(vr.driver_name) AS driver_name,
                       COALESCE(dd.driver_phone, d.phone::text) AS phone,
                       COALESCE(dp.city, prk.city) AS city,
                       COALESCE(dp.country, prk.country) AS country,
                       COALESCE(dp.park_name, prk.park_name) AS park_name
                FROM ops.driver_supply_workflow w
                JOIN public.drivers d ON w.driver_id = d.driver_id
                LEFT JOIN ops.v_dim_driver_resolved vr ON d.driver_id = vr.driver_id
                LEFT JOIN public.drivers_data dd ON d.driver_id = dd.driver_id
                LEFT JOIN dim.dim_park dp ON d.park_id = dp.park_id
                LEFT JOIN ops.v_dim_park_resolved prk ON d.park_id = prk.park_id
                WHERE {where}
                ORDER BY w.updated_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {**params, "limit": limit, "offset": offset},
            )
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("list_workflows failed: %s", e)
        return []


def get_accountability_metrics() -> dict:
    """Aggregate execution metrics."""
    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute("""
                SELECT
                    COUNT(*) AS total_workflows,
                    COUNT(*) FILTER (WHERE workflow_status = 'UNASSIGNED') AS unassigned,
                    COUNT(*) FILTER (WHERE workflow_status = 'ASSIGNED') AS assigned,
                    COUNT(*) FILTER (WHERE workflow_status = 'IN_PROGRESS') AS in_progress,
                    COUNT(*) FILTER (WHERE workflow_status = 'CONTACTED') AS contacted,
                    COUNT(*) FILTER (WHERE workflow_status = 'NO_RESPONSE') AS no_response,
                    COUNT(*) FILTER (WHERE workflow_status = 'RECOVERED') AS recovered,
                    COUNT(*) FILTER (WHERE workflow_status = 'CLOSED') AS closed,
                    COUNT(*) FILTER (WHERE workflow_status = 'BLOCKED') AS blocked,
                    COUNT(DISTINCT assigned_owner) AS owners_count
                FROM ops.driver_supply_workflow
            """)
            row = cur.fetchone()

            cur.execute("""
                SELECT assigned_owner, COUNT(*) AS cnt
                FROM ops.driver_supply_workflow
                WHERE assigned_owner IS NOT NULL
                GROUP BY assigned_owner
                ORDER BY cnt DESC
                LIMIT 20
            """)
            by_owner = cur.fetchall() or []

            return {
                "status": "ok",
                "metrics": dict(row) if row else {},
                "by_owner": [dict(o) for o in by_owner],
                "generated_at": _now_iso(),
            }
    except Exception as e:
        logger.warning("accountability_metrics failed: %s", e)
        return {"status": "blocked", "metrics": {}, "error": str(e)}
