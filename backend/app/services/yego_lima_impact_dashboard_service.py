"""
YEGO Lima Growth — Impact Dashboard Service (IF-2 V1).

Aggregates impact tracking by program, campaign, and channel.
Deterministic. NO revenue. NO ROI. NO attribution.
"""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_IMPACT = "growth.yego_lima_impact_tracking"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"


def _build_aggregation_query(group_field: str, group_label: str,
                             date_str: Optional[str] = None) -> tuple:
    conditions = ["i.assignment_queue_id IS NOT NULL"]
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("i.contact_date = %(d)s")
        params["d"] = date_str

    where = " AND ".join(conditions)

    query = f"""
        SELECT
            q.{group_field} as {group_label},
            COUNT(i.id) as exported_count,
            SUM(CASE WHEN i.contact_status = 'CONTACTED' THEN 1 ELSE 0 END) as contacted_count,
            SUM(CASE WHEN i.impact_status = 'RETURNED' THEN 1 ELSE 0 END) as returned_count,
            SUM(CASE WHEN i.impact_status = 'NOT_RETURNED' THEN 1 ELSE 0 END) as not_returned_count,
            SUM(CASE WHEN i.impact_status = 'PENDING_WINDOW' THEN 1 ELSE 0 END) as pending_count
        FROM {TABLE_IMPACT} i
        LEFT JOIN {TABLE_QUEUE} q ON q.id = i.assignment_queue_id
        WHERE {where}
        GROUP BY q.{group_field}
        ORDER BY exported_count DESC
    """

    return query, params


def _enrich_results(rows: list, group_label: str) -> List[Dict[str, Any]]:
    results = []
    for r in rows:
        exported = int(r["exported_count"] or 0)
        contacted = int(r["contacted_count"] or 0)
        returned = int(r["returned_count"] or 0)
        not_returned = int(r["not_returned_count"] or 0)
        pending = int(r["pending_count"] or 0)

        return_rate = round(returned / contacted, 4) if contacted > 0 else 0.0
        contact_rate = round(contacted / exported, 4) if exported > 0 else 0.0

        results.append({
            group_label: r[group_label] or "UNKNOWN",
            "exported_count": exported,
            "contacted_count": contacted,
            "returned_count": returned,
            "not_returned_count": not_returned,
            "pending_count": pending,
            "return_rate": return_rate,
            "contact_rate": contact_rate,
        })

    results.sort(key=lambda x: x["return_rate"], reverse=True)
    return results


def get_impact_by_program(date_str: Optional[str] = None) -> Dict[str, Any]:
    query, params = _build_aggregation_query("program_code", "program_code", date_str)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        rows = cur.fetchall()

    programs = _enrich_results(rows, "program_code")

    cur.execute(
        "SELECT program_code, program_name FROM growth.yego_lima_assignment_queue GROUP BY program_code, program_name"
    )
    name_map = {r["program_code"]: r["program_name"] for r in cur.fetchall()}

    for p in programs:
        p["program_name"] = name_map.get(p["program_code"], p["program_code"])

    return {
        "date": date_str,
        "total_programs": len(programs),
        "programs": programs,
    }


def get_impact_by_campaign(date_str: Optional[str] = None) -> Dict[str, Any]:
    query, params = _build_aggregation_query("campaign_id_external", "campaign_id_external", date_str)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        rows = cur.fetchall()

    campaigns = _enrich_results(rows, "campaign_id_external")
    return {
        "date": date_str,
        "total_campaigns": len(campaigns),
        "campaigns": campaigns,
    }


def get_impact_by_channel(date_str: Optional[str] = None) -> Dict[str, Any]:
    query, params = _build_aggregation_query("assigned_channel", "channel", date_str)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, params)
        rows = cur.fetchall()

    channels = _enrich_results(rows, "channel")
    return {
        "date": date_str,
        "total_channels": len(channels),
        "channels": channels,
    }


def get_impact_dashboard_summary(date_str: Optional[str] = None) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("contact_date = %(d)s")
        params["d"] = date_str

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"""
            SELECT
                COUNT(*) as exported,
                SUM(CASE WHEN contact_status = 'CONTACTED' THEN 1 ELSE 0 END) as contacted,
                SUM(CASE WHEN impact_status = 'RETURNED' THEN 1 ELSE 0 END) as returned
            FROM {TABLE_IMPACT}
            WHERE {where}
        """,
            params,
        )
        row = cur.fetchone()
        exported = int(row["exported"] or 0)
        contacted = int(row["contacted"] or 0)
        returned = int(row["returned"] or 0)

        return_rate = round(returned / contacted, 4) if contacted > 0 else 0.0
        contact_rate = round(contacted / exported, 4) if exported > 0 else 0.0

        cur.execute(
            f"""
            SELECT q.program_code, COUNT(*) as cnt
            FROM {TABLE_IMPACT} i
            JOIN {TABLE_QUEUE} q ON q.id = i.assignment_queue_id
            WHERE {where} AND i.impact_status = 'RETURNED'
            GROUP BY q.program_code
            ORDER BY cnt DESC
            LIMIT 1
        """,
            params,
        )
        top = cur.fetchone()
        top_program = top["program_code"] if top else None

        cur.execute(
            f"""
            SELECT q.program_code, COUNT(*) as cnt
            FROM {TABLE_IMPACT} i
            JOIN {TABLE_QUEUE} q ON q.id = i.assignment_queue_id
            WHERE {where} AND i.impact_status = 'RETURNED'
            GROUP BY q.program_code
            ORDER BY cnt ASC
            LIMIT 1
        """,
            params,
        )
        bottom = cur.fetchone()
        bottom_program = bottom["program_code"] if bottom else None

    return {
        "date": date_str,
        "exported_count": exported,
        "contacted_count": contacted,
        "returned_count": returned,
        "return_rate": return_rate,
        "contact_rate": contact_rate,
        "top_program": top_program,
        "bottom_program": bottom_program,
    }
