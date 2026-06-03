"""
YEGO Lima Growth — Actionable List Daily Service (Fase 2C).

Generates daily actionable driver lists from segmentation snapshot.
Manages item lifecycle: PENDING_ACTION → ACTION_CONFIRMED / NO_ACTION / etc.
"""

from __future__ import annotations
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_LIST = "growth.yango_lima_actionable_list_daily"
TABLE_SNAPSHOT = "growth.yango_lima_driver_segment_snapshot"

LIST_TYPES = {
    "LEALTAD_1_14_90": ["NEW", "REACTIVATED"],
    "LEALTAD_2_ACTIVE_GROWTH": ["ACTIVE", "RECOVERED"],
    "LEALTAD_3_CHURN_PREVENTION": ["DECLINING", "CHURN_RISK", "CHURNED"],
}


def build_daily_actionable_lists(list_date_str: str) -> Dict[str, Any]:
    list_date = date.fromisoformat(list_date_str)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_SNAPSHOT}")
        latest = cur.fetchone()
        if not latest or not latest["max"]:
            return {"ok": False, "error": "No segmentation snapshot available"}

        snap_date = latest["max"]

        counts = {}
        total = 0

        for list_type, l1_values in LIST_TYPES.items():
            cur.execute(f"""
                INSERT INTO {TABLE_LIST} (list_date, driver_profile_id, list_type,
                    segment_level_1, segment_level_2, segment_level_3,
                    priority, action_reason,
                    current_week_orders, distance_to_target, supply_hours,
                    productivity_band, driver_state,
                    management_status)
                SELECT %(list_date)s, driver_profile_id, %(list_type)s,
                       segment_level_1, segment_level_2, segment_level_3,
                       growth_priority, segment_level_3,
                       current_week_orders, distance_to_target, current_week_supply_hours,
                       productivity_band, driver_state,
                       'PENDING_ACTION'
                FROM {TABLE_SNAPSHOT}
                WHERE snapshot_date = %(snap_date)s
                  AND segment_level_1 = ANY(%(l1)s)
                ON CONFLICT (list_date, driver_profile_id, list_type) DO NOTHING
            """, {"list_date": list_date, "list_type": list_type, "snap_date": snap_date, "l1": l1_values})

            cur.execute(f"""
                SELECT COUNT(*) FROM {TABLE_LIST}
                WHERE list_date = %(list_date)s AND list_type = %(list_type)s
            """, {"list_date": list_date, "list_type": list_type})
            cnt = cur.fetchone()["count"]
            counts[list_type] = cnt
            total += cnt

        conn.commit()

    return {
        "ok": True,
        "list_date": list_date_str,
        "source_snapshot_date": str(snap_date),
        "total_items": total,
        "by_list_type": counts,
    }


def close_unmanaged_items(list_date_str: str) -> Dict[str, Any]:
    list_date = date.fromisoformat(list_date_str)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            UPDATE {TABLE_LIST}
            SET management_status = 'NO_ACTION', closed_at = now()
            WHERE list_date = %(d)s AND management_status = 'PENDING_ACTION'
        """, {"d": list_date})
        closed = cur.rowcount
        conn.commit()

    return {"ok": True, "list_date": list_date_str, "items_closed": closed}


def get_daily_actionable_list(list_date: Optional[str] = None, list_type: Optional[str] = None,
                              management_status: Optional[str] = None, assigned_agent: Optional[str] = None,
                              limit: int = 100) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if not list_date:
            cur.execute(f"SELECT MAX(list_date) FROM {TABLE_LIST}")
            r = cur.fetchone()
            if not r or not r["max"]:
                return []
            list_date = str(r["max"])

        where = ["list_date = %(d)s"]
        params = {"d": list_date, "limit": min(limit, 500)}
        if list_type:
            where.append("list_type = %(lt)s")
            params["lt"] = list_type
        if management_status:
            where.append("management_status = %(ms)s")
            params["ms"] = management_status
        if assigned_agent:
            where.append("assigned_agent = %(ag)s")
            params["ag"] = assigned_agent

        cur.execute(f"""
            SELECT list_date, driver_profile_id, list_type,
                   segment_level_1, segment_level_2, segment_level_3,
                   priority, action_reason,
                   current_week_orders, distance_to_target, supply_hours,
                   management_status, assigned_agent, action_id
            FROM {TABLE_LIST}
            WHERE {' AND '.join(where)}
            ORDER BY priority ASC NULLS LAST
            LIMIT %(limit)s
        """, params)

        result = []
        for row in cur.fetchall():
            item = dict(row)
            item["list_date"] = str(item["list_date"])
            result.append(item)
        return result


def assign_agent(list_date_str: str, driver_profile_id: str, list_type: str, agent: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            UPDATE {TABLE_LIST}
            SET assigned_agent = %(agent)s
            WHERE list_date = %(d)s AND driver_profile_id = %(did)s AND list_type = %(lt)s
        """, {"d": list_date_str, "did": driver_profile_id, "lt": list_type, "agent": agent})
        conn.commit()
        return {"ok": cur.rowcount > 0, "assigned_agent": agent}


def update_management_status(list_date_str: str, driver_profile_id: str, list_type: str,
                             status: str, action_id: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_LIST}
            SET management_status = %(status)s, action_id = COALESCE(%(aid)s::uuid, action_id),
                closed_at = CASE WHEN %(status)s != 'PENDING_ACTION' THEN now() ELSE closed_at END
            WHERE list_date = %(d)s AND driver_profile_id = %(did)s AND list_type = %(lt)s
        """, {"d": list_date_str, "did": driver_profile_id, "lt": list_type, "status": status, "aid": action_id})
        conn.commit()
        return {"ok": cur.rowcount > 0, "status": status}
