"""
YEGO Lima Growth — Programs Summary Service (LG-C1.4-P0).

Returns counts for the 4 static-registry programs.
Source: STATIC_REGISTRY — no DB program table yet (P2).
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

PROGRAMS: List[Dict[str, Any]] = [
    {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "program_name": "High Value Recovery",
     "priority_rank": 1, "color": "#d97706"},
    {"program_code": "PROGRAM_CHURN_PREVENTION", "program_name": "Churn Prevention",
     "priority_rank": 2, "color": "#dc2626"},
    {"program_code": "PROGRAM_14_90", "program_name": "14/90",
     "priority_rank": 3, "color": "#0891b2"},
    {"program_code": "PROGRAM_ACTIVE_GROWTH", "program_name": "Active Growth",
     "priority_rank": 4, "color": "#059669"},
]


def get_programs_summary(date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # eligible per program
        cur.execute(
            "SELECT program_code, COUNT(DISTINCT driver_profile_id) as cnt "
            "FROM growth.yango_lima_program_eligibility_daily "
            "WHERE eligibility_date = %(d)s GROUP BY program_code", {"d": date}
        )
        eligible_map = {r["program_code"]: r["cnt"] for r in cur.fetchall()}

        # prioritized per program
        cur.execute(
            "SELECT selected_program_code, COUNT(*) as cnt "
            "FROM growth.yango_lima_prioritized_opportunity_daily "
            "WHERE opportunity_date = %(d)s GROUP BY selected_program_code", {"d": date}
        )
        prioritized_map = {r["selected_program_code"]: r["cnt"] for r in cur.fetchall()}

        # actionable per program
        cur.execute(
            "SELECT selected_program_code, COUNT(*) as cnt "
            "FROM growth.yango_lima_prioritized_opportunity_daily "
            "WHERE opportunity_date = %(d)s AND is_actionable_today = true "
            "GROUP BY selected_program_code", {"d": date}
        )
        actionable_map = {r["selected_program_code"]: r["cnt"] for r in cur.fetchall()}

        # queued per program
        cur.execute(
            "SELECT program_code, COUNT(*) as cnt "
            "FROM growth.yego_lima_assignment_queue "
            "WHERE assignment_date = %(d)s GROUP BY program_code", {"d": date}
        )
        queued_map = {r["program_code"]: r["cnt"] for r in cur.fetchall()}

        # exported
        cur.execute(
            "SELECT program_code, SUM(contacts_inserted) as cnt "
            "FROM growth.yango_lima_loopcontrol_campaign_export "
            "WHERE export_status = 'exported' GROUP BY program_code"
        )
        exported_map = {r["program_code"] or "": r["cnt"] for r in cur.fetchall()}

    programs = []
    for p in PROGRAMS:
        code = p["program_code"]
        eligible = eligible_map.get(code, 0)
        prioritized = prioritized_map.get(code, 0)
        actionable = actionable_map.get(code, 0)
        queued = queued_map.get(code, 0)
        exported = exported_map.get(code, 0)
        programs.append({
            "program_code": code,
            "program_name": p["program_name"],
            "priority_rank": p["priority_rank"],
            "color": p["color"],
            "eligible_total": eligible,
            "prioritized_total": prioritized,
            "actionable_today": actionable,
            "queued_total": queued,
            "exported_total": exported,
            "status": "ACTIVO" if eligible > 0 else "SIN_DATOS",
            "source": "STATIC_REGISTRY",
        })

    return {
        "date": date,
        "programs": programs,
        "source": "STATIC_REGISTRY",
        "notice": "Programas definidos en registry estatico. Program Builder pendiente P2.",
    }
