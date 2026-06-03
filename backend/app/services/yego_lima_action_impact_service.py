"""
YEGO Lima Growth — Action Impact Service (Fase 2C).

Measures daily impact of actions on drivers.
Tracks orders, supply, segment movement post-action.
"""

from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

TABLE_IMPACT = "growth.yango_lima_driver_action_daily_impact"
TABLE_ACTIONS = "growth.yango_lima_driver_action_registry"
TABLE_360 = "growth.yango_lima_driver_360_daily"
TABLE_SNAPSHOT = "growth.yango_lima_driver_segment_snapshot"


def build_daily_impact_for_date(impact_date_str: str) -> Dict[str, Any]:
    impact_date = date.fromisoformat(impact_date_str)
    window = int(settings.LIMA_GROWTH_IMPACT_WINDOW_DAYS)
    baseline_days = int(settings.LIMA_GROWTH_IMPACT_BASELINE_DAYS)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        start = impact_date - timedelta(days=window)
        cur.execute(f"""
            SELECT action_id, driver_profile_id, action_date,
                   source_segment_snapshot_date
            FROM {TABLE_ACTIONS}
            WHERE action_date >= %(start)s AND action_date <= %(end)s
        """, {"start": start, "end": impact_date})
        actions = [dict(r) for r in cur.fetchall()]

        if not actions:
            return {"ok": True, "impact_date": impact_date_str, "actions_processed": 0}

        count = 0
        for act in actions:
            action_id = str(act["action_id"])
            driver = act["driver_profile_id"]
            action_date_val = act["action_date"]
            days_since = (impact_date - action_date_val).days

            # Get current day data from 360_daily
            cur.execute(f"""
                SELECT SUM(completed_orders) AS orders, SUM(supply_hours) AS supply
                FROM {TABLE_360}
                WHERE driver_profile_id = %(did)s AND date = %(d)s
            """, {"did": driver, "d": impact_date})
            day_data = cur.fetchone()
            orders = int(day_data["orders"] or 0) if day_data else 0
            supply = float(day_data["supply"] or 0) if day_data else 0

            # Get baseline (7 days before action)
            bl_start = action_date_val - timedelta(days=baseline_days)
            cur.execute(f"""
                SELECT AVG(completed_orders) AS avg_orders, AVG(supply_hours) AS avg_supply
                FROM {TABLE_360}
                WHERE driver_profile_id = %(did)s
                  AND date >= %(bl)s AND date < %(ad)s
            """, {"did": driver, "bl": bl_start, "ad": action_date_val})
            bl_data = cur.fetchone()
            bl_orders = float(bl_data["avg_orders"] or 0) if bl_data else 0
            bl_supply = float(bl_data["avg_supply"] or 0) if bl_data else 0

            # Get current segment
            cur.execute(f"""
                SELECT segment_level_1, segment_level_2, segment_level_3,
                       driver_state, productivity_band
                FROM {TABLE_SNAPSHOT}
                WHERE driver_profile_id = %(did)s AND snapshot_date <= %(d)s
                ORDER BY snapshot_date DESC LIMIT 1
            """, {"did": driver, "d": impact_date})
            seg = cur.fetchone()

            # Get previous segment for movement check
            cur.execute(f"""
                SELECT segment_level_3 FROM {TABLE_SNAPSHOT}
                WHERE driver_profile_id = %(did)s AND snapshot_date < %(ad)s
                ORDER BY snapshot_date DESC LIMIT 1
            """, {"did": driver, "ad": action_date_val})
            prev_seg = cur.fetchone()
            prev_l3 = prev_seg["segment_level_3"] if prev_seg else None

            cur_l3 = seg["segment_level_3"] if seg else None
            moved = (prev_l3 is not None and cur_l3 is not None and prev_l3 != cur_l3)

            cur.execute(f"""
                INSERT INTO {TABLE_IMPACT} (
                    action_id, impact_date, driver_profile_id, days_since_action,
                    completed_orders_day, supply_hours_day, trips_per_supply_hour_day,
                    segment_level_1, segment_level_2, segment_level_3,
                    driver_state, productivity_band,
                    baseline_completed_orders_7d, baseline_supply_hours_7d,
                    delta_orders_vs_baseline, delta_supply_vs_baseline,
                    moved_segment_flag, improved_orders_flag, improved_supply_flag,
                    reactivated_flag, reached_target_flag
                ) VALUES (
                    %(aid)s::uuid, %(d)s, %(did)s, %(dsa)s,
                    %(o)s, %(sh)s, %(tph)s,
                    %(sl1)s, %(sl2)s, %(sl3)s,
                    %(st)s, %(pb)s,
                    %(blo)s, %(bls)s,
                    %(do)s, %(dss)s,
                    %(mv)s, %(io)s, %(is)s,
                    %(re)s, %(rt)s
                )
                ON CONFLICT (action_id, impact_date) DO UPDATE SET
                    completed_orders_day = EXCLUDED.completed_orders_day,
                    supply_hours_day = EXCLUDED.supply_hours_day,
                    segment_level_3 = EXCLUDED.segment_level_3,
                    moved_segment_flag = EXCLUDED.moved_segment_flag,
                    improved_orders_flag = EXCLUDED.improved_orders_flag,
                    improved_supply_flag = EXCLUDED.improved_supply_flag,
                    reactivated_flag = EXCLUDED.reactivated_flag,
                    reached_target_flag = EXCLUDED.reached_target_flag,
                    calculated_at = now()
            """, {
                "aid": action_id, "d": impact_date, "did": driver, "dsa": days_since,
                "o": orders, "sh": round(supply, 4),
                "tph": round(orders / supply, 4) if supply > 0 else None,
                "sl1": seg["segment_level_1"] if seg else None,
                "sl2": seg["segment_level_2"] if seg else None,
                "sl3": seg["segment_level_3"] if seg else None,
                "st": seg["driver_state"] if seg else None,
                "pb": seg["productivity_band"] if seg else None,
                "blo": round(bl_orders, 4) if bl_orders else None,
                "bls": round(bl_supply, 4) if bl_supply else None,
                "do": round(orders - bl_orders, 4),
                "dss": round(supply - bl_supply, 4),
                "mv": moved,
                "io": orders > bl_orders,
                "is": supply > bl_supply,
                "re": prev_l3 in ("CHURNED", "CHURN_RISK") and cur_l3 not in ("CHURNED", "CHURN_RISK"),
                "rt": orders >= int(settings.LIMA_GROWTH_WEEKLY_TRIPS_TARGET),
            })
            count += 1

        conn.commit()

    return {"ok": True, "impact_date": impact_date_str, "actions_processed": count}


