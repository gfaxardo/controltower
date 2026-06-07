"""
YEGO Lima Growth — Movement Engine Service (ME-1 V1).

Tracks lifecycle_state transitions before/after contact.
Deterministic. NO causalidad. NO ROI. NO attribution.
"""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_MOVEMENT = "growth.yego_lima_movement_tracking"
TABLE_IMPACT = "growth.yego_lima_impact_tracking"
TABLE_STATE = "growth.yango_lima_driver_state_snapshot"

POSITIVE_TRANSITIONS = {
    ("CHURN", "ACTIVE"),
    ("CHURN", "ONBOARDING"),
    ("AT_RISK", "ACTIVE"),
    ("DECLINING", "ACTIVE"),
    ("DECLINING", "STABLE"),
    ("ACTIVE", "HIGH_VALUE"),
    ("ONBOARDING", "ACTIVE"),
    ("DORMANT", "ACTIVE"),
}

NEGATIVE_TRANSITIONS = {
    ("ACTIVE", "CHURN"),
    ("ACTIVE", "DORMANT"),
    ("ACTIVE", "AT_RISK"),
    ("ACTIVE", "DECLINING"),
    ("STABLE", "DECLINING"),
    ("STABLE", "CHURN"),
    ("HIGH_VALUE", "ACTIVE"),
    ("HIGH_VALUE", "DECLINING"),
    ("HIGH_VALUE", "CHURN"),
}


def _classify_movement(from_state: Optional[str], to_state: Optional[str]) -> Dict[str, str]:
    if not from_state or not to_state:
        return {
            "movement_type": "NO_MOVEMENT" if from_state == to_state else "UNKNOWN",
            "movement_direction": "NEUTRAL_MOVEMENT",
            "movement_status": "INSUFFICIENT_DATA",
        }

    if from_state == to_state:
        return {
            "movement_type": f"{from_state}->{to_state}",
            "movement_direction": "NEUTRAL_MOVEMENT",
            "movement_status": "STABLE",
        }

    pair = (from_state, to_state)
    if pair in POSITIVE_TRANSITIONS:
        return {
            "movement_type": f"{from_state}->{to_state}",
            "movement_direction": "POSITIVE_MOVEMENT",
            "movement_status": "IMPROVED",
        }
    elif pair in NEGATIVE_TRANSITIONS:
        return {
            "movement_type": f"{from_state}->{to_state}",
            "movement_direction": "NEGATIVE_MOVEMENT",
            "movement_status": "DECLINED",
        }
    else:
        return {
            "movement_type": f"{from_state}->{to_state}",
            "movement_direction": "NEUTRAL_MOVEMENT",
            "movement_status": "TRANSITIONED",
        }


def rebuild_movement_tracking(
    date_str: Optional[str] = None,
    campaign_id_external: Optional[str] = None,
) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("i.contact_date = %(d)s")
        params["d"] = date_str
    if campaign_id_external:
        conditions.append("i.campaign_id_external = %(cid)s")
        params["cid"] = campaign_id_external

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"""
            SELECT i.id as impact_id, i.driver_id, i.assignment_queue_id,
                   i.campaign_id_external, i.contact_status, i.contact_date
            FROM {TABLE_IMPACT} i
            WHERE {where}
              AND i.contact_status = 'CONTACTED'
              AND i.driver_id IS NOT NULL
              AND i.contact_date IS NOT NULL
            ORDER BY i.contact_date ASC
        """,
            params,
        )
        impacts = [dict(r) for r in cur.fetchall()]

    if not impacts:
        return {
            "total_processed": 0,
            "positive_movements": 0,
            "negative_movements": 0,
            "neutral_movements": 0,
            "no_movements": 0,
        }

    processed = 0
    positive = 0
    negative = 0
    neutral = 0
    no_movement = 0

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        for imp in impacts:
            driver_id = imp["driver_id"]
            contact_date = imp["contact_date"]
            cd = contact_date.date() if hasattr(contact_date, 'date') else contact_date
            if isinstance(cd, str):
                cd = datetime.fromisoformat(cd.replace('Z', '+00:00')).date()

            aq_id = imp.get("assignment_queue_id")
            campaign_id = imp.get("campaign_id_external")
            impact_id = imp.get("impact_id")

            cur.execute(
                f"""
                SELECT lifecycle_state
                FROM {TABLE_STATE}
                WHERE driver_profile_id = %(did)s
                  AND snapshot_date <= %(cd)s
                ORDER BY snapshot_date DESC
                LIMIT 1
            """,
                {"did": driver_id, "cd": cd.isoformat()},
            )
            before_row = cur.fetchone()
            from_state = before_row["lifecycle_state"] if before_row else None

            cur.execute(
                f"""
                SELECT lifecycle_state
                FROM {TABLE_STATE}
                WHERE driver_profile_id = %(did)s
                  AND snapshot_date > %(cd)s
                ORDER BY snapshot_date ASC
                LIMIT 1
            """,
                {"did": driver_id, "cd": cd.isoformat()},
            )
            after_row = cur.fetchone()
            to_state = after_row["lifecycle_state"] if after_row else None

            classification = _classify_movement(from_state, to_state)
            direction = classification["movement_direction"]

            if direction == "POSITIVE_MOVEMENT":
                positive += 1
            elif direction == "NEGATIVE_MOVEMENT":
                negative += 1
            elif direction == "NEUTRAL_MOVEMENT" and from_state == to_state:
                no_movement += 1
            else:
                neutral += 1

            _upsert_movement(
                cur, driver_id, campaign_id, aq_id, impact_id,
                from_state, to_state,
                classification["movement_type"],
                classification["movement_direction"],
                classification["movement_status"],
                cd.isoformat(),
            )
            processed += 1

        conn.commit()

    return {
        "total_processed": processed,
        "positive_movements": positive,
        "negative_movements": negative,
        "neutral_movements": neutral,
        "no_movements": no_movement,
    }


