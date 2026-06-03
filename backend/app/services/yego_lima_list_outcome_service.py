"""
YEGO Lima Growth — List Outcome Service (Fase 2C.1).

Daily outcome aggregation per actionable list type.
Crosses management_status counts with transition data.
"""

from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_OUTCOME = "growth.yango_lima_actionable_list_outcome_daily"
TABLE_LIST = "growth.yango_lima_actionable_list_daily"
TABLE_TRANSITION = "growth.yango_lima_driver_segment_transition_daily"


def build_list_outcomes(list_date_str: str) -> Dict[str, Any]:
    list_date = date.fromisoformat(list_date_str)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"SELECT DISTINCT list_type FROM {TABLE_LIST} WHERE list_date = %(d)s", {"d": list_date})
        list_types = [r["list_type"] for r in cur.fetchall()]

        if not list_types:
            return {"ok": False, "error": f"No lists found for {list_date_str}"}

        outcomes = []

        for lt in list_types:
            # Management status counts
            cur.execute(f"""
                SELECT
                    COUNT(*) AS generated,
                    SUM(CASE WHEN management_status = 'PENDING_ACTION' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN management_status = 'ACTION_CONFIRMED' THEN 1 ELSE 0 END) AS confirmed,
                    SUM(CASE WHEN management_status = 'ACTION_ATTEMPTED' THEN 1 ELSE 0 END) AS attempted,
                    SUM(CASE WHEN management_status = 'NO_ACTION' THEN 1 ELSE 0 END) AS no_action,
                    SUM(CASE WHEN management_status = 'DISMISSED' THEN 1 ELSE 0 END) AS dismissed
                FROM {TABLE_LIST}
                WHERE list_date = %(d)s AND list_type = %(lt)s
            """, {"d": list_date, "lt": lt})
            status_counts = dict(cur.fetchone())

            # Get driver IDs with confirmed actions from this list
            cur.execute(f"""
                SELECT driver_profile_id FROM {TABLE_LIST}
                WHERE list_date = %(d)s AND list_type = %(lt)s
                  AND management_status IN ('ACTION_CONFIRMED', 'ACTION_ATTEMPTED')
            """, {"d": list_date, "lt": lt})
            managed_drivers = [r["driver_profile_id"] for r in cur.fetchall()]

            improved = worsened = no_change = moved = reached = reactivated = 0

            if managed_drivers:
                # Transition impact in following days (up to 7 days after list_date)
                end_date = list_date + timedelta(days=7)
                cur.execute(f"""
                    SELECT
                        SUM(CASE WHEN movement_direction = 'IMPROVED' THEN 1 ELSE 0 END) AS imp,
                        SUM(CASE WHEN movement_direction = 'WORSENED' THEN 1 ELSE 0 END) AS wor,
                        SUM(CASE WHEN movement_direction = 'NO_CHANGE' THEN 1 ELSE 0 END) AS nc,
                        SUM(CASE WHEN segment_changed_flag THEN 1 ELSE 0 END) AS mv,
                        SUM(CASE WHEN current_segment_level_3 = 'RECOVERED' THEN 1 ELSE 0 END) AS react
                    FROM {TABLE_TRANSITION}
                    WHERE transition_date > %(ld)s AND transition_date <= %(ed)s
                      AND driver_profile_id = ANY(%(dids)s)
                      AND had_confirmed_action_flag = true
                """, {"ld": list_date, "ed": end_date, "dids": managed_drivers})
                trans = cur.fetchone()
                improved = int(trans["imp"] or 0)
                worsened = int(trans["wor"] or 0)
                no_change = int(trans["nc"] or 0)
                moved = int(trans["mv"] or 0)
                reactivated = int(trans["react"] or 0)

            total = int(status_counts["generated"] or 0)
            confirmed = int(status_counts["confirmed"] or 0)
            attempted = int(status_counts["attempted"] or 0)
            managed = confirmed + attempted

            outcomes.append({
                "list_date": list_date,
                "list_type": lt,
                "generated_count": total,
                "pending_count": int(status_counts["pending"] or 0),
                "action_confirmed_count": confirmed,
                "action_attempted_count": attempted,
                "no_action_count": int(status_counts["no_action"] or 0),
                "dismissed_count": int(status_counts["dismissed"] or 0),
                "improved_count": improved,
                "worsened_count": worsened,
                "no_change_count": no_change,
                "moved_segment_count": moved,
                "reached_target_count": 0,
                "reactivated_count": reactivated,
                "action_confirmation_rate": round(confirmed / managed * 100, 2) if managed else None,
                "movement_rate": round(moved / managed * 100, 2) if managed else None,
                "improvement_rate": round(improved / managed * 100, 2) if managed else None,
                "no_action_rate": round(status_counts["no_action"] / total * 100, 2) if total else None,
            })

        # Upsert
        for o in outcomes:
            cur.execute(f"""
                INSERT INTO {TABLE_OUTCOME} (
                    list_date, list_type,
                    generated_count, pending_count, action_confirmed_count, action_attempted_count,
                    no_action_count, dismissed_count,
                    improved_count, worsened_count, no_change_count,
                    moved_segment_count, reached_target_count, reactivated_count,
                    action_confirmation_rate, movement_rate, improvement_rate, no_action_rate
                ) VALUES (
                    %(list_date)s, %(list_type)s,
                    %(generated_count)s, %(pending_count)s, %(action_confirmed_count)s, %(action_attempted_count)s,
                    %(no_action_count)s, %(dismissed_count)s,
                    %(improved_count)s, %(worsened_count)s, %(no_change_count)s,
                    %(moved_segment_count)s, %(reached_target_count)s, %(reactivated_count)s,
                    %(action_confirmation_rate)s, %(movement_rate)s, %(improvement_rate)s, %(no_action_rate)s
                )
                ON CONFLICT (list_date, list_type) DO UPDATE SET
                    generated_count = EXCLUDED.generated_count,
                    action_confirmed_count = EXCLUDED.action_confirmed_count,
                    action_attempted_count = EXCLUDED.action_attempted_count,
                    no_action_count = EXCLUDED.no_action_count,
                    improved_count = EXCLUDED.improved_count,
                    movement_rate = EXCLUDED.movement_rate,
                    improvement_rate = EXCLUDED.improvement_rate,
                    no_action_rate = EXCLUDED.no_action_rate,
                    calculated_at = now()
            """, o)

        conn.commit()

    return {"ok": True, "list_date": list_date_str, "list_types_processed": len(outcomes)}


def get_list_outcome_summary(date_from: str, date_to: str,
                              list_type: Optional[str] = None) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        where = ["list_date >= %(df)s", "list_date <= %(dt)s"]
        params = {"df": date_from, "dt": date_to}
        if list_type:
            where.append("list_type = %(lt)s")
            params["lt"] = list_type

        cur.execute(f"""
            SELECT * FROM {TABLE_OUTCOME}
            WHERE {' AND '.join(where)}
            ORDER BY list_date DESC, list_type
        """, params)
        return [dict(r) for r in cur.fetchall()]


def get_list_outcome_detail(list_date_str: str, list_type: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT * FROM {TABLE_OUTCOME}
            WHERE list_date = %(d)s AND list_type = %(lt)s
        """, {"d": list_date_str, "lt": list_type})
        r = cur.fetchone()
        return dict(r) if r else {"error": "Not found"}
