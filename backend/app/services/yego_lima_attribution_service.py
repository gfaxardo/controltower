"""
YEGO Lima Growth — Attribution Candidate Service (AE-1 V1).

Deterministic attribution eligibility from impact + movement data.
NO causalidad. NO ML. NO ROI.
"""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_ATTRIB = "growth.yego_lima_attribution_candidates"
TABLE_MOVEMENT = "growth.yego_lima_movement_tracking"
TABLE_IMPACT = "growth.yego_lima_impact_tracking"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"


def _determine_confidence(impact_status: Optional[str],
                          movement_direction: Optional[str]) -> tuple:
    if not impact_status or not movement_direction:
        return "UNKNOWN", "UNKNOWN", "Insufficient data"

    if impact_status == "RETURNED" and movement_direction == "POSITIVE_MOVEMENT":
        return "ELIGIBLE", "HIGH", "Contacted + returned + positive movement"
    if impact_status == "RETURNED":
        return "ELIGIBLE", "MEDIUM", "Contacted + returned (no positive movement)"
    if movement_direction == "POSITIVE_MOVEMENT":
        return "ELIGIBLE", "LOW", "Returned or positive movement but not both fully confirmed"
    return "NOT_ELIGIBLE", "LOW", "No clear signal"


def rebuild_attribution_candidates(
    date_str: Optional[str] = None,
) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("m.movement_date = %(d)s")
        params["d"] = date_str

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"""
            SELECT
                m.id as movement_id, m.driver_id, m.campaign_id_external,
                m.assignment_queue_id, m.impact_tracking_id,
                m.movement_direction,
                i.contact_status, i.impact_status,
                q.program_code, q.assigned_channel
            FROM {TABLE_MOVEMENT} m
            LEFT JOIN {TABLE_IMPACT} i ON i.id = m.impact_tracking_id
            LEFT JOIN {TABLE_QUEUE} q ON q.id = m.assignment_queue_id
            WHERE {where}
              AND m.driver_id IS NOT NULL
            ORDER BY m.movement_date DESC NULLS LAST
        """,
            params,
        )
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return {"total_processed": 0, "high_count": 0, "medium_count": 0, "low_count": 0}

    high = 0
    medium = 0
    low = 0
    processed = 0

    for r in rows:
        status, confidence, reason = _determine_confidence(
            r.get("impact_status"),
            r.get("movement_direction"),
        )

        if confidence == "HIGH":
            high += 1
        elif confidence == "MEDIUM":
            medium += 1
        elif confidence == "LOW":
            low += 1

        _upsert_attribution(
            cur, r["driver_id"], r.get("campaign_id_external"),
            r.get("assignment_queue_id"), r.get("impact_tracking_id"),
            r["movement_id"], r.get("program_code"), r.get("assigned_channel"),
            status, confidence, reason,
        )
        processed += 1

    conn.commit()

    return {
        "total_processed": processed,
        "high_count": high,
        "medium_count": medium,
        "low_count": low,
    }


def _upsert_attribution(cur, driver_id, campaign_id, aq_id, impact_id,
                        movement_id, program_code, channel, status, confidence, reason):
    cur.execute(
        f"""
        SELECT id FROM {TABLE_ATTRIB}
        WHERE movement_tracking_id = %(mid)s
        LIMIT 1
    """,
        {"mid": movement_id},
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            f"""
            UPDATE {TABLE_ATTRIB}
            SET candidate_status = %(cs)s,
                candidate_confidence = %(cc)s,
                candidate_reason = %(cr)s,
                program_code = %(pc)s,
                assigned_channel = %(ac)s,
                updated_at = now()
            WHERE id = %(eid)s
        """,
            {
                "cs": status, "cc": confidence, "cr": reason,
                "pc": program_code, "ac": channel,
                "eid": existing["id"],
            },
        )
    else:
        cur.execute(
            f"""
            INSERT INTO {TABLE_ATTRIB} (
                driver_id, campaign_id_external, assignment_queue_id,
                impact_tracking_id, movement_tracking_id,
                program_code, assigned_channel,
                candidate_status, candidate_confidence, candidate_reason
            ) VALUES (
                %(did)s, %(cid)s, %(aq)s, %(iid)s, %(mid)s,
                %(pc)s, %(ac)s,
                %(cs)s, %(cc)s, %(cr)s
            )
        """,
            {
                "did": driver_id, "cid": campaign_id, "aq": aq_id,
                "iid": impact_id, "mid": movement_id,
                "pc": program_code, "ac": channel,
                "cs": status, "cc": confidence, "cr": reason,
            },
        )


def _aggregate_by(group_field: str, date_str: Optional[str] = None) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("m.movement_date = %(d)s")
        params["d"] = date_str

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"""
            SELECT
                a.{group_field},
                COUNT(*) as candidate_count,
                SUM(CASE WHEN a.candidate_confidence = 'HIGH' THEN 1 ELSE 0 END) as high_count,
                SUM(CASE WHEN a.candidate_confidence = 'MEDIUM' THEN 1 ELSE 0 END) as medium_count,
                SUM(CASE WHEN a.candidate_confidence = 'LOW' THEN 1 ELSE 0 END) as low_count
            FROM {TABLE_ATTRIB} a
            JOIN {TABLE_MOVEMENT} m ON m.id = a.movement_tracking_id
            WHERE {where} AND a.{group_field} IS NOT NULL
            GROUP BY a.{group_field}
            ORDER BY candidate_count DESC
        """,
            params,
        )
        rows = cur.fetchall()

    items = []
    for r in rows:
        items.append({
            group_field: r[group_field],
            "candidate_count": int(r["candidate_count"] or 0),
            "high_count": int(r["high_count"] or 0),
            "medium_count": int(r["medium_count"] or 0),
            "low_count": int(r["low_count"] or 0),
        })

    return {"date": date_str, "items": items}


def get_attribution_summary(date_str: Optional[str] = None) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("m.movement_date = %(d)s")
        params["d"] = date_str

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN a.candidate_confidence = 'HIGH' THEN 1 ELSE 0 END) as high,
                SUM(CASE WHEN a.candidate_confidence = 'MEDIUM' THEN 1 ELSE 0 END) as medium,
                SUM(CASE WHEN a.candidate_confidence = 'LOW' THEN 1 ELSE 0 END) as low
            FROM {TABLE_ATTRIB} a
            JOIN {TABLE_MOVEMENT} m ON m.id = a.movement_tracking_id
            WHERE {where}
        """,
            params,
        )
        row = cur.fetchone()

    return {
        "date": date_str,
        "total_candidates": int(row["total"] or 0),
        "high_confidence": int(row["high"] or 0),
        "medium_confidence": int(row["medium"] or 0),
        "low_confidence": int(row["low"] or 0),
    }


def get_attribution_by_program(date_str: Optional[str] = None) -> Dict[str, Any]:
    return _aggregate_by("program_code", date_str)


def get_attribution_by_campaign(date_str: Optional[str] = None) -> Dict[str, Any]:
    return _aggregate_by("campaign_id_external", date_str)


def get_attribution_by_channel(date_str: Optional[str] = None) -> Dict[str, Any]:
    return _aggregate_by("assigned_channel", date_str)
