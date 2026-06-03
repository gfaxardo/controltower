"""
YEGO Lima Growth — Segment Migration Service (Fase 2C.1).

Tracks daily segment transitions per driver.
Compares prev vs current snapshot, computes movement direction.
Attributes actions to transitions.
"""

from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

TABLE_TRANSITION = "growth.yango_lima_driver_segment_transition_daily"
TABLE_SNAPSHOT = "growth.yango_lima_driver_segment_snapshot"
TABLE_ACTIONS = "growth.yango_lima_driver_action_registry"

IMPROVED = "IMPROVED"
WORSENED = "WORSENED"
NO_CHANGE = "NO_CHANGE"
NEW_ENTRY = "NEW_ENTRY"
RECOVERED = "RECOVERED"
LOST = "LOST"
UNKNOWN = "UNKNOWN"

DIRECTION_ORDER = {IMPROVED: 1, RECOVERED: 2, NEW_ENTRY: 3, NO_CHANGE: 4, WORSENED: 5, LOST: 6, UNKNOWN: 7}


def _determine_direction(prev_l3: Optional[str], cur_l3: Optional[str],
                         prev_l1: Optional[str], cur_l1: Optional[str]) -> str:
    if prev_l1 is None and cur_l1 is not None:
        return NEW_ENTRY
    if cur_l1 == "CHURNED" and prev_l1 not in (None, "CHURNED"):
        return LOST
    if cur_l3 == "RECOVERED" and prev_l3 != "RECOVERED":
        return RECOVERED

    recovery_states = {"RECOVERED", "ACTIVE", "STABLE", "NEAR_TARGET"}
    if cur_l3 in recovery_states and prev_l3 in ("CHURNED", "CHURN_RISK", "DECLINING_4W", "DECLINING_12W", "CHURNED"):
        return IMPROVED
    if prev_l3 in recovery_states and cur_l3 in ("CHURNED", "CHURN_RISK", "DECLINING_4W", "DECLINING_12W"):
        return WORSENED

    return NO_CHANGE


def build_segment_transitions(transition_date_str: str) -> Dict[str, Any]:
    tdate = date.fromisoformat(transition_date_str)
    lookback = int(settings.LIMA_GROWTH_TRANSITION_LOOKBACK_DAYS)
    attribution = int(settings.LIMA_GROWTH_ACTION_ATTRIBUTION_DAYS)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Current snapshot
        cur.execute(f"""
            SELECT * FROM {TABLE_SNAPSHOT}
            WHERE snapshot_date <= %(d)s
            ORDER BY snapshot_date DESC LIMIT 1
        """, {"d": tdate})
        cur_snap_row = cur.fetchone()
        if not cur_snap_row:
            return {"ok": False, "error": "No current snapshot found"}
        cur_snap_date = cur_snap_row["snapshot_date"]

        cur.execute(f"""
            SELECT * FROM {TABLE_SNAPSHOT}
            WHERE snapshot_date = %(ds)s
        """, {"ds": cur_snap_date})
        current = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        # Previous snapshot
        prev_start = cur_snap_date - timedelta(days=lookback)
        cur.execute(f"""
            SELECT DISTINCT ON (driver_profile_id) *
            FROM {TABLE_SNAPSHOT}
            WHERE snapshot_date >= %(ps)s AND snapshot_date < %(cs)s
            ORDER BY driver_profile_id, snapshot_date DESC
        """, {"ps": prev_start, "cs": cur_snap_date})
        previous = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        # Actions in attribution window
        attr_start = tdate - timedelta(days=attribution)
        cur.execute(f"""
            SELECT DISTINCT ON (driver_profile_id)
                driver_profile_id, action_id, action_type, action_owner,
                campaign_code, action_confirmed
            FROM {TABLE_ACTIONS}
            WHERE action_date >= %(as)s AND action_date <= %(ts)s
            ORDER BY driver_profile_id, action_confirmed DESC, action_date DESC
        """, {"as": attr_start, "ts": tdate})
        actions = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        # Build transitions
        rows = []
        all_drivers = set(list(current.keys()) + list(previous.keys()))
        dir_counts: Dict[str, int] = {}

        for did in all_drivers:
            cur_data = current.get(did, {})
            prev_data = previous.get(did, {})
            action_data = actions.get(did)

            prev_l1 = prev_data.get("segment_level_1")
            prev_l3 = prev_data.get("segment_level_3")
            cur_l1 = cur_data.get("segment_level_1")
            cur_l3 = cur_data.get("segment_level_3")

            changed = prev_l3 != cur_l3
            direction = _determine_direction(prev_l3, cur_l3, prev_l1, cur_l1)

            had_action = action_data is not None
            had_confirmed = bool(action_data.get("action_confirmed")) if had_action else False

            if changed and had_confirmed and direction in (IMPROVED, RECOVERED):
                move_type = f"{prev_l3}_TO_{cur_l3}"
            elif changed and had_confirmed:
                move_type = f"{prev_l3}_TO_{cur_l3}_WITH_ACTION"
            elif changed:
                move_type = f"{prev_l3}_TO_{cur_l3}"
            elif had_confirmed:
                move_type = "NO_CHANGE_WITH_ACTION"
            elif had_action:
                move_type = "NO_CHANGE_ATTEMPTED"
            else:
                move_type = "NO_CHANGE_NO_ACTION"

            cur_orders = int(cur_data.get("current_week_orders") or 0)
            prev_orders = int(prev_data.get("current_week_orders") or 0)

            rows.append({
                "transition_date": tdate,
                "driver_profile_id": did,
                "prev_snapshot_date": prev_data.get("snapshot_date"),
                "prev_segment_level_1": prev_l1,
                "prev_segment_level_2": prev_data.get("segment_level_2"),
                "prev_segment_level_3": prev_l3,
                "prev_driver_state": prev_data.get("driver_state"),
                "prev_productivity_band": prev_data.get("productivity_band"),
                "prev_current_week_orders": prev_orders if prev_data else None,
                "prev_supply_hours": float(prev_data["current_week_supply_hours"]) if prev_data.get("current_week_supply_hours") else None,
                "current_snapshot_date": cur_snap_date,
                "current_segment_level_1": cur_l1,
                "current_segment_level_2": cur_data.get("segment_level_2"),
                "current_segment_level_3": cur_l3,
                "current_driver_state": cur_data.get("driver_state"),
                "current_productivity_band": cur_data.get("productivity_band"),
                "current_week_orders": cur_orders if cur_data else None,
                "current_supply_hours": float(cur_data["current_week_supply_hours"]) if cur_data.get("current_week_supply_hours") else None,
                "segment_changed_flag": changed,
                "level_1_changed_flag": prev_l1 != cur_l1,
                "level_2_changed_flag": prev_data.get("segment_level_2") != cur_data.get("segment_level_2"),
                "level_3_changed_flag": changed,
                "movement_direction": direction,
                "movement_type": move_type,
                "orders_delta": round(cur_orders - prev_orders, 4) if prev_data and cur_data else None,
                "supply_delta": None,
                "productivity_delta": None,
                "had_action_flag": had_action,
                "had_confirmed_action_flag": had_confirmed,
                "action_id": action_data.get("action_id") if had_action else None,
                "action_type": action_data.get("action_type") if had_action else None,
                "action_owner": action_data.get("action_owner") if had_action else None,
                "campaign_code": action_data.get("campaign_code") if had_action else None,
            })
            dir_counts[direction] = dir_counts.get(direction, 0) + 1

        if rows:
            _upsert_transitions(cur, rows)
            conn.commit()

        return {
            "ok": True,
            "transition_date": transition_date_str,
            "drivers_processed": len(rows),
            "current_snapshot_date": str(cur_snap_date),
            "segment_changed": sum(1 for r in rows if r["segment_changed_flag"]),
            "direction_distribution": dir_counts,
        }


