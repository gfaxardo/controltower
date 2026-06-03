"""
YEGO Lima Growth — Driver State Snapshot Service (Fase 2D-R).

Builds growth.yango_lima_driver_state_snapshot from canonical sources:
- growth.yango_lima_driver_360_daily (current week)
- growth.yango_lima_driver_history_weekly (historical)

Does NOT use:
- trips_2026 runtime
- orders_raw direct
- proxies
- ops.driver_daily_activity_fact

Canonical states: LIFECYCLE, PERFORMANCE, RETENTION.
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
TABLE_OUT = "growth.yango_lima_driver_state_snapshot"

# ── Lifecycle States ──
LC_PROSPECT = "PROSPECT"
LC_REGISTERED = "REGISTERED"
LC_ACTIVATED = "ACTIVATED"
LC_EARLY_LIFE = "EARLY_LIFE"
LC_ESTABLISHED = "ESTABLISHED"
LC_REACTIVATED = "REACTIVATED"
LC_CHURNED = "CHURNED"
LC_UNKNOWN = "UNKNOWN"

# ── Performance States ──
PS_NO_TRIPS = "NO_TRIPS"
PS_LOW = "LOW"
PS_MEDIUM = "MEDIUM"
PS_TARGET = "TARGET"
PS_HIGH = "HIGH"
PS_UNKNOWN = "UNKNOWN"

# ── Retention States ──
RS_HEALTHY = "HEALTHY"
RS_WATCHLIST = "WATCHLIST"
RS_AT_RISK = "AT_RISK"
RS_CHURN_RISK = "CHURN_RISK"
RS_UNKNOWN = "UNKNOWN"


def build_driver_state_snapshot(snapshot_date_str: str) -> Dict[str, Any]:
    snapshot_date = date.fromisoformat(snapshot_date_str)
    monday = snapshot_date - timedelta(days=snapshot_date.weekday())
    sunday = monday + timedelta(days=6)

    target = int(settings.LIMA_GROWTH_WEEKLY_TRIPS_TARGET)
    low_ratio = float(settings.LIMA_GROWTH_LOW_PERFORMANCE_RATIO)
    medium_ratio = float(settings.LIMA_GROWTH_MEDIUM_PERFORMANCE_RATIO)
    decline_warn_pct = float(settings.LIMA_GROWTH_DECLINE_WARNING_PCT) / 100.0
    decline_risk_pct = float(settings.LIMA_GROWTH_DECLINE_RISK_PCT) / 100.0
    churn_days = int(settings.LIMA_GROWTH_CHURN_DAYS)
    new_driver_window = int(settings.LIMA_GROWTH_NEW_DRIVER_WINDOW_DAYS)
    recovery_days = int(settings.LIMA_GROWTH_RECOVERY_DAYS)

    logger.info("Building driver state snapshot: snapshot=%s, week=%s/%s, target=%s",
                snapshot_date, monday, sunday, target)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ── PRIMARY UNIVERSE: ALL drivers from history_weekly ──
        cur.execute("""
            SELECT hw.driver_profile_id,
                   hw.completed_orders_week,
                   hw.week_start_date,
                   hw.historical_band
            FROM growth.yango_lima_driver_history_weekly hw
            INNER JOIN (
                SELECT driver_profile_id, MAX(week_start_date) AS latest_week
                FROM growth.yango_lima_driver_history_weekly
                WHERE week_start_date <= %(monday)s
                GROUP BY driver_profile_id
            ) latest ON hw.driver_profile_id = latest.driver_profile_id
                     AND hw.week_start_date = latest.latest_week
        """, {"monday": monday})
        history_universe = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}
        logger.info("  History universe: %s drivers from history_weekly", len(history_universe))

        # ── SECONDARY: 360_daily data for supply enrichment ──
        cur.execute("""
            SELECT
                driver_profile_id,
                SUM(completed_orders) AS completed_orders_360,
                SUM(supply_hours) AS supply_hours_week,
                MAX(date) FILTER (WHERE supply_hours > 0) AS last_supply_at,
                MAX(date) AS last_360_date
            FROM growth.yango_lima_driver_360_daily
            WHERE date >= %(monday)s AND date <= %(sunday)s
            GROUP BY driver_profile_id
        """, {"monday": monday, "sunday": sunday})
        supply_data = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}
        logger.info("  Supply data: %s drivers from 360_daily", len(supply_data))

        # Day-level supply for snapshot_date
        cur.execute("""
            SELECT
                driver_profile_id,
                SUM(completed_orders) AS completed_orders_day,
                SUM(supply_hours) AS supply_hours_day
            FROM growth.yango_lima_driver_360_daily
            WHERE date = %(snap_date)s
            GROUP BY driver_profile_id
        """, {"snap_date": snapshot_date})
        day_data = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        # ── FULL UNIVERSE: history_weekly UNION 360_daily ──
        all_driver_ids = list(set(history_universe.keys()) | set(supply_data.keys()))
        logger.info("  Total universe: %s drivers (history + supply)", len(all_driver_ids))

        if not all_driver_ids:
            return {"ok": False, "error": "No drivers found in history_weekly or 360_daily"}

        # ── HISTORICAL METRICS: compute avg_orders_4w, best_week_12w, etc. ──
        cur.execute("""
            SELECT driver_profile_id,
                   COUNT(*) AS weeks_with_data,
                   ROUND(AVG(completed_orders_week), 4) AS avg_orders_4w,
                   ROUND(AVG(completed_orders_week), 4) AS avg_orders_12w,
                   MAX(completed_orders_week) AS best_week_12w,
                   SUM(completed_orders_week) AS total_orders_hist,
                   MIN(week_start_date) AS first_week,
                   MAX(week_start_date) AS last_week,
                   MAX(completed_orders_week) AS max_week_orders
            FROM growth.yango_lima_driver_history_weekly
            WHERE driver_profile_id = ANY(%(drivers)s)
              AND week_start_date <= %(monday)s
            GROUP BY driver_profile_id
        """, {"drivers": all_driver_ids, "monday": monday})
        hist_metrics = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}

        # ── BUILD STATE SNAPSHOTS ──
        rows = []
        counts_lc: Dict[str, int] = {
            LC_PROSPECT: 0, LC_REGISTERED: 0, LC_ACTIVATED: 0,
            LC_EARLY_LIFE: 0, LC_ESTABLISHED: 0, LC_REACTIVATED: 0,
            LC_CHURNED: 0, LC_UNKNOWN: 0,
        }
        counts_ps: Dict[str, int] = {
            PS_NO_TRIPS: 0, PS_LOW: 0, PS_MEDIUM: 0, PS_TARGET: 0,
            PS_HIGH: 0, PS_UNKNOWN: 0,
        }
        counts_rs: Dict[str, int] = {
            RS_HEALTHY: 0, RS_WATCHLIST: 0, RS_AT_RISK: 0,
            RS_CHURN_RISK: 0, RS_UNKNOWN: 0,
        }

        for driver_id in all_driver_ids:
            h = history_universe.get(driver_id, {})
            s = supply_data.get(driver_id, {})
            hm = hist_metrics.get(driver_id, {})
            d = day_data.get(driver_id, {})

            # Orders: prefer history_weekly for completed_orders
            orders_week = int(h.get("completed_orders_week", 0) or 0)
            supply_week = float(s.get("supply_hours_week", 0) or 0)
            if supply_week == 0 and not orders_week:
                supply_week = 0.0

            orders_day = int(d.get("completed_orders_day", 0) or 0)
            supply_day = float(d.get("supply_hours_day", 0) or 0)

            avg_4w = float(hm["avg_orders_4w"]) if hm.get("avg_orders_4w") is not None else None
            avg_12w = float(hm["avg_orders_12w"]) if hm.get("avg_orders_12w") is not None else None
            best_12w = int(hm["best_week_12w"]) if hm.get("best_week_12w") is not None else None
            hband = h.get("historical_band")
            first_w = hm.get("first_week")
            weeks_with_data = int(hm.get("weeks_with_data", 0) or 0)

            last_trip = _infer_last_order_date(snapshot_date, h, s)
            last_supply = s.get("last_supply_at")
            days_since_last_trip = (snapshot_date - last_trip).days if last_trip else 999
            days_since_first = (snapshot_date - first_w).days if first_w else 999

            tph_week = round(orders_week / supply_week, 4) if supply_week > 0 and orders_week > 0 else None

            distance = max(0, target - orders_week)
            reached_target = orders_week >= target

            # ── LIFECYCLE STATE ──
            if orders_week == 0 and not supply_week and not weeks_with_data:
                lifecycle = LC_UNKNOWN
            elif orders_week > 0:
                if first_w and days_since_first <= new_driver_window:
                    lifecycle = LC_EARLY_LIFE
                elif first_w and days_since_first <= 90:
                    lifecycle = LC_ACTIVATED
                elif avg_4w and avg_4w > 0:
                    lifecycle = LC_ESTABLISHED
                elif last_trip and days_since_last_trip > recovery_days:
                    lifecycle = LC_REACTIVATED
                else:
                    lifecycle = LC_ACTIVATED
            elif supply_week > 0 and orders_week == 0:
                if first_w and weeks_with_data > 0:
                    lifecycle = LC_ESTABLISHED
                else:
                    lifecycle = LC_ACTIVATED
            elif weeks_with_data == 0 and not supply_week:
                lifecycle = LC_CHURNED
            else:
                lifecycle = LC_UNKNOWN

            # ── PERFORMANCE STATE ──
            if not orders_week:
                if avg_4w and avg_4w > 0:
                    perf = PS_NO_TRIPS
                else:
                    perf = PS_UNKNOWN if not supply_week else PS_NO_TRIPS
            elif orders_week <= target * low_ratio:
                perf = PS_LOW
            elif orders_week <= target * medium_ratio:
                perf = PS_MEDIUM
            elif orders_week <= target:
                perf = PS_TARGET
            else:
                perf = PS_HIGH

            # ── RETENTION STATE ──
            new_driver_flag = lifecycle in (LC_EARLY_LIFE, LC_ACTIVATED) and days_since_first <= new_driver_window
            reactivated_flag = lifecycle == LC_REACTIVATED
            recoverable = (avg_12w is not None and avg_12w >= target and orders_week < target)
            declining = False
            churn_risk_flag = False

            if avg_4w and avg_4w > 0 and orders_week < avg_4w:
                pct_drop = (avg_4w - orders_week) / avg_4w
                if pct_drop >= decline_risk_pct:
                    churn_risk_flag = True
                elif pct_drop >= decline_warn_pct:
                    declining = True

            if lifecycle == LC_UNKNOWN:
                retention = RS_UNKNOWN
            elif lifecycle == LC_CHURNED:
                retention = RS_CHURN_RISK
            elif churn_risk_flag:
                retention = RS_CHURN_RISK
            elif declining:
                retention = RS_AT_RISK
            elif (avg_4w and avg_4w > 0 and
                  orders_week < avg_4w * (1 - decline_warn_pct * 0.5)):
                retention = RS_WATCHLIST
            elif orders_week > 0 or weeks_with_data > 0:
                retention = RS_HEALTHY
            else:
                retention = RS_UNKNOWN

            rows.append({
                "snapshot_date": snapshot_date,
                "driver_profile_id": driver_id,
                "lifecycle_state": lifecycle,
                "performance_state": perf,
                "retention_state": retention,
                "completed_orders_day": orders_day,
                "completed_orders_week": orders_week,
                "supply_hours_day": round(supply_day, 4),
                "supply_hours_week": round(supply_week, 4),
                "trips_per_supply_hour_week": tph_week,
                "avg_orders_4w": round(avg_4w, 4) if avg_4w else None,
                "avg_orders_12w": round(avg_12w, 4) if avg_12w else None,
                "best_week_12w": best_12w,
                "historical_band": hband,
                "weekly_trips_target": target,
                "distance_to_weekly_target": distance,
                "new_driver_flag": new_driver_flag,
                "reactivated_flag": reactivated_flag,
                "recoverable_flag": recoverable,
                "declining_flag": declining,
                "churn_risk_flag": churn_risk_flag,
                "reached_target_flag": reached_target,
                "first_seen_at": first_w.isoformat() if first_w else None,
                "first_trip_at": None,
                "last_trip_at": last_trip.isoformat() if last_trip else None,
                "last_supply_at": last_supply.isoformat() if last_supply else None,
            })

            counts_lc[lifecycle] += 1
            counts_ps[perf] += 1
            counts_rs[retention] += 1

        if rows:
            _upsert_snapshot(cur, rows)
            conn.commit()

        return {
            "ok": True,
            "snapshot_date": snapshot_date_str,
            "drivers_total": len(rows),
            "lifecycle_distribution": counts_lc,
            "performance_distribution": counts_ps,
            "retention_distribution": counts_rs,
        }


def _infer_last_order_date(snapshot_date: date, history: dict, supply: dict):
    last_trip = None
    if history and history.get("week_start_date"):
        hw = history["week_start_date"]
        if isinstance(hw, date):
            last_trip = hw + timedelta(days=6)
    if supply and supply.get("last_360_date"):
        s_date = supply["last_360_date"]
        if isinstance(s_date, date):
            if not last_trip or s_date > last_trip:
                last_trip = s_date
    return last_trip


def _upsert_snapshot(cur, rows: list) -> None:
    from psycopg2.extras import execute_values

    if not rows:
        return

    sql = """
        INSERT INTO growth.yango_lima_driver_state_snapshot (
            snapshot_date, driver_profile_id,
            lifecycle_state, performance_state, retention_state,
            completed_orders_day, completed_orders_week,
            supply_hours_day, supply_hours_week,
            trips_per_supply_hour_week,
            avg_orders_4w, avg_orders_12w, best_week_12w, historical_band,
            weekly_trips_target, distance_to_weekly_target,
            new_driver_flag, reactivated_flag, recoverable_flag,
            declining_flag, churn_risk_flag, reached_target_flag,
            first_seen_at, first_trip_at, last_trip_at, last_supply_at,
            last_calculated_at, source
        ) VALUES %s
        ON CONFLICT (snapshot_date, driver_profile_id) DO UPDATE SET
            lifecycle_state = EXCLUDED.lifecycle_state,
            performance_state = EXCLUDED.performance_state,
            retention_state = EXCLUDED.retention_state,
            completed_orders_day = EXCLUDED.completed_orders_day,
            completed_orders_week = EXCLUDED.completed_orders_week,
            supply_hours_day = EXCLUDED.supply_hours_day,
            supply_hours_week = EXCLUDED.supply_hours_week,
            trips_per_supply_hour_week = EXCLUDED.trips_per_supply_hour_week,
            avg_orders_4w = EXCLUDED.avg_orders_4w,
            avg_orders_12w = EXCLUDED.avg_orders_12w,
            best_week_12w = EXCLUDED.best_week_12w,
            historical_band = EXCLUDED.historical_band,
            weekly_trips_target = EXCLUDED.weekly_trips_target,
            distance_to_weekly_target = EXCLUDED.distance_to_weekly_target,
            new_driver_flag = EXCLUDED.new_driver_flag,
            reactivated_flag = EXCLUDED.reactivated_flag,
            recoverable_flag = EXCLUDED.recoverable_flag,
            declining_flag = EXCLUDED.declining_flag,
            churn_risk_flag = EXCLUDED.churn_risk_flag,
            reached_target_flag = EXCLUDED.reached_target_flag,
            first_seen_at = EXCLUDED.first_seen_at,
            first_trip_at = EXCLUDED.first_trip_at,
            last_trip_at = EXCLUDED.last_trip_at,
            last_supply_at = EXCLUDED.last_supply_at,
            last_calculated_at = now(),
            source = EXCLUDED.source
    """

    template = """(
        %(snapshot_date)s, %(driver_profile_id)s,
        %(lifecycle_state)s, %(performance_state)s, %(retention_state)s,
        %(completed_orders_day)s, %(completed_orders_week)s,
        %(supply_hours_day)s, %(supply_hours_week)s,
        %(trips_per_supply_hour_week)s,
        %(avg_orders_4w)s, %(avg_orders_12w)s, %(best_week_12w)s, %(historical_band)s,
        %(weekly_trips_target)s, %(distance_to_weekly_target)s,
        %(new_driver_flag)s, %(reactivated_flag)s, %(recoverable_flag)s,
        %(declining_flag)s, %(churn_risk_flag)s, %(reached_target_flag)s,
        %(first_seen_at)s::timestamptz, %(first_trip_at)s::timestamptz,
        %(last_trip_at)s::timestamptz, %(last_supply_at)s::timestamptz,
        now(), 'driver_state_snapshot'
    )"""

    execute_values(cur, sql, rows, template=template, page_size=500)


# ── QUERY ENDPOINTS ──

def _latest_snapshot_date(cur) -> Optional[str]:
    cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_OUT}")
    r = cur.fetchone()
    return str(r["max"]) if r and r["max"] else None


def get_state_summary(snapshot_date_str: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if snapshot_date_str:
            sd = snapshot_date_str
        else:
            sd = _latest_snapshot_date(cur)
            if not sd:
                return {"error": "No data. Run POST /state/build-driver-states first."}

        cur.execute(f"""
            SELECT lifecycle_state, COUNT(*) AS cnt,
                   ROUND(AVG(completed_orders_week), 1) AS avg_orders,
                   ROUND(AVG(supply_hours_week), 2) AS avg_supply
            FROM {TABLE_OUT}
            WHERE snapshot_date = %(sd)s
            GROUP BY lifecycle_state ORDER BY cnt DESC
        """, {"sd": sd})
        lifecycle = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT performance_state, COUNT(*) AS cnt
            FROM {TABLE_OUT} WHERE snapshot_date = %(sd)s
            GROUP BY performance_state ORDER BY cnt DESC
        """, {"sd": sd})
        performance = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT retention_state, COUNT(*) AS cnt
            FROM {TABLE_OUT} WHERE snapshot_date = %(sd)s
            GROUP BY retention_state ORDER BY cnt DESC
        """, {"sd": sd})
        retention = [dict(r) for r in cur.fetchall()]

        return {
            "snapshot_date": str(sd),
            "lifecycle_distribution": lifecycle,
            "performance_distribution": performance,
            "retention_distribution": retention,
        }


def get_drivers_by_state(
    snapshot_date_str: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    performance_state: Optional[str] = None,
    retention_state: Optional[str] = None,
    limit: int = 100,
) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if snapshot_date_str:
            sd = snapshot_date_str
        else:
            sd = _latest_snapshot_date(cur)
            if not sd:
                return []

        where = ["snapshot_date = %(sd)s"]
        params = {"sd": sd, "limit": min(limit, 500)}

        if lifecycle_state:
            placeholders = ", ".join(f"%(lc_{i})s" for i in range(len(lifecycle_state)))
            where.append(f"lifecycle_state IN ({placeholders})")
            for i, v in enumerate(lifecycle_state):
                params[f"lc_{i}"] = v
        elif lifecycle_state:
            where.append("lifecycle_state = %(lc)s")
            params["lc"] = lifecycle_state

        if performance_state:
            where.append("performance_state = %(ps)s")
            params["ps"] = performance_state

        if retention_state:
            where.append("retention_state = %(rs)s")
            params["rs"] = retention_state

        cur.execute(f"""
            SELECT driver_profile_id, lifecycle_state, performance_state, retention_state,
                   completed_orders_week, supply_hours_week,
                   distance_to_weekly_target, trips_per_supply_hour_week,
                   recoverable_flag, churn_risk_flag, reached_target_flag
            FROM {TABLE_OUT}
            WHERE {' AND '.join(where)}
            ORDER BY distance_to_weekly_target ASC NULLS LAST
            LIMIT %(limit)s
        """, params)
        return [dict(r) for r in cur.fetchall()]


def get_driver_state(driver_profile_id: str, snapshot_date_str: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if snapshot_date_str:
            sd = snapshot_date_str
        else:
            sd = _latest_snapshot_date(cur)
            if not sd:
                return None

        cur.execute(f"""
            SELECT * FROM {TABLE_OUT}
            WHERE snapshot_date = %(sd)s AND driver_profile_id = %(did)s
        """, {"sd": sd, "did": driver_profile_id})
        r = cur.fetchone()
        return dict(r) if r else None