def _upsert_movement(cur, driver_id, campaign_id, aq_id, impact_id,
                     from_state, to_state, movement_type, direction, status, mdate):
    cur.execute(
        f"""
        SELECT id FROM {TABLE_MOVEMENT}
        WHERE driver_id = %(did)s
          AND impact_tracking_id IS NOT DISTINCT FROM %(iid)s
        LIMIT 1
    """,
        {"did": driver_id, "iid": impact_id},
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            f"""
            UPDATE {TABLE_MOVEMENT}
            SET from_state = %(fs)s, to_state = %(ts)s,
                movement_type = %(mt)s, movement_direction = %(md)s,
                movement_status = %(ms)s, movement_date = %(mdate)s,
                updated_at = now()
            WHERE id = %(eid)s
        """,
            {
                "fs": from_state, "ts": to_state,
                "mt": movement_type, "md": direction,
                "ms": status, "mdate": mdate,
                "eid": existing["id"],
            },
        )
    else:
        cur.execute(
            f"""
            INSERT INTO {TABLE_MOVEMENT} (
                driver_id, campaign_id_external, assignment_queue_id, impact_tracking_id,
                from_state, to_state, movement_type, movement_direction,
                movement_status, movement_date
            ) VALUES (
                %(did)s, %(cid)s, %(aq)s, %(iid)s,
                %(fs)s, %(ts)s, %(mt)s, %(md)s,
                %(ms)s, %(mdate)s
            )
        """,
            {
                "did": driver_id, "cid": campaign_id,
                "aq": aq_id, "iid": impact_id,
                "fs": from_state, "ts": to_state,
                "mt": movement_type, "md": direction,
                "ms": status, "mdate": mdate,
            },
        )


def get_movement_summary(date_str: Optional[str] = None,
                         campaign_id_external: Optional[str] = None) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("movement_date = %(d)s")
        params["d"] = date_str
    if campaign_id_external:
        conditions.append("campaign_id_external = %(cid)s")
        params["cid"] = campaign_id_external

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN movement_direction = 'POSITIVE_MOVEMENT' THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN movement_direction = 'NEGATIVE_MOVEMENT' THEN 1 ELSE 0 END) as negative,
                SUM(CASE WHEN movement_direction = 'NEUTRAL_MOVEMENT' THEN 1 ELSE 0 END) as neutral
            FROM {TABLE_MOVEMENT}
            WHERE {where}
        """,
            params,
        )
        row = cur.fetchone()
        total = int(row["total"] or 0)
        positive = int(row["positive"] or 0)
        negative = int(row["negative"] or 0)
        neutral = int(row["neutral"] or 0)

        movement_rate = round(positive / total, 4) if total > 0 else 0.0

    return {
        "date": date_str,
        "campaign_id_external": campaign_id_external,
        "total_movements": total,
        "positive_movements": positive,
        "negative_movements": negative,
        "neutral_movements": neutral,
        "movement_rate": movement_rate,
    }


def get_movement_records(date_str: Optional[str] = None,
                         campaign_id_external: Optional[str] = None,
                         movement_direction: Optional[str] = None,
                         limit: int = 200) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {"lim": min(limit, 500)}

    if date_str:
        conditions.append("m.movement_date = %(d)s")
        params["d"] = date_str
    if campaign_id_external:
        conditions.append("m.campaign_id_external = %(cid)s")
        params["cid"] = campaign_id_external
    if movement_direction:
        conditions.append("m.movement_direction = %(md)s")
        params["md"] = movement_direction

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"SELECT COUNT(*) as cnt FROM {TABLE_MOVEMENT} m WHERE {where}",
            {k: v for k, v in params.items() if k != "lim"},
        )
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"""
            SELECT m.*, q.driver_name as queue_driver_name
            FROM {TABLE_MOVEMENT} m
            LEFT JOIN growth.yego_lima_assignment_queue q ON q.id = m.assignment_queue_id
            WHERE {where}
            ORDER BY m.movement_date DESC NULLS LAST
            LIMIT %(lim)s
        """,
            params,
        )
        rows = cur.fetchall()

    records = []
    for r in rows:
        records.append({
            "id": str(r["id"]),
            "driver_id": r["driver_id"],
            "driver_name": r.get("queue_driver_name"),
            "campaign_id_external": r.get("campaign_id_external"),
            "from_state": r.get("from_state"),
            "to_state": r.get("to_state"),
            "movement_type": r.get("movement_type"),
            "movement_direction": r.get("movement_direction"),
            "movement_status": r.get("movement_status"),
            "movement_date": r["movement_date"].isoformat() if hasattr(r.get("movement_date"), 'isoformat') else str(r.get("movement_date")) if r.get("movement_date") else None,
        })

    return {"total_records": total, "records": records}


def get_movement_transitions(date_str: Optional[str] = None) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("movement_date = %(d)s")
        params["d"] = date_str

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"""
            SELECT from_state, to_state, COUNT(*) as cnt
            FROM {TABLE_MOVEMENT}
            WHERE {where} AND from_state IS NOT NULL AND to_state IS NOT NULL
            GROUP BY from_state, to_state
            ORDER BY cnt DESC
        """,
            params,
        )
        rows = cur.fetchall()

    transitions = []
    for r in rows:
        transitions.append({
            "from_state": r["from_state"],
            "to_state": r["to_state"],
            "count": int(r["cnt"]),
        })

    return {"date": date_str, "total_transitions": len(transitions), "transitions": transitions}