def _upsert_transitions(cur, rows):
    sql = """
        INSERT INTO growth.yango_lima_driver_segment_transition_daily (
            transition_date, driver_profile_id,
            prev_snapshot_date, prev_segment_level_1, prev_segment_level_2, prev_segment_level_3,
            prev_driver_state, prev_productivity_band, prev_current_week_orders, prev_supply_hours,
            current_snapshot_date, current_segment_level_1, current_segment_level_2, current_segment_level_3,
            current_driver_state, current_productivity_band, current_week_orders, current_supply_hours,
            segment_changed_flag, level_1_changed_flag, level_2_changed_flag, level_3_changed_flag,
            movement_direction, movement_type, orders_delta, supply_delta, productivity_delta,
            had_action_flag, had_confirmed_action_flag, action_id, action_type, action_owner, campaign_code
        ) VALUES (
            %(transition_date)s, %(driver_profile_id)s,
            %(prev_snapshot_date)s, %(prev_segment_level_1)s, %(prev_segment_level_2)s, %(prev_segment_level_3)s,
            %(prev_driver_state)s, %(prev_productivity_band)s, %(prev_current_week_orders)s, %(prev_supply_hours)s,
            %(current_snapshot_date)s, %(current_segment_level_1)s, %(current_segment_level_2)s, %(current_segment_level_3)s,
            %(current_driver_state)s, %(current_productivity_band)s, %(current_week_orders)s, %(current_supply_hours)s,
            %(segment_changed_flag)s, %(level_1_changed_flag)s, %(level_2_changed_flag)s, %(level_3_changed_flag)s,
            %(movement_direction)s, %(movement_type)s, %(orders_delta)s, %(supply_delta)s, %(productivity_delta)s,
            %(had_action_flag)s, %(had_confirmed_action_flag)s, %(action_id)s, %(action_type)s, %(action_owner)s, %(campaign_code)s
        )
        ON CONFLICT (transition_date, driver_profile_id) DO UPDATE SET
            segment_changed_flag = EXCLUDED.segment_changed_flag,
            movement_direction = EXCLUDED.movement_direction,
            movement_type = EXCLUDED.movement_type,
            had_action_flag = EXCLUDED.had_action_flag,
            had_confirmed_action_flag = EXCLUDED.had_confirmed_action_flag,
            calculated_at = now()
    """
    for row in rows:
        cur.execute(sql, row)