def build_impact_for_action(action_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT action_date FROM {TABLE_ACTIONS} WHERE action_id = %(aid)s::uuid", {"aid": action_id})
        r = cur.fetchone()
        if not r:
            return {"ok": False, "error": "Action not found"}

        action_date_val = r["action_date"]
        today = date.today()
        count = 0
        d = action_date_val + timedelta(days=1)
        while d <= today:
            result = build_daily_impact_for_date(d.isoformat())
            count += result.get("actions_processed", 0)
            d += timedelta(days=1)

    return {"ok": True, "action_id": action_id, "days_processed": count}


def summarize_agent_performance(date_from: str, date_to: str,
                                action_owner: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        owner_filter = "AND a.action_owner = %(ao)s" if action_owner else ""

        cur.execute(f"""
            SELECT
                COALESCE(a.action_owner, 'unassigned') AS agent,
                COUNT(DISTINCT a.action_id) AS assigned_items,
                SUM(CASE WHEN a.action_confirmed THEN 1 ELSE 0 END) AS action_confirmed_count,
                SUM(CASE WHEN a.action_status = 'attempted' AND NOT a.action_confirmed THEN 1 ELSE 0 END) AS action_attempted_count,
                ROUND(AVG(COALESCE(i.delta_orders_vs_baseline, 0))::numeric, 2) AS avg_delta_orders,
                ROUND(AVG(COALESCE(i.delta_supply_vs_baseline, 0))::numeric, 2) AS avg_delta_supply,
                SUM(CASE WHEN i.moved_segment_flag THEN 1 ELSE 0 END) AS moved_segment_count,
                SUM(CASE WHEN i.reactivated_flag THEN 1 ELSE 0 END) AS reactivated_count
            FROM {TABLE_ACTIONS} a
            LEFT JOIN {TABLE_IMPACT} i ON a.action_id = i.action_id
            WHERE a.action_date >= %(df)s AND a.action_date <= %(dt)s {owner_filter}
            GROUP BY a.action_owner
            ORDER BY assigned_items DESC
        """, {"df": date_from, "dt": date_to, "ao": action_owner} if action_owner
           else {"df": date_from, "dt": date_to})

        agents = []
        for row in cur.fetchall():
            r = dict(row)
            total = r["assigned_items"]
            r["confirmation_rate"] = round(r["action_confirmed_count"] / total * 100, 1) if total else 0
            r["contacted_rate"] = round((r["action_confirmed_count"] + r["action_attempted_count"]) / total * 100, 1) if total else 0
            agents.append(r)

        return {"date_from": date_from, "date_to": date_to, "agents": agents}


def summarize_impact_by_segment(date_from: str, date_to: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT segment_level_3, COUNT(*) AS cnt,
                   ROUND(AVG(delta_orders_vs_baseline)::numeric, 2) AS avg_delta_orders,
                   SUM(CASE WHEN improved_orders_flag THEN 1 ELSE 0 END) AS improved_count,
                   SUM(CASE WHEN moved_segment_flag THEN 1 ELSE 0 END) AS moved_count,
                   SUM(CASE WHEN reactivated_flag THEN 1 ELSE 0 END) AS reactivated_count,
                   SUM(CASE WHEN reached_target_flag THEN 1 ELSE 0 END) AS reached_target_count
            FROM {TABLE_IMPACT}
            WHERE impact_date >= %(df)s AND impact_date <= %(dt)s
            GROUP BY segment_level_3 ORDER BY cnt DESC
        """, {"df": date_from, "dt": date_to})
        return {"date_from": date_from, "date_to": date_to, "segments": [dict(r) for r in cur.fetchall()]}


def get_driver_impact_timeline(driver_profile_id: str, limit: int = 30) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT i.impact_date, i.days_since_action,
                   i.completed_orders_day, i.supply_hours_day,
                   i.segment_level_3, i.driver_state,
                   i.moved_segment_flag, i.improved_orders_flag,
                   i.improved_supply_flag, i.reactivated_flag,
                   i.delta_orders_vs_baseline,
                   a.action_type, a.action_owner, a.action_status, a.action_confirmed
            FROM {TABLE_IMPACT} i
            LEFT JOIN {TABLE_ACTIONS} a ON i.action_id = a.action_id
            WHERE i.driver_profile_id = %(did)s
            ORDER BY i.impact_date DESC
            LIMIT %(limit)s
        """, {"did": driver_profile_id, "limit": min(limit, 100)})
        return [dict(r) for r in cur.fetchall()]
