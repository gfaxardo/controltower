"""
YEGO Lima Growth — Impact Attribution Engine (Fase 2C.2).

Attribution: which agents, campaigns, segments, action types, and channels
generate measurable driver movement and improvement.

Sources:
- growth.yango_lima_driver_action_registry
- growth.yango_lima_driver_action_daily_impact
- growth.yango_lima_driver_segment_transition_daily
"""

from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

TABLE_ATTRIBUTION = "growth.yango_lima_action_attribution_daily"
TABLE_ACTIONS = "growth.yango_lima_driver_action_registry"
TABLE_IMPACT = "growth.yango_lima_driver_action_daily_impact"
TABLE_TRANSITION = "growth.yango_lima_driver_segment_transition_daily"

SCOPES = ["AGENT", "CAMPAIGN", "SEGMENT", "ACTION_TYPE", "ACTION_CHANNEL"]


def _upsert_attribution(cur, rows):
    sql = """
        INSERT INTO growth.yango_lima_action_attribution_daily (
            attribution_date, attribution_scope, attribution_key,
            drivers_assigned, drivers_contacted, drivers_attempted, drivers_confirmed, drivers_no_action,
            drivers_moved, drivers_improved, drivers_worsened, drivers_reactivated, drivers_recovered, drivers_reached_target,
            orders_delta_total, orders_delta_avg, supply_delta_total, supply_delta_avg, productivity_delta_avg,
            contact_rate, movement_rate, improvement_rate, target_reached_rate, reactivation_rate,
            attribution_window_days
        ) VALUES (
            %(attribution_date)s, %(attribution_scope)s, %(attribution_key)s,
            %(drivers_assigned)s, %(drivers_contacted)s, %(drivers_attempted)s, %(drivers_confirmed)s, %(drivers_no_action)s,
            %(drivers_moved)s, %(drivers_improved)s, %(drivers_worsened)s, %(drivers_reactivated)s, %(drivers_recovered)s, %(drivers_reached_target)s,
            %(orders_delta_total)s, %(orders_delta_avg)s, %(supply_delta_total)s, %(supply_delta_avg)s, %(productivity_delta_avg)s,
            %(contact_rate)s, %(movement_rate)s, %(improvement_rate)s, %(target_reached_rate)s, %(reactivation_rate)s,
            %(attribution_window_days)s
        )
        ON CONFLICT (attribution_date, attribution_scope, attribution_key) DO UPDATE SET
            drivers_assigned = EXCLUDED.drivers_assigned,
            drivers_moved = EXCLUDED.drivers_moved,
            drivers_improved = EXCLUDED.drivers_improved,
            drivers_reached_target = EXCLUDED.drivers_reached_target,
            improvement_rate = EXCLUDED.improvement_rate,
            movement_rate = EXCLUDED.movement_rate,
            calculated_at = now()
    """
    for row in rows:
        cur.execute(sql, row)


