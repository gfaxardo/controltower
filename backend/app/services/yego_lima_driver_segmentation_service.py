"""
YEGO Lima Fleet Growth Tower — Unified Driver Segmentation Service (Fase 2B-R2).

3-Level segmentation:
  L1 = LIFECYCLE: NEW, REACTIVATED, ACTIVE, DECLINING, CHURN_RISK, CHURNED, RECOVERED, UNKNOWN
  L2 = LOYALTY PROGRAM: LOYALTY_14_90, LOYALTY_ACTIVE_GROWTH, LOYALTY_CHURN_PREVENTION, NONE
  L3 = ACTIONABLE COHORT: NEAR_TARGET, RECOVERABLE, HIGH_SUPPLY_LOW_ORDERS, DECLINING_4W, etc.

Canonical sources only:
- growth.yango_lima_driver_360_daily (current week)
- growth.yango_lima_driver_history_weekly (historical)
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

TABLE_360 = "growth.yango_lima_driver_360_daily"
TABLE_HISTORY = "growth.yango_lima_driver_history_weekly"
TABLE_OUT = "growth.yango_lima_driver_segment_snapshot"

# ── L1: Lifecycle ──
L1_NEW = "NEW"
L1_REACTIVATED = "REACTIVATED"
L1_ACTIVE = "ACTIVE"
L1_DECLINING = "DECLINING"
L1_CHURN_RISK = "CHURN_RISK"
L1_CHURNED = "CHURNED"
L1_RECOVERED = "RECOVERED"
L1_UNKNOWN = "UNKNOWN"

# ── L2: Loyalty Program ──
L2_14_90 = "LOYALTY_14_90"
L2_ACTIVE_GROWTH = "LOYALTY_ACTIVE_GROWTH"
L2_CHURN_PREVENTION = "LOYALTY_CHURN_PREVENTION"
L2_NONE = "NONE"

# ── L3: Actionable Cohorts ──
L3_NEAR_TARGET = "NEAR_TARGET"
L3_HIGH_SUPPLY_LOW_ORDERS = "HIGH_SUPPLY_LOW_ORDERS"
L3_RECOVERABLE = "RECOVERABLE"
L3_DECLINING_4W = "DECLINING_4W"
L3_DECLINING_12W = "DECLINING_12W"
L3_CHURN_RISK = "CHURN_RISK"
L3_NEW_0_14 = "NEW_0_14"
L3_REACTIVATED_0_14 = "REACTIVATED_0_14"
L3_RECOVERED = "RECOVERED"
L3_STABLE = "STABLE"
L3_CHURNED = "CHURNED"

L1_TO_L2 = {
    L1_NEW: L2_14_90,
    L1_REACTIVATED: L2_14_90,
    L1_ACTIVE: L2_ACTIVE_GROWTH,
    L1_DECLINING: L2_CHURN_PREVENTION,
    L1_CHURN_RISK: L2_CHURN_PREVENTION,
    L1_RECOVERED: L2_ACTIVE_GROWTH,
    L1_CHURNED: L2_CHURN_PREVENTION,
    L1_UNKNOWN: L2_NONE,
}


def _mask_driver_id(driver_id: str) -> str:
    if len(driver_id) <= 8:
        return driver_id[:4] + "****"
    return driver_id[:4] + "****" + driver_id[-4:]


def build_driver_segments(snapshot_date_str: str) -> Dict[str, Any]:
    snapshot_date = date.fromisoformat(snapshot_date_str)
    monday = snapshot_date - timedelta(days=snapshot_date.weekday())
    sunday = monday + timedelta(days=6)

    target = int(settings.LIMA_GROWTH_WEEKLY_TRIPS_TARGET)
    warn_pct = float(settings.LIMA_GROWTH_DECLINE_WARNING_PCT) / 100.0
    risk_pct = float(settings.LIMA_GROWTH_DECLINE_RISK_PCT) / 100.0
    churn_days = int(settings.LIMA_GROWTH_CHURN_DAYS)
    recovery_days = int(settings.LIMA_GROWTH_RECOVERY_DAYS)

    logger.info("Building driver segments: snapshot=%s, week=%s/%s, target=%s",
                snapshot_date, monday, sunday, target)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1. Current week from 360_daily
        cur.execute("""
            SELECT driver_profile_id,
                   SUM(completed_orders) AS current_week_orders,
                   SUM(supply_hours) AS current_week_supply_hours,
                   MAX(driver_state) AS driver_state,
                   MAX(productivity_band) AS productivity_band
            FROM growth.yango_lima_driver_360_daily
            WHERE date >= %(monday)s AND date <= %(sunday)s
              AND active_flag = true
            GROUP BY driver_profile_id
        """, {"monday": monday, "sunday": sunday})
        week_data = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}
        logger.info("  Week data: %s active drivers from 360_daily", len(week_data))

        if not week_data:
            return {"ok": False, "error": "No active drivers in 360_daily for this week"}

        driver_ids = list(week_data.keys())

        # 2. Latest historical from history_weekly
        cur.execute("""
            SELECT DISTINCT ON (driver_profile_id)
                driver_profile_id,
                avg_orders_4w, avg_orders_12w, best_week_12w, historical_band,
                week_start_date AS last_week_date,
                completed_orders_week AS last_week_orders
            FROM growth.yango_lima_driver_history_weekly
            WHERE driver_profile_id = ANY(%(drivers)s)
              AND week_start_date <= %(monday)s
            ORDER BY driver_profile_id, week_start_date DESC
        """, {"drivers": driver_ids, "monday": monday})
        history_data = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}
        logger.info("  History data: %s drivers", len(history_data))

        # 3. First appearance for NEW classification
        cur.execute("""
            SELECT driver_profile_id, MIN(week_start_date) AS first_week
            FROM growth.yango_lima_driver_history_weekly
            WHERE driver_profile_id = ANY(%(drivers)s)
            GROUP BY driver_profile_id
        """, {"drivers": driver_ids})
        first_weeks = {r["driver_profile_id"]: r["first_week"] for r in cur.fetchall()}

        # 4. Last activity date for RECOVERED classification
        cur.execute("""
            SELECT driver_profile_id, MAX(date) AS last_active_date
            FROM growth.yango_lima_driver_360_daily
            WHERE driver_profile_id = ANY(%(drivers)s)
              AND completed_orders > 0
            GROUP BY driver_profile_id
        """, {"drivers": driver_ids})
        last_orders = {r["driver_profile_id"]: r["last_active_date"] for r in cur.fetchall()}

        # 5. Build segments
        rows = []
        counts: Dict[str, int] = {k: 0 for k in [L1_NEW, L1_REACTIVATED, L1_ACTIVE, L1_DECLINING,
                                                   L1_CHURN_RISK, L1_CHURNED, L1_RECOVERED, L1_UNKNOWN]}
        l3_counts: Dict[str, int] = {}

        avg_orders_all = sum(float(wd["current_week_orders"] or 0) for wd in week_data.values()) / len(week_data)
        avg_supply_all = sum(float(wd["current_week_supply_hours"] or 0) for wd in week_data.values()) / len(week_data)

        for driver_id, wd in week_data.items():
            orders = int(wd["current_week_orders"] or 0)
            supply = float(wd["current_week_supply_hours"] or 0)
            hist = history_data.get(driver_id, {})
            avg_4w = float(hist["avg_orders_4w"]) if hist.get("avg_orders_4w") is not None else None
            avg_12w = float(hist["avg_orders_12w"]) if hist.get("avg_orders_12w") is not None else None
            best_12w = int(hist["best_week_12w"]) if hist.get("best_week_12w") is not None else None
            hband = hist.get("historical_band")
            first_w = first_weeks.get(driver_id)
            last_order = last_orders.get(driver_id)
            days_since_last = (snapshot_date - last_order).days if last_order else 999

            # L1 classification
            days_since_first = (snapshot_date - first_w).days if first_w else 999

            if days_since_last > churn_days:
                l1 = L1_CHURNED
            elif days_since_first <= 14:
                l1 = L1_NEW
            elif days_since_last > recovery_days and orders > 0:
                l1 = L1_REACTIVATED
            elif avg_4w and avg_4w > 0:
                pct_drop = (avg_4w - orders) / avg_4w * 100
                if pct_drop >= risk_pct * 100:
                    l1 = L1_CHURN_RISK
                elif pct_drop >= warn_pct * 100:
                    l1 = L1_DECLINING
                elif orders >= avg_4w:
                    l1 = L1_ACTIVE
                else:
                    l1 = L1_ACTIVE
            elif orders > 0:
                l1 = L1_ACTIVE
            else:
                l1 = L1_UNKNOWN

            # L2 mapping
            l2 = L1_TO_L2.get(l1, L2_NONE)

            # L3 classification
            distance = max(0, target - orders)
            recoverable = (avg_12w is not None and avg_12w >= target and orders < target)
            is_hslo = (supply >= avg_supply_all and orders < avg_orders_all)

            if l1 == L1_NEW:
                l3 = L3_NEW_0_14
            elif l1 == L1_REACTIVATED:
                l3 = L3_REACTIVATED_0_14
            elif l1 == L1_CHURNED:
                l3 = L3_CHURNED
            elif l1 == L1_RECOVERED:
                l3 = L3_RECOVERED
            elif recoverable:
                l3 = L3_RECOVERABLE
            elif l1 == L1_CHURN_RISK:
                l3 = L3_CHURN_RISK
            elif l1 == L1_DECLINING:
                l3 = L3_DECLINING_4W if (avg_4w and avg_4w > orders * 1.3) else L3_DECLINING_12W
            elif distance <= max(10, int(target * 0.2)):
                l3 = L3_NEAR_TARGET
            elif is_hslo:
                l3 = L3_HIGH_SUPPLY_LOW_ORDERS
            else:
                l3 = L3_STABLE

            # Growth priority
            priority_map = {
                L3_RECOVERABLE: 1, L3_NEAR_TARGET: 2, L3_HIGH_SUPPLY_LOW_ORDERS: 3,
                L3_NEW_0_14: 4, L3_REACTIVATED_0_14: 5,
                L3_DECLINING_4W: 6, L3_CHURN_RISK: 7,
                L3_DECLINING_12W: 8, L3_RECOVERED: 9, L3_STABLE: 10, L3_CHURNED: 11,
            }
            priority = priority_map.get(l3, 99)

            rows.append({
                "snapshot_date": snapshot_date,
                "driver_profile_id": driver_id,
                "segment_level_1": l1,
                "segment_level_2": l2,
                "segment_level_3": l3,
                "current_week_orders": orders,
                "current_week_supply_hours": round(supply, 4),
                "distance_to_target": distance,
                "avg_orders_4w": round(avg_4w, 4) if avg_4w else None,
                "avg_orders_12w": round(avg_12w, 4) if avg_12w else None,
                "best_week_12w": best_12w,
                "driver_state": wd.get("driver_state"),
                "productivity_band": wd.get("productivity_band"),
                "historical_band": hband,
                "recoverable_flag": recoverable,
                "growth_priority": priority,
            })

            counts[l1] += 1
            l3_counts[l3] = l3_counts.get(l3, 0) + 1

        if rows:
            _upsert_snapshot(cur, rows)
            conn.commit()

        return {
            "ok": True,
            "snapshot_date": snapshot_date_str,
            "drivers_total": len(rows),
            "l1_distribution": counts,
            "l3_distribution": l3_counts,
            "avg_orders_week": round(avg_orders_all, 2),
            "avg_supply_hours_week": round(avg_supply_all, 2),
        }


def _upsert_snapshot(cur, rows: list) -> None:
    sql = """
        INSERT INTO growth.yango_lima_driver_segment_snapshot (
            snapshot_date, driver_profile_id,
            segment_level_1, segment_level_2, segment_level_3,
            current_week_orders, current_week_supply_hours, distance_to_target,
            avg_orders_4w, avg_orders_12w, best_week_12w,
            driver_state, productivity_band, historical_band,
            recoverable_flag, growth_priority,
            last_calculated_at, source
        ) VALUES (
            %(snapshot_date)s, %(driver_profile_id)s,
            %(segment_level_1)s, %(segment_level_2)s, %(segment_level_3)s,
            %(current_week_orders)s, %(current_week_supply_hours)s, %(distance_to_target)s,
            %(avg_orders_4w)s, %(avg_orders_12w)s, %(best_week_12w)s,
            %(driver_state)s, %(productivity_band)s, %(historical_band)s,
            %(recoverable_flag)s, %(growth_priority)s,
            now(), 'driver_segment_snapshot'
        )
        ON CONFLICT (snapshot_date, driver_profile_id) DO UPDATE SET
            segment_level_1 = EXCLUDED.segment_level_1,
            segment_level_2 = EXCLUDED.segment_level_2,
            segment_level_3 = EXCLUDED.segment_level_3,
            current_week_orders = EXCLUDED.current_week_orders,
            current_week_supply_hours = EXCLUDED.current_week_supply_hours,
            distance_to_target = EXCLUDED.distance_to_target,
            avg_orders_4w = EXCLUDED.avg_orders_4w,
            avg_orders_12w = EXCLUDED.avg_orders_12w,
            best_week_12w = EXCLUDED.best_week_12w,
            driver_state = EXCLUDED.driver_state,
            productivity_band = EXCLUDED.productivity_band,
            historical_band = EXCLUDED.historical_band,
            recoverable_flag = EXCLUDED.recoverable_flag,
            growth_priority = EXCLUDED.growth_priority,
            last_calculated_at = now(),
            source = EXCLUDED.source
    """
    for row in rows:
        cur.execute(sql, row)


# ── QUERY ENDPOINTS ──

def _latest_snapshot(cur) -> Optional[str]:
    cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_OUT}")
    r = cur.fetchone()
    return r["max"] if r else None


def get_segments_summary(snapshot_date_str: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if snapshot_date_str:
            sd_filter = "WHERE snapshot_date = %(sd)s"
            params = {"sd": snapshot_date_str}
        else:
            sd = _latest_snapshot(cur)
            if not sd:
                return {"error": "No data. Run POST /build-driver-segments first."}
            sd_filter = "WHERE snapshot_date = %(sd)s"
            params = {"sd": sd}

        cur.execute(f"""
            SELECT segment_level_1, COUNT(*) AS cnt,
                   ROUND(AVG(current_week_orders), 1) AS avg_orders,
                   ROUND(AVG(current_week_supply_hours), 2) AS avg_supply
            FROM {TABLE_OUT} {sd_filter}
            GROUP BY segment_level_1 ORDER BY cnt DESC
        """, params)
        l1 = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT segment_level_2, COUNT(*) AS cnt
            FROM {TABLE_OUT} {sd_filter}
            GROUP BY segment_level_2 ORDER BY cnt DESC
        """, params)
        l2 = [dict(r) for r in cur.fetchall()]

        return {"snapshot_date": params.get("sd"), "l1_distribution": l1, "l2_distribution": l2}