# ── Query functions ──

def get_transition_summary(date_from: str, date_to: str,
                           segment_level_2: Optional[str] = None,
                           movement_direction: Optional[str] = None,
                           action_owner: Optional[str] = None,
                           campaign_code: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        where = ["transition_date >= %(df)s", "transition_date <= %(dt)s"]
        params = {"df": date_from, "dt": date_to}
        if segment_level_2:
            where.append("current_segment_level_2 = %(sl2)s")
            params["sl2"] = segment_level_2
        if movement_direction:
            where.append("movement_direction = %(md)s")
            params["md"] = movement_direction
        if action_owner:
            where.append("action_owner = %(ao)s")
            params["ao"] = action_owner
        if campaign_code:
            where.append("campaign_code = %(cc)s")
            params["cc"] = campaign_code

        cur.execute(f"""
            SELECT movement_direction, COUNT(*) AS cnt,
                   SUM(CASE WHEN had_action_flag THEN 1 ELSE 0 END) AS with_action,
                   SUM(CASE WHEN had_confirmed_action_flag THEN 1 ELSE 0 END) AS with_confirmed
            FROM {TABLE_TRANSITION}
            WHERE {' AND '.join(where)}
            GROUP BY movement_direction ORDER BY cnt DESC
        """, params)
        return {
            "date_from": date_from, "date_to": date_to,
            "distribution": [dict(r) for r in cur.fetchall()],
        }


def get_movement_matrix(date_from: str, date_to: str, level: str = "3") -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        prev_col = f"prev_segment_level_{level}"
        cur_col = f"current_segment_level_{level}"
        cur.execute(f"""
            SELECT {prev_col} AS from_segment, {cur_col} AS to_segment, COUNT(*) AS cnt
            FROM {TABLE_TRANSITION}
            WHERE transition_date >= %(df)s AND transition_date <= %(dt)s
              AND segment_changed_flag = true
            GROUP BY {prev_col}, {cur_col}
            ORDER BY cnt DESC
        """, {"df": date_from, "dt": date_to})
        return [dict(r) for r in cur.fetchall()]


def get_driver_transition_timeline(driver_profile_id: str, limit: int = 30) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT transition_date, prev_segment_level_3, current_segment_level_3,
                   movement_direction, movement_type,
                   current_week_orders, current_supply_hours,
                   action_type, action_owner, campaign_code, had_action_flag
            FROM {TABLE_TRANSITION}
            WHERE driver_profile_id = %(did)s
            ORDER BY transition_date DESC LIMIT %(limit)s
        """, {"did": driver_profile_id, "limit": min(limit, 100)})
        return [dict(r) for r in cur.fetchall()]


def get_movements_by_agent(date_from: str, date_to: str) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT COALESCE(action_owner, 'unassigned') AS agent,
                   COUNT(*) AS actions_confirmed,
                   SUM(CASE WHEN segment_changed_flag THEN 1 ELSE 0 END) AS drivers_moved,
                   SUM(CASE WHEN movement_direction = 'IMPROVED' THEN 1 ELSE 0 END) AS drivers_improved,
                   SUM(CASE WHEN movement_direction = 'WORSENED' THEN 1 ELSE 0 END) AS drivers_worsened,
                   ROUND(AVG(CASE WHEN segment_changed_flag THEN 1.0 ELSE 0.0 END) * 100, 1) AS movement_rate,
                   ROUND(AVG(CASE WHEN movement_direction = 'IMPROVED' THEN 1.0 ELSE 0.0 END) * 100, 1) AS improvement_rate,
                   SUM(CASE WHEN NOT segment_changed_flag AND had_action_flag THEN 1 ELSE 0 END) AS no_change_with_action
            FROM {TABLE_TRANSITION}
            WHERE transition_date >= %(df)s AND transition_date <= %(dt)s
              AND had_confirmed_action_flag = true
            GROUP BY action_owner ORDER BY actions_confirmed DESC
        """, {"df": date_from, "dt": date_to})
        return [dict(r) for r in cur.fetchall()]


def get_movements_by_campaign(date_from: str, date_to: str) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT campaign_code, COUNT(*) AS cnt,
                   SUM(CASE WHEN segment_changed_flag THEN 1 ELSE 0 END) AS moved,
                   SUM(CASE WHEN movement_direction = 'IMPROVED' THEN 1 ELSE 0 END) AS improved
            FROM {TABLE_TRANSITION}
            WHERE transition_date >= %(df)s AND transition_date <= %(dt)s
              AND campaign_code IS NOT NULL
            GROUP BY campaign_code ORDER BY cnt DESC
        """, {"df": date_from, "dt": date_to})
        return [dict(r) for r in cur.fetchall()]