def build_daily_attribution(attribution_date_str: str) -> Dict[str, Any]:
    adate = date.fromisoformat(attribution_date_str)
    window = int(settings.LIMA_GROWTH_ATTRIBUTION_WINDOW_DAYS)
    wstart = adate - timedelta(days=window)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Actions in window
        cur.execute(f"""
            SELECT action_owner, campaign_code, action_type, action_channel,
                   action_status, action_confirmed, driver_profile_id
            FROM {TABLE_ACTIONS}
            WHERE action_date >= %(ws)s AND action_date <= %(ad)s
        """, {"ws": wstart, "ad": adate})
        actions = [dict(r) for r in cur.fetchall()]

        # Transitions in window
        cur.execute(f"""
            SELECT driver_profile_id, movement_direction, segment_changed_flag,
                   orders_delta
            FROM {TABLE_TRANSITION}
            WHERE transition_date >= %(ws)s AND transition_date <= %(ad)s
        """, {"ws": wstart, "ad": adate})
        transitions = [dict(r) for r in cur.fetchall()]

        # Impact data
        cur.execute(f"""
            SELECT driver_profile_id, delta_orders_vs_baseline, delta_supply_vs_baseline,
                   improved_orders_flag, moved_segment_flag, reactivated_flag, reached_target_flag
            FROM {TABLE_IMPACT}
            WHERE impact_date >= %(ws)s AND impact_date <= %(ad)s
        """, {"ws": wstart, "ad": adate})
        impacts = [dict(r) for r in cur.fetchall()]

        if not actions:
            return {"ok": True, "attribution_date": attribution_date_str, "rows": 0, "message": "No actions in window"}

        # Index by driver
        trans_by_driver: Dict[str, list] = {}
        for t in transitions:
            trans_by_driver.setdefault(t["driver_profile_id"], []).append(t)

        impact_by_driver: Dict[str, list] = {}
        for i in impacts:
            impact_by_driver.setdefault(i["driver_profile_id"], []).append(i)

        all_rows = []

        for scope in SCOPES:
            scope_actions = actions
            if scope == "AGENT":
                groups = _group_by(actions, "action_owner", "unassigned")
            elif scope == "CAMPAIGN":
                groups = _group_by(actions, "campaign_code", "no_campaign")
                groups = {k: v for k, v in groups.items() if k and k != "no_campaign"}
            elif scope == "SEGMENT":
                groups = _group_by_segment(actions, trans_by_driver)
            elif scope == "ACTION_TYPE":
                groups = _group_by(actions, "action_type", "unknown")
            elif scope == "ACTION_CHANNEL":
                groups = _group_by(actions, "action_channel", "unknown")
            else:
                continue

            for key, acts in groups.items():
                if not key:
                    continue

                assigned = len(acts)
                contacted = sum(1 for a in acts if a["action_status"] == "contacted")
                attempted = sum(1 for a in acts if a["action_status"] == "attempted" and not a["action_confirmed"])
                confirmed = sum(1 for a in acts if a["action_confirmed"])
                no_action = assigned - contacted - attempted - confirmed
                if no_action < 0:
                    no_action = 0

                driver_ids = list({a["driver_profile_id"] for a in acts})

                moved = improved = worsened = reactivated = recovered = reached = 0
                orders_delta_total = 0.0
                supply_delta_total = 0.0

                for did in driver_ids:
                    dr_trans = trans_by_driver.get(did, [])
                    dr_impact = impact_by_driver.get(did, [])

                    for t in dr_trans:
                        md = t["movement_direction"]
                        if md != "NO_CHANGE":
                            moved += 1
                        if md == "IMPROVED" or md == "RECOVERED":
                            improved += 1
                        if md == "WORSENED" or md == "LOST":
                            worsened += 1
                        if md == "RECOVERED":
                            recovered += 1
                        if t["orders_delta"] is not None:
                            orders_delta_total += float(t["orders_delta"])

                    for i in dr_impact:
                        if i["reactivated_flag"]:
                            reactivated += 1
                        if i["reached_target_flag"]:
                            reached += 1
                        if i["delta_supply_vs_baseline"] is not None:
                            supply_delta_total += float(i["delta_supply_vs_baseline"])

                row = {
                    "attribution_date": adate,
                    "attribution_scope": scope,
                    "attribution_key": key,
                    "drivers_assigned": assigned,
                    "drivers_contacted": contacted,
                    "drivers_attempted": attempted,
                    "drivers_confirmed": confirmed,
                    "drivers_no_action": no_action,
                    "drivers_moved": moved,
                    "drivers_improved": improved,
                    "drivers_worsened": worsened,
                    "drivers_reactivated": reactivated,
                    "drivers_recovered": recovered,
                    "drivers_reached_target": reached,
                    "orders_delta_total": round(orders_delta_total, 4) if orders_delta_total else None,
                    "orders_delta_avg": round(orders_delta_total / assigned, 4) if assigned and orders_delta_total else None,
                    "supply_delta_total": round(supply_delta_total, 4) if supply_delta_total else None,
                    "supply_delta_avg": round(supply_delta_total / assigned, 4) if assigned and supply_delta_total else None,
                    "productivity_delta_avg": None,
                    "contact_rate": round(contacted / assigned * 100, 2) if assigned else None,
                    "movement_rate": round(moved / assigned * 100, 2) if assigned else None,
                    "improvement_rate": round(improved / assigned * 100, 2) if assigned else None,
                    "target_reached_rate": round(reached / assigned * 100, 2) if assigned else None,
                    "reactivation_rate": round(reactivated / assigned * 100, 2) if assigned else None,
                    "attribution_window_days": window,
                }
                all_rows.append(row)

        if all_rows:
            _upsert_attribution(cur, all_rows)
            conn.commit()

        return {"ok": True, "attribution_date": attribution_date_str, "rows": len(all_rows)}


def _group_by(items, key, default):
    groups: Dict[str, list] = {}
    for item in items:
        k = item.get(key) or default
        groups.setdefault(k, []).append(item)
    return groups


def _group_by_segment(actions, trans_by_driver):
    groups: Dict[str, list] = {}
    for a in actions:
        did = a["driver_profile_id"]
        trans_list = trans_by_driver.get(did, [])
        if trans_list:
            seg = trans_list[-1].get("current_segment_level_2") if hasattr(trans_list[-1], 'get') else None
            key = seg or "UNKNOWN"
        else:
            key = "UNKNOWN"
        groups.setdefault(key, []).append(a)
    return groups


def get_attribution_summary(date_from: str, date_to: str, scope: Optional[str] = None) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        where = ["attribution_date >= %(df)s", "attribution_date <= %(dt)s"]
        params = {"df": date_from, "dt": date_to}
        if scope:
            where.append("attribution_scope = %(sc)s")
            params["sc"] = scope

        cur.execute(f"""
            SELECT * FROM {TABLE_ATTRIBUTION}
            WHERE {' AND '.join(where)}
            ORDER BY drivers_assigned DESC
        """, params)
        return [dict(r) for r in cur.fetchall()]


def get_attribution_by_scope(date_from: str, date_to: str, scope: str) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT * FROM {TABLE_ATTRIBUTION}
            WHERE attribution_date >= %(df)s AND attribution_date <= %(dt)s
              AND attribution_scope = %(sc)s
            ORDER BY drivers_assigned DESC
        """, {"df": date_from, "dt": date_to, "sc": scope})
        return [dict(r) for r in cur.fetchall()]


def get_top_performing(date_from: str, date_to: str, scope: str, metric: str = "improvement_rate",
                       limit: int = 10) -> list:
    valid = {"improvement_rate", "movement_rate", "target_reached_rate", "contact_rate", "drivers_improved", "drivers_reached_target"}
    if metric not in valid:
        metric = "improvement_rate"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT attribution_key, drivers_assigned, drivers_moved, drivers_improved,
                   drivers_reached_target, improvement_rate, movement_rate, contact_rate
            FROM {TABLE_ATTRIBUTION}
            WHERE attribution_date >= %(df)s AND attribution_date <= %(dt)s
              AND attribution_scope = %(sc)s
            ORDER BY {metric} DESC NULLS LAST
            LIMIT %(limit)s
        """, {"df": date_from, "dt": date_to, "sc": scope, "limit": limit})
        return [dict(r) for r in cur.fetchall()]
