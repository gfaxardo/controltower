"""
YEGO Lima Growth — Executive Metrics Service (Fase 2D.0 + Fase 2D-R).

Read-only aggregated metrics for future dashboard.
Sources (preferred): driver_state_snapshot, program_eligibility_daily, daily_opportunity_list.
Fallback: legacy segment_snapshot, actionable_list_daily.
"""

from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_STATE = "growth.yango_lima_driver_state_snapshot"
TABLE_PROGRAM = "growth.yango_lima_program_eligibility_daily"
TABLE_OPPORTUNITY = "growth.yango_lima_daily_opportunity_list"

TABLE_LEGACY_SNAPSHOT = "growth.yango_lima_driver_segment_snapshot"
TABLE_LEGACY_LIST = "growth.yango_lima_actionable_list_daily"


def _has_state_data(cur, query_date: str) -> bool:
    cur.execute(f"SELECT COUNT(*) AS cnt FROM {TABLE_STATE} WHERE snapshot_date = %(d)s", {"d": query_date})
    r = cur.fetchone()
    return r["cnt"] > 0 if r else False


def executive_summary(query_date: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if not query_date:
            cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_STATE}")
            r = cur.fetchone()
            if r and r["max"]:
                query_date = str(r["max"])
            else:
                cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_LEGACY_SNAPSHOT}")
                r = cur.fetchone()
                if not r or not r["max"]:
                    return {"error": "No snapshot data"}
                query_date = str(r["max"])

        use_new = _has_state_data(cur, query_date)

        if use_new:
            # ── CANONICAL: driver_state_snapshot ──
            cur.execute(f"""
                SELECT lifecycle_state, COUNT(*) AS cnt
                FROM {TABLE_STATE} WHERE snapshot_date = %(d)s
                GROUP BY lifecycle_state
            """, {"d": query_date})
            lc_dist = {r["lifecycle_state"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(f"""
                SELECT performance_state, COUNT(*) AS cnt
                FROM {TABLE_STATE} WHERE snapshot_date = %(d)s
                GROUP BY performance_state
            """, {"d": query_date})
            perf_dist = {r["performance_state"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(f"""
                SELECT retention_state, COUNT(*) AS cnt
                FROM {TABLE_STATE} WHERE snapshot_date = %(d)s
                GROUP BY retention_state
            """, {"d": query_date})
            ret_dist = {r["retention_state"]: r["cnt"] for r in cur.fetchall()}

            # Program counts
            cur.execute(f"""
                SELECT program_code, COUNT(*) AS cnt
                FROM {TABLE_PROGRAM} WHERE eligibility_date = %(d)s
                GROUP BY program_code
            """, {"d": query_date})
            prog_counts = {r["program_code"]: r["cnt"] for r in cur.fetchall()}

            # Opportunity counts
            cur.execute(f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN management_status = 'ACTION_CONFIRMED' THEN 1 ELSE 0 END) AS confirmed,
                    SUM(CASE WHEN management_status = 'ACTION_ATTEMPTED' THEN 1 ELSE 0 END) AS attempted,
                    SUM(CASE WHEN management_status = 'NO_ACTION' THEN 1 ELSE 0 END) AS no_action,
                    SUM(CASE WHEN management_status = 'PENDING_ACTION' THEN 1 ELSE 0 END) AS pending
                FROM {TABLE_OPPORTUNITY} WHERE opportunity_date = %(d)s
            """, {"d": query_date})
            actions = dict(cur.fetchone() or {})

            total_drivers = sum(lc_dist.values())
            managed = int(actions.get("confirmed") or 0) + int(actions.get("attempted") or 0)

            # 360_daily stats
            cur.execute("""
                SELECT COUNT(DISTINCT driver_profile_id) AS active,
                       SUM(completed_orders) AS orders,
                       SUM(supply_hours) AS supply
                FROM growth.yango_lima_driver_360_daily
                WHERE date = %(d)s AND active_flag = true
            """, {"d": query_date})
            d360 = dict(cur.fetchone() or {})

            active = int(d360.get("active") or 0)
            orders_total = int(d360.get("orders") or 0)
            supply_total = float(d360.get("supply") or 0)

            # Freshness
            cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_STATE}")
            fstate = str(cur.fetchone()["max"])
            cur.execute(f"SELECT MAX(eligibility_date) FROM {TABLE_PROGRAM}")
            fprog = str(cur.fetchone()["max"])
            cur.execute(f"SELECT MAX(opportunity_date) FROM {TABLE_OPPORTUNITY}")
            fopp = str(cur.fetchone()["max"])

            return {
                "date": query_date,
                "source": "state_based",
                "drivers_total": total_drivers,
                "lifecycle_distribution": lc_dist,
                "performance_distribution": perf_dist,
                "retention_distribution": ret_dist,
                "program_counts": prog_counts,
                "opportunity_total": int(actions.get("total") or 0),
                "drivers_managed_today": managed,
                "drivers_no_action_today": int(actions.get("no_action") or 0),
                "drivers_pending_today": int(actions.get("pending") or 0),
                "action_confirmation_rate": round(int(actions.get("confirmed") or 0) / max(managed, 1) * 100, 1),
                "avg_orders_per_driver": round(orders_total / active, 1) if active else 0,
                "total_supply_hours": round(supply_total, 2),
                "avg_trips_per_supply_hour": round(orders_total / supply_total, 2) if supply_total else 0,
                "freshness": {
                    "driver_state_max_date": fstate,
                    "program_eligibility_max_date": fprog,
                    "opportunity_max_date": fopp,
                },
            }

        else:
            # ── LEGACY FALLBACK: segment_snapshot ──
            cur.execute(f"""
                SELECT segment_level_1, COUNT(*) AS cnt
                FROM {TABLE_LEGACY_SNAPSHOT} WHERE snapshot_date = %(d)s
                GROUP BY segment_level_1
            """, {"d": query_date})
            l1 = {r["segment_level_1"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(f"""
                SELECT segment_level_2, COUNT(*) AS cnt
                FROM {TABLE_LEGACY_SNAPSHOT} WHERE snapshot_date = %(d)s
                GROUP BY segment_level_2
            """, {"d": query_date})
            l2 = {r["segment_level_2"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(f"""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN management_status = 'ACTION_CONFIRMED' THEN 1 ELSE 0 END) AS confirmed,
                    SUM(CASE WHEN management_status = 'ACTION_ATTEMPTED' THEN 1 ELSE 0 END) AS attempted,
                    SUM(CASE WHEN management_status = 'NO_ACTION' THEN 1 ELSE 0 END) AS no_action,
                    SUM(CASE WHEN management_status = 'PENDING_ACTION' THEN 1 ELSE 0 END) AS pending
                FROM {TABLE_LEGACY_LIST} WHERE list_date = %(d)s
            """, {"d": query_date})
            actions = dict(cur.fetchone() or {})

            cur.execute("""
                SELECT COUNT(DISTINCT driver_profile_id) AS active,
                       SUM(completed_orders) AS orders,
                       SUM(supply_hours) AS supply
                FROM growth.yango_lima_driver_360_daily
                WHERE date = %(d)s AND active_flag = true
            """, {"d": query_date})
            d360 = dict(cur.fetchone() or {})

            active = int(d360.get("active") or 0)
            orders_total = int(d360.get("orders") or 0)
            supply_total = float(d360.get("supply") or 0)

            cur.execute("SELECT MAX(date) FROM growth.yango_lima_driver_360_daily")
            f360 = str(cur.fetchone()["max"])
            cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_LEGACY_SNAPSHOT}")
            fseg = str(cur.fetchone()["max"])
            cur.execute("SELECT MAX(attribution_date) FROM growth.yango_lima_action_attribution_daily")
            fatt = str(cur.fetchone()["max"])

            total_drivers = sum(l1.values())
            managed = int(actions.get("confirmed") or 0) + int(actions.get("attempted") or 0)

            return {
                "date": query_date,
                "source": "legacy_fallback",
                "drivers_total": total_drivers,
                "l1_14_90_count": l1.get("NEW", 0) + l1.get("REACTIVATED", 0),
                "l2_active_growth_count": l2.get("LOYALTY_ACTIVE_GROWTH", 0),
                "l3_churn_prevention_count": l2.get("LOYALTY_CHURN_PREVENTION", 0),
                "drivers_managed_today": managed,
                "drivers_no_action_today": int(actions.get("no_action") or 0),
                "action_confirmation_rate": round(int(actions.get("confirmed") or 0) / max(managed, 1) * 100, 1),
                "avg_orders_per_driver": round(orders_total / active, 1) if active else 0,
                "total_supply_hours": round(supply_total, 2),
                "avg_trips_per_supply_hour": round(orders_total / supply_total, 2) if supply_total else 0,
                "freshness": {"driver360_max_date": f360, "segment_snapshot_max_date": fseg, "attribution_max_date": fatt},
            }


def executive_segments(query_date: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if not query_date:
            cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_segment_snapshot")
            query_date = str(cur.fetchone()["max"])

        cur.execute("""
            SELECT segment_level_1 AS level, COUNT(*) AS cnt FROM growth.yango_lima_driver_segment_snapshot
            WHERE snapshot_date = %(d)s GROUP BY 1 ORDER BY 2 DESC
        """, {"d": query_date})
        l1_dist = [{"level": r["level"], "count": r["cnt"]} for r in cur.fetchall()]

        cur.execute("""
            SELECT segment_level_2 AS level, COUNT(*) AS cnt FROM growth.yango_lima_driver_segment_snapshot
            WHERE snapshot_date = %(d)s GROUP BY 1 ORDER BY 2 DESC
        """, {"d": query_date})
        l2_dist = [{"level": r["level"], "count": r["cnt"]} for r in cur.fetchall()]

        cur.execute("""
            SELECT segment_level_3 AS level, COUNT(*) AS cnt FROM growth.yango_lima_driver_segment_snapshot
            WHERE snapshot_date = %(d)s GROUP BY 1 ORDER BY 2 DESC
        """, {"d": query_date})
        l3_dist = [{"level": r["level"], "count": r["cnt"]} for r in cur.fetchall()]

        cur.execute("""
            SELECT SUM(CASE WHEN recoverable_flag THEN 1 ELSE 0 END) AS recoverable,
                   SUM(CASE WHEN distance_to_target <= 10 THEN 1 ELSE 0 END) AS near_target,
                   SUM(CASE WHEN segment_level_1 = 'CHURN_RISK' THEN 1 ELSE 0 END) AS churn_risk
            FROM growth.yango_lima_driver_segment_snapshot WHERE snapshot_date = %(d)s
        """, {"d": query_date})
        extras = dict(cur.fetchone() or {})

        return {"date": query_date, "l1": l1_dist, "l2": l2_dist, "l3": l3_dist,
                "near_target": extras.get("near_target", 0), "recoverable": extras.get("recoverable", 0),
                "churn_risk": extras.get("churn_risk", 0)}


def executive_movements(date_from: str, date_to: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT movement_direction AS direction, COUNT(*) AS cnt FROM growth.yango_lima_driver_segment_transition_daily
            WHERE transition_date >= %(df)s AND transition_date <= %(dt)s
            GROUP BY 1 ORDER BY 2 DESC
        """, {"df": date_from, "dt": date_to})
        directions = [{"direction": r["direction"], "count": r["cnt"]} for r in cur.fetchall()]

        cur.execute("""
            SELECT prev_segment_level_3 AS from_seg, current_segment_level_3 AS to_seg, COUNT(*) AS cnt
            FROM growth.yango_lima_driver_segment_transition_daily
            WHERE transition_date >= %(df)s AND transition_date <= %(dt)s AND segment_changed_flag
            GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20
        """, {"df": date_from, "dt": date_to})
        matrix = [{"from": r["from_seg"] or "NEW", "to": r["to_seg"], "count": r["cnt"]} for r in cur.fetchall()]

        return {"date_from": date_from, "date_to": date_to, "directions": directions, "movement_matrix": matrix}


def executive_actions(query_date: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if not query_date:
            cur.execute("SELECT MAX(list_date) FROM growth.yango_lima_actionable_list_daily")
            query_date = str(cur.fetchone()["max"])

    cur.execute("""
        SELECT list_type AS lt, management_status AS ms, COUNT(*) AS cnt FROM growth.yango_lima_actionable_list_daily
        WHERE list_date = %(d)s GROUP BY 1,2 ORDER BY 1,2
    """, {"d": query_date})
    raw = [{"list_type": r["lt"], "status": r["ms"], "count": r["cnt"]} for r in cur.fetchall()]

    by_type: Dict[str, Any] = {}
    for r in raw:
        lt = r["list_type"]
        if lt not in by_type:
            by_type[lt] = {"generated": 0, "confirmed": 0, "attempted": 0, "no_action": 0, "dismissed": 0}
        by_type[lt][r["status"].lower().replace("action_", "").replace("pending_action", "pending")] = r["count"]

    return {"date": query_date, "by_list_type": [
        {"list_type": k, **v, "confirmation_rate": round(
            v.get("confirmed", 0) / max(v.get("confirmed", 0) + v.get("attempted", 0), 1) * 100, 1),
         "no_action_rate": round(v.get("no_action", 0) / max(sum(v.values()), 1) * 100, 1)}
        for k, v in by_type.items()
    ]}


def executive_agents(date_from: str, date_to: str) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT COALESCE(action_owner,'unassigned') AS agent, COUNT(*) AS assigned,
                   SUM(CASE WHEN action_confirmed THEN 1 ELSE 0 END) AS confirmed,
                   SUM(CASE WHEN action_status='attempted' AND NOT action_confirmed THEN 1 ELSE 0 END) AS attempted
            FROM growth.yango_lima_driver_action_registry
            WHERE action_date >= %(df)s AND action_date <= %(dt)s
            GROUP BY action_owner ORDER BY assigned DESC
        """, {"df": date_from, "dt": date_to})

        agents = []
        for r in cur.fetchall():
            agent = dict(r)
            total = agent["assigned"]
            agent["movement_rate"] = 0
            agent["improvement_rate"] = 0
            agent["confirmation_rate"] = round(agent["confirmed"] / total * 100, 1) if total else 0
            agents.append(agent)
        return agents


def executive_campaigns(date_from: str, date_to: str) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT campaign_code, COUNT(*) AS drivers_confirmed,
                   SUM(CASE WHEN action_confirmed THEN 1 ELSE 0 END) AS confirmed
            FROM growth.yango_lima_driver_action_registry
            WHERE action_date >= %(df)s AND action_date <= %(dt)s AND campaign_code IS NOT NULL
            GROUP BY campaign_code ORDER BY 2 DESC
        """, {"df": date_from, "dt": date_to})
        return [dict(r) for r in cur.fetchall()]


def executive_freshness() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        layers = [
            ("orders_raw", "growth.yango_lima_orders_raw", "MAX(ended_at)"),
            ("driver360_daily", "growth.yango_lima_driver_360_daily", "MAX(date)"),
            ("segment_snapshot", "growth.yango_lima_driver_segment_snapshot", "MAX(snapshot_date)"),
            ("actionable_list_daily", "growth.yango_lima_actionable_list_daily", "MAX(list_date)"),
            ("action_registry", "growth.yango_lima_driver_action_registry", "MAX(action_date)"),
            ("daily_impact", "growth.yango_lima_driver_action_daily_impact", "MAX(impact_date)"),
            ("transitions", "growth.yango_lima_driver_segment_transition_daily", "MAX(transition_date)"),
            ("list_outcomes", "growth.yango_lima_actionable_list_outcome_daily", "MAX(list_date)"),
            ("attribution", "growth.yango_lima_action_attribution_daily", "MAX(attribution_date)"),
        ]
        result = {}
        for name, table, col in layers:
            try:
                cur.execute(f"SELECT {col} FROM {table}")
                r = cur.fetchone()
                result[name] = {"max_date": str(r[0]) if r and r[0] else None, "status": "ok" if r and r[0] else "empty"}
            except Exception:
                result[name] = {"max_date": None, "status": "missing"}
        return result
