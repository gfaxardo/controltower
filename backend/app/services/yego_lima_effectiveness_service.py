"""
LG-IMP-1B — Program Effectiveness Real Scoring Service
Reads from existing effectiveness fact tables. NO recalculation.
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_EFF = "growth.program_effectiveness_fact"
TABLE_DRV = "growth.driver_program_effectiveness_fact"
TABLE_MOV = "growth.yego_lima_v2_movement_fact"
TABLE_PR = "growth.yango_lima_program_eligibility_daily"


def get_effectiveness_summary() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT program_code, report_date, assigned_drivers,
                   positive_moves, negative_moves, neutral_moves,
                   effectiveness_score
            FROM {TABLE_EFF}
            ORDER BY report_date DESC, effectiveness_score DESC
        """)
        rows = cur.fetchall()
        if not rows:
            return {"programs": [], "total_programs": 0, "message": "No effectiveness data available yet."}

        programs = []
        for r in rows:
            pos = r[3] or 0
            neg = r[4] or 0
            assigned = r[2] or 0
            programs.append({
                "program_code": r[0],
                "report_date": str(r[1]) if r[1] else None,
                "assigned_drivers": assigned,
                "positive_moves": pos,
                "negative_moves": neg,
                "neutral_moves": r[5] or 0,
                "improvement_rate": round(pos / assigned * 100, 2) if assigned else 0,
                "decline_rate": round(neg / assigned * 100, 2) if assigned else 0,
                "net_effect": float(r[6]) if r[6] is not None else 0.0,
                "movement_score_delta": 0.0,
                "outcome_coverage_pct": 0.0,
            })

        latest_date = max(p["report_date"] for p in programs if p["report_date"])

        cur.execute(f"""
            SELECT COUNT(DISTINCT driver_profile_id) FROM {TABLE_DRV}
        """)
        total_drivers = (cur.fetchone() or [0])[0]

        cur.execute(f"""
            SELECT COUNT(DISTINCT driver_profile_id) FROM {TABLE_DRV}
            WHERE movement_score != 0
        """)
        drivers_with_outcome = (cur.fetchone() or [0])[0]

        cur.execute(f"""
            SELECT movement_type, COUNT(*) as cnt
            FROM {TABLE_DRV}
            WHERE movement_score != 0
            GROUP BY movement_type
            ORDER BY cnt DESC
        """)
        movement_types = [{"type": r[0], "count": r[1]} for r in cur.fetchall()]

        return {
            "programs": programs,
            "total_programs": len(programs),
            "latest_date": latest_date,
            "total_drivers_tracked": total_drivers,
            "drivers_with_outcome": drivers_with_outcome,
            "coverage_pct": round(drivers_with_outcome / total_drivers * 100, 2) if total_drivers else 0,
            "movement_types": movement_types,
        }


def get_program_effectiveness(program_code: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT program_code, report_date, assigned_drivers,
                   positive_moves, negative_moves, neutral_moves,
                   improvement_rate, decline_rate, net_effect,
                   movement_score_delta, outcome_coverage_pct,
                   lifecycle_delta_json
            FROM {TABLE_EFF}
            WHERE program_code = %(p)s
            ORDER BY report_date DESC
        """, {"p": program_code})
        rows = cur.fetchall()
        if not rows:
            return {"program_code": program_code, "found": False}

        latest = rows[0]
        history = []
        for r in rows:
            history.append({
                "report_date": str(r[1]) if r[1] else None,
                "assigned_drivers": r[2] or 0,
                "positive_moves": r[3] or 0,
                "negative_moves": r[4] or 0,
                "neutral_moves": r[5] or 0,
                "improvement_rate": float(r[6]) if r[6] is not None else 0,
                "decline_rate": float(r[7]) if r[7] is not None else 0,
                "net_effect": float(r[8]) if r[8] is not None else 0,
                "movement_score_delta": float(r[9]) if r[9] is not None else 0,
                "outcome_coverage_pct": float(r[10]) if r[10] is not None else 0,
            })

        cur.execute(f"""
            SELECT movement_type, movement_score, COUNT(*) as cnt
            FROM {TABLE_DRV}
            WHERE program_code = %(p)s AND movement_score != 0
            GROUP BY movement_type, movement_score
            ORDER BY cnt DESC
            LIMIT 20
        """, {"p": program_code})
        top_outcomes = [{"type": r[0], "score": r[1], "count": r[2]} for r in cur.fetchall()]

        cur.execute(f"""
            SELECT driver_profile_id, from_segment, to_segment,
                   from_lifecycle, to_lifecycle, movement_class,
                   movement_score, movement_type
            FROM {TABLE_DRV}
            WHERE program_code = %(p)s AND movement_score != 0
            ORDER BY ABS(movement_score) DESC
            LIMIT 10
        """, {"p": program_code})
        top_drivers = []
        for r in cur.fetchall():
            top_drivers.append({
                "driver_id": r[0],
                "from_segment": r[1], "to_segment": r[2],
                "from_lifecycle": r[3], "to_lifecycle": r[4],
                "movement_class": r[5], "score": r[6], "type": r[7],
            })

        return {
            "program_code": program_code,
            "found": True,
            "current": {
                "assigned_drivers": latest[2] or 0,
                "positive_moves": latest[3] or 0,
                "negative_moves": latest[4] or 0,
                "improvement_rate": float(latest[6]) if latest[6] is not None else 0,
                "decline_rate": float(latest[7]) if latest[7] is not None else 0,
                "net_effect": float(latest[8]) if latest[8] is not None else 0,
                "score_delta": float(latest[9]) if latest[9] is not None else 0,
            },
            "history": history,
            "top_outcomes": top_outcomes,
            "top_drivers": top_drivers,
        }


def get_driver_effectiveness(driver_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT program_code, from_segment, to_segment,
                   from_lifecycle, to_lifecycle, movement_class,
                   movement_score, movement_type, movement_date
            FROM {TABLE_DRV}
            WHERE driver_profile_id = %(did)s
            ORDER BY movement_date DESC LIMIT 5
        """, {"did": driver_id})
        rows = cur.fetchall()
        if not rows:
            return {"driver_id": driver_id, "found": False, "message": "No effectiveness data for this driver."}

        movements = []
        for r in rows:
            movements.append({
                "program": r[0],
                "from_segment": r[1], "to_segment": r[2],
                "from_lifecycle": r[3], "to_lifecycle": r[4],
                "movement_class": r[5], "score": r[6],
                "type": r[7], "date": str(r[8]) if r[8] else None,
            })

        return {
            "driver_id": driver_id,
            "found": True,
            "movements": movements,
            "net_score": sum(m["score"] for m in movements),
            "latest_program": movements[0]["program"] if movements else None,
        }
