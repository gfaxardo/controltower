"""
YEGO Lima Growth — Action Registry Service (Fase 2C + Fase 2D-R).

Registers, confirms, and queries agent actions on drivers.

Fase 2D-R extensions:
- Supports opportunity_date + opportunity_type + program_code (canonical)
- Maintains backward compatibility with list_date + list_type (legacy)

DEPRECATED: list_type / list_date legacy replaced by
  opportunity_type / opportunity_date / program_code.
"""

from __future__ import annotations
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_ACTIONS = "growth.yango_lima_driver_action_registry"
TABLE_LIST = "growth.yango_lima_actionable_list_daily"
TABLE_OPPORTUNITY = "growth.yango_lima_daily_opportunity_list"


def create_action(
    driver_profile_id: str, action_date_str: str, action_type: str,
    source_segment_snapshot_date: str,
    list_date: Optional[str] = None, list_type: Optional[str] = None,
    action_channel: Optional[str] = None, action_owner: Optional[str] = None,
    action_status: str = "attempted", action_confirmed: bool = False,
    confirmation_source: Optional[str] = None, action_reason: Optional[str] = None,
    campaign_code: Optional[str] = None, notes: Optional[str] = None,
    # ── Fase 2D-R new fields ──
    opportunity_date: Optional[str] = None,
    opportunity_type: Optional[str] = None,
    program_code: Optional[str] = None,
) -> Dict[str, Any]:

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            INSERT INTO {TABLE_ACTIONS} (
                action_date, driver_profile_id,
                list_date, list_type, source_segment_snapshot_date,
                action_type, action_channel, action_owner,
                action_status, action_confirmed, confirmation_source,
                action_reason, campaign_code, notes
            ) VALUES (
                %(ad)s, %(did)s,
                %(ld)s, %(lt)s, %(ssd)s,
                %(at)s, %(ac)s, %(ao)s,
                %(as)s, %(acf)s, %(cs)s,
                %(ar)s, %(cc)s, %(n)s
            ) RETURNING action_id, created_at
        """, {
            "ad": action_date_str, "did": driver_profile_id,
            "ld": list_date, "lt": list_type, "ssd": source_segment_snapshot_date,
            "at": action_type, "ac": action_channel, "ao": action_owner,
            "as": action_status, "acf": action_confirmed, "cs": confirmation_source,
            "ar": action_reason, "cc": campaign_code, "n": notes,
        })
        row = cur.fetchone()
        action_id = str(row["action_id"])

        new_status = "ACTION_CONFIRMED" if action_confirmed else "ACTION_ATTEMPTED"

        # Update actionable list if linked (legacy)
        if list_date and list_type:
            cur.execute(f"""
                UPDATE {TABLE_LIST}
                SET management_status = %(ms)s, action_id = %(aid)s::uuid, closed_at = now()
                WHERE list_date = %(ld)s AND driver_profile_id = %(did)s AND list_type = %(lt)s
            """, {"ms": new_status, "aid": action_id, "ld": list_date, "did": driver_profile_id, "lt": list_type})

        # Update opportunity list if linked (new canonical)
        if opportunity_date and opportunity_type:
            cur.execute(f"""
                UPDATE {TABLE_OPPORTUNITY}
                SET management_status = %(ms)s, action_id = %(aid)s::uuid, closed_at = now()
                WHERE opportunity_date = %(od)s AND driver_profile_id = %(did)s AND opportunity_type = %(ot)s
            """, {"ms": new_status, "aid": action_id, "od": opportunity_date, "did": driver_profile_id, "ot": opportunity_type})

        conn.commit()
        return {"ok": True, "action_id": action_id}


def confirm_action(action_id: str, confirmation_source: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_ACTIONS}
            SET action_status = 'completed', action_confirmed = true,
                confirmation_source = %(cs)s, confirmation_at = now(), updated_at = now()
            WHERE action_id = %(aid)s::uuid
        """, {"aid": action_id, "cs": confirmation_source})
        conn.commit()
        return {"ok": cur.rowcount > 0}


def update_action_status(action_id: str, action_status: str, action_confirmed: bool = False) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_ACTIONS}
            SET action_status = %(as)s, action_confirmed = %(acf)s,
                confirmation_at = CASE WHEN %(acf)s THEN now() ELSE confirmation_at END,
                updated_at = now()
            WHERE action_id = %(aid)s::uuid
        """, {"aid": action_id, "as": action_status, "acf": action_confirmed})
        conn.commit()
        return {"ok": cur.rowcount > 0}


def list_actions(date_from: Optional[str] = None, date_to: Optional[str] = None,
                 action_owner: Optional[str] = None, limit: int = 100) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        where = []
        params = {"limit": min(limit, 500)}
        if date_from:
            where.append("action_date >= %(df)s")
            params["df"] = date_from
        if date_to:
            where.append("action_date <= %(dt)s")
            params["dt"] = date_to
        if action_owner:
            where.append("action_owner = %(ao)s")
            params["ao"] = action_owner

        wc = "WHERE " + " AND ".join(where) if where else ""
        cur.execute(f"""
            SELECT action_id, action_date, driver_profile_id, list_type,
                   action_type, action_channel, action_owner, action_status,
                   action_confirmed, confirmation_source, action_reason
            FROM {TABLE_ACTIONS} {wc}
            ORDER BY action_date DESC, created_at DESC
            LIMIT %(limit)s
        """, params)
        return [dict(r) for r in cur.fetchall()]


def get_actions_by_driver(driver_profile_id: str, limit: int = 20) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT * FROM {TABLE_ACTIONS}
            WHERE driver_profile_id = %(did)s
            ORDER BY action_date DESC LIMIT %(limit)s
        """, {"did": driver_profile_id, "limit": limit})
        return [dict(r) for r in cur.fetchall()]
