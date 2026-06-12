"""
LG-MOV-2A — Movement Analytics Service
Reads from growth.driver_movement_fact. NO recalculation.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from app.db.connection import get_db

logger = logging.getLogger(__name__)
TABLE_MOV = "growth.yego_lima_v2_movement_fact"


def get_transition_matrix() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_MOV}")
        total = (cur.fetchone() or [0])[0]

        cur.execute(f"""
            SELECT from_state AS from_segment, to_state AS to_segment, COUNT(*) as cnt
            FROM {TABLE_MOV}
            WHERE movement_type = 'SEGMENT_CHANGE'
            GROUP BY from_state, to_state
            ORDER BY cnt DESC
        """)
        segment_transitions = [{"from": r[0], "to": r[1], "count": r[2]} for r in cur.fetchall()]

        cur.execute(f"""
            SELECT from_state AS from_lifecycle, to_state AS to_lifecycle, COUNT(*) as cnt
            FROM {TABLE_MOV}
            WHERE movement_type = 'LIFECYCLE_CHANGE'
            GROUP BY from_state, to_state
            ORDER BY cnt DESC
        """)
        lifecycle_transitions = [{"from": r[0], "to": r[1], "count": r[2]} for r in cur.fetchall()]

        cur.execute(f"""
            SELECT from_program, to_program, COUNT(*) as cnt
            FROM {TABLE_MOV}
            WHERE movement_type = 'PROGRAM_CHANGE' AND from_program IS DISTINCT FROM to_program
            GROUP BY from_program, to_program
            ORDER BY cnt DESC
            LIMIT 30
        """)
        program_transitions = [{"from": r[0], "to": r[1], "count": r[2]} for r in cur.fetchall()]

        cur.execute(f"""
            SELECT movement_type AS movement_class, 0 AS movement_score, COUNT(*) as cnt
            FROM {TABLE_MOV}
            WHERE movement_type IS NOT NULL
            GROUP BY movement_type
            ORDER BY cnt DESC
        """)
        score_distribution = [{"class": r[0], "score": r[1], "count": r[2]} for r in cur.fetchall()]

        return {
            "total_movements": total,
            "segment_transitions": segment_transitions,
            "lifecycle_transitions": lifecycle_transitions,
            "program_transitions": program_transitions,
            "score_distribution": score_distribution,
        }


def get_top_winners(limit: int = 20) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT driver_id, from_state AS from_segment, to_state AS to_segment,
                   from_state AS from_lifecycle, to_state AS to_lifecycle, movement_type AS movement_class,
                   0 AS movement_score, movement_type, from_program, to_program
            FROM {TABLE_MOV}
            WHERE movement_type IN ('SEGMENT_CHANGE', 'LIFECYCLE_CHANGE', 'PROGRAM_CHANGE')
            ORDER BY driver_id
            LIMIT %(lim)s
        """, {"lim": limit})
        winners = []
        for r in cur.fetchall():
            winners.append({
                "driver_id": r[0],
                "from_segment": r[1], "to_segment": r[2],
                "from_lifecycle": r[3], "to_lifecycle": r[4],
                "movement_class": r[5], "score": r[6],
                "movement_type": r[7], "program": r[8] or r[9],
            })
        return {"top_winners": winners, "count": len(winners)}


def get_top_losers(limit: int = 20) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT driver_id, from_state AS from_segment, to_state AS to_segment,
                   from_state AS from_lifecycle, to_state AS to_lifecycle, movement_type AS movement_class,
                   0 AS movement_score, movement_type, from_program, to_program
            FROM {TABLE_MOV}
            WHERE movement_type IN ('SEGMENT_CHANGE', 'LIFECYCLE_CHANGE', 'PROGRAM_CHANGE')
            ORDER BY driver_id DESC
            LIMIT %(lim)s
        """, {"lim": limit})
        losers = []
        for r in cur.fetchall():
            losers.append({
                "driver_id": r[0],
                "from_segment": r[1], "to_segment": r[2],
                "from_lifecycle": r[3], "to_lifecycle": r[4],
                "movement_class": r[5], "score": r[6],
                "movement_type": r[7], "program": r[8] or r[9],
            })
        return {"top_losers": losers, "count": len(losers)}


def get_movement_stats() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_MOV}")
        total = (cur.fetchone() or [0])[0]

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_MOV} WHERE movement_type = 'SEGMENT_CHANGE'")
        positive = (cur.fetchone() or [0])[0]

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_MOV} WHERE movement_type = 'LIFECYCLE_CHANGE'")
        negative = (cur.fetchone() or [0])[0]

        cur.execute(f"SELECT 0")
        net = (cur.fetchone() or [0])[0]

        cur.execute(f"""
            SELECT movement_type AS movement_class, COUNT(*) as cnt
            FROM {TABLE_MOV}
            WHERE movement_type IS NOT NULL
            GROUP BY movement_type ORDER BY cnt DESC
        """)
        classes = [{"class": r[0], "count": r[1]} for r in cur.fetchall()]

        return {
            "total_transitions": total,
            "positive_transitions": positive,
            "negative_transitions": negative,
            "net_movement": float(net),
            "positive_pct": round(positive / total * 100, 2) if total else 0,
            "negative_pct": round(negative / total * 100, 2) if total else 0,
            "movement_classes": classes,
        }