def get_segments_distribution(snapshot_date_str: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if snapshot_date_str:
            sd_filter = "WHERE snapshot_date = %(sd)s"
            params = {"sd": snapshot_date_str}
        else:
            sd = _latest_snapshot(cur)
            if not sd:
                return {"error": "No data."}
            sd_filter = "WHERE snapshot_date = %(sd)s"
            params = {"sd": sd}

        cur.execute(f"""
            SELECT segment_level_1, segment_level_2, segment_level_3, COUNT(*) AS cnt
            FROM {TABLE_OUT} {sd_filter}
            GROUP BY segment_level_1, segment_level_2, segment_level_3
            ORDER BY COUNT(*) DESC
        """, params)
        return {"snapshot_date": params.get("sd"), "distribution": [dict(r) for r in cur.fetchall()]}


def _query_segment(snapshot_date_str, l1_filter, l3_filter, limit, order_by):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if snapshot_date_str:
            sd_filter = "snapshot_date = %(sd)s"
            params = {"sd": snapshot_date_str, "limit": min(limit or 100, 500)}
        else:
            sd = _latest_snapshot(cur)
            if not sd:
                return []
            sd_filter = "snapshot_date = %(sd)s"
            params = {"sd": sd, "limit": min(limit or 100, 500)}

        where = [sd_filter]
        if l1_filter:
            placeholders = ", ".join(f"%(l1_{i})s" for i in range(len(l1_filter)))
            where.append(f"segment_level_1 IN ({placeholders})")
            for i, v in enumerate(l1_filter):
                params[f"l1_{i}"] = v

        if l3_filter:
            placeholders = ", ".join(f"%(l3_{i})s" for i in range(len(l3_filter)))
            where.append(f"segment_level_3 IN ({placeholders})")
            for i, v in enumerate(l3_filter):
                params[f"l3_{i}"] = v

        cur.execute(f"""
            SELECT driver_profile_id, segment_level_1, segment_level_2, segment_level_3,
                   current_week_orders, current_week_supply_hours, distance_to_target,
                   avg_orders_4w, avg_orders_12w, driver_state, productivity_band,
                   historical_band, recoverable_flag, growth_priority
            FROM {TABLE_OUT}
            WHERE {' AND '.join(where)}
            ORDER BY {order_by}
            LIMIT %(limit)s
        """, params)

        result = []
        for row in cur.fetchall():
            item = dict(row)
            item["driver_profile_id_masked"] = _mask_driver_id(item.pop("driver_profile_id", ""))
            for k in ("current_week_supply_hours", "avg_orders_4w", "avg_orders_12w"):
                if item.get(k) is not None:
                    item[k] = round(float(item[k]), 2)
            result.append(item)
        return result


def get_top_opportunities(snapshot_date_str=None, limit=100):
    return _query_segment(snapshot_date_str, None, None, limit, "growth_priority ASC NULLS LAST")


def get_recoverable_list(snapshot_date_str=None, limit=100):
    return _query_segment(snapshot_date_str, None, ["RECOVERABLE"], limit, "avg_orders_12w DESC NULLS LAST")


def get_churn_risk(snapshot_date_str=None, limit=100):
    return _query_segment(snapshot_date_str, None, ["CHURN_RISK", "DECLINING_4W", "DECLINING_12W"], limit,
                          "current_week_orders ASC, avg_orders_4w DESC NULLS LAST")


def get_14_90(snapshot_date_str=None, limit=100):
    return _query_segment(snapshot_date_str, ["NEW", "REACTIVATED"], None, limit,
                          "snapshot_date DESC, driver_profile_id")
