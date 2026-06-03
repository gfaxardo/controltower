"""
YEGO Lima Fleet Growth Tower — Loyalty Sub-50 Engine (Fase 2B-R1 Canonical).

CANONICAL SOURCES:
- growth.yango_lima_driver_360_daily   (current week: orders, supply, tph, state, productivity)
- growth.yango_lima_driver_history_weekly (historical: 4w/8w/12w, best_week, band)

DEPRECATED (no longer used):
- ops.driver_daily_activity_fact → replaced by growth.yango_lima_driver_360_daily
- growth.yango_lima_orders_raw proxy supply → replaced by 360_daily.supply_hours
- trips_2026 runtime → replaced by growth history tables

Dynamic segments (distance_to_target):
NEAR_TARGET (1-10), MID_GAP (11-20), LARGE_GAP (21-40), VERY_LARGE_GAP (>40)

Recoverable: completed < target AND avg_orders_12w >= target
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
TABLE_OUT = "growth.yango_lima_loyalty_sub50_weekly"
SOURCE_VERSION = "2B-R1-canonical"

# ── Dynamic segments (distance_to_target) ──
SEGMENT_NEAR = "NEAR_TARGET"
SEGMENT_MID = "MID_GAP"
SEGMENT_LARGE = "LARGE_GAP"
SEGMENT_VERY_LARGE = "VERY_LARGE_GAP"

# Legacy display labels for backward compatibility
LEGACY_LABELS = {
    SEGMENT_NEAR: "SUB50_40_49",
    SEGMENT_MID: "SUB50_30_39",
    SEGMENT_LARGE: "SUB50_20_29",
    SEGMENT_VERY_LARGE: "SUB50_00_09",
}


def _classify_segment_dynamic(distance: int, target: int) -> str:
    if distance <= max(10, int(target * 0.2)):
        return SEGMENT_NEAR
    if distance <= max(20, int(target * 0.4)):
        return SEGMENT_MID
    if distance <= max(40, int(target * 0.8)):
        return SEGMENT_LARGE
    return SEGMENT_VERY_LARGE


def _classify_growth_priority(
    segment: str,
    recoverable: bool,
    is_high_supply_low_orders: bool,
    distance: int,
) -> int:
    if recoverable:
        return 1
    if segment == SEGMENT_NEAR:
        return 2
    if is_high_supply_low_orders:
        return 3
    if segment == SEGMENT_MID:
        return 4
    if segment == SEGMENT_LARGE:
        return 5
    return 6


def _mask_driver_id(driver_id: str) -> str:
    if len(driver_id) <= 8:
        return driver_id[:4] + "****"
    return driver_id[:4] + "****" + driver_id[-4:]


# =====================================================================
# DEPRECATED FUNCTIONS — kept for reference, not used by new endpoints
# =====================================================================

def _get_lima_driver_universe_deprecated() -> set:
    """
    DEPRECATED: replaced by direct query to growth.yango_lima_driver_360_daily.
    Uses growth.yango_lima_orders_raw as driver universe filter.
    Kept for reference only. Do not use in new code.
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT DISTINCT driver_profile_id
            FROM growth.yango_lima_orders_raw
            WHERE driver_profile_id IS NOT NULL
        """)
        return {row["driver_profile_id"] for row in cur.fetchall()}


def _compute_supply_from_orders_deprecated(drivers, start, end) -> Dict[str, float]:
    """
    DEPRECATED: replaced by growth.yango_lima_driver_360_daily.supply_hours.
    Used (ended_at - created_at) from raw orders as proxy.
    Kept for reference only. Do not use in new code.
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT driver_profile_id,
                   SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, created_at) - created_at)) / 3600.0) AS sh
            FROM growth.yango_lima_orders_raw
            WHERE ended_at >= %(start)s AT TIME ZONE 'America/Lima'
              AND driver_profile_id = ANY(%(drivers)s)
              AND created_at IS NOT NULL AND ended_at IS NOT NULL AND ended_at > created_at
            GROUP BY driver_profile_id
        """, {"start": start.isoformat(), "drivers": list(drivers)})
        return {r["driver_profile_id"]: round(float(r["sh"] or 0), 4) for r in cur.fetchall()}


# =====================================================================
# CANONICAL BUILD — uses only 360_daily + history_weekly
# =====================================================================

def build_loyalty_sub50(week_start_date_str: str, target_weekly_trips: Optional[int] = None) -> Dict[str, Any]:
    target = target_weekly_trips if target_weekly_trips is not None else int(settings.LIMA_GROWTH_WEEKLY_TRIPS_TARGET)
    week_start = date.fromisoformat(week_start_date_str)
    week_end = week_start + timedelta(days=6)

    logger.info("Loyalty Sub-50 canonical build: %s - %s, target=%s", week_start, week_end, target)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check driver_360_daily data availability
        cur.execute(f"SELECT MAX(date) FROM {TABLE_360}")
        max_360_date = cur.fetchone()
        if not max_360_date or not max_360_date["max"]:
            return {"ok": False, "error": f"{TABLE_360} is empty. Run driver 360 pipeline first."}

        # 1. Aggregate current week from driver_360_daily
        cur.execute("""
            SELECT
                driver_profile_id,
                SUM(completed_orders) AS completed_orders_week,
                SUM(supply_hours) AS supply_hours_week,
                SUM(completed_orders) / NULLIF(SUM(supply_hours), 0) AS trips_per_supply_hour_week,
                MAX(driver_state) AS driver_state,
                MAX(productivity_band) AS productivity_band
            FROM growth.yango_lima_driver_360_daily
            WHERE date >= %(start)s AND date <= %(end)s
              AND active_flag = true
            GROUP BY driver_profile_id
        """, {"start": week_start, "end": week_end})

        week_data = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}
        logger.info("  Week data: %s drivers from 360_daily", len(week_data))

        if not week_data:
            return {"ok": False, "error": "No drivers with activity in the week window from 360_daily"}

        # 2. Get historical data from history_weekly (latest week for each driver)
        cur.execute("""
            SELECT DISTINCT ON (driver_profile_id)
                driver_profile_id,
                avg_orders_4w, avg_orders_8w, avg_orders_12w,
                best_week_12w, historical_band
            FROM growth.yango_lima_driver_history_weekly
            WHERE week_start_date <= %(ws)s
            ORDER BY driver_profile_id, week_start_date DESC
        """, {"ws": week_start})
        history_data = {r["driver_profile_id"]: dict(r) for r in cur.fetchall()}
        logger.info("  History data: %s drivers from history_weekly", len(history_data))

        # 3. Compute averages for supply/orders classification
        all_orders = [d["completed_orders_week"] for d in week_data.values()]
        all_supply = [float(d["supply_hours_week"] or 0) for d in week_data.values()]
        avg_orders = sum(all_orders) / len(all_orders) if all_orders else 0
        avg_supply = sum(all_supply) / len(all_supply) if all_supply else 0

        # 4. Build rows
        rows_to_upsert: list = []
        segment_counts: Dict[str, int] = {}
        recoverable_count = 0
        high_supply_low_orders_count = 0

        for driver_id, wd in week_data.items():
            completed = int(wd["completed_orders_week"] or 0)
            supply = float(wd["supply_hours_week"] or 0)
            tph = float(wd["trips_per_supply_hour_week"]) if wd.get("trips_per_supply_hour_week") is not None else None

            hist = history_data.get(driver_id, {})
            avg_4w = float(hist["avg_orders_4w"]) if hist.get("avg_orders_4w") is not None else None
            avg_8w = float(hist["avg_orders_8w"]) if hist.get("avg_orders_8w") is not None else None
            avg_12w = float(hist["avg_orders_12w"]) if hist.get("avg_orders_12w") is not None else None
            best_12w = int(hist["best_week_12w"]) if hist.get("best_week_12w") is not None else None
            hband = hist.get("historical_band")

            if completed >= target:
                continue

            distance = max(0, target - completed)
            segment = _classify_segment_dynamic(distance, target)
            legacy_label = LEGACY_LABELS.get(segment, segment)

            recoverable = (avg_12w is not None and avg_12w >= target)
            if recoverable:
                recoverable_count += 1

            is_hslo = (supply >= avg_supply and completed < avg_orders)
            if is_hslo:
                high_supply_low_orders_count += 1

            priority = _classify_growth_priority(segment, recoverable, is_hslo, distance)

            rows_to_upsert.append({
                "week_start_date": week_start,
                "week_end_date": week_end,
                "driver_profile_id": driver_id,
                "completed_orders_week": completed,
                "supply_hours_week": round(supply, 4),
                "trips_per_supply_hour_week": round(tph, 4) if tph else None,
                "productivity_band": wd.get("productivity_band"),
                "driver_state": wd.get("driver_state"),
                "segment": legacy_label,
                "distance_to_50": distance,
                "growth_priority": priority,
                "target_weekly_trips": target,
                "avg_orders_4w": round(avg_4w, 4) if avg_4w is not None else None,
                "avg_orders_8w": round(avg_8w, 4) if avg_8w is not None else None,
                "avg_orders_12w": round(avg_12w, 4) if avg_12w is not None else None,
                "best_week_12w": best_12w,
                "historical_band": hband,
                "recoverable_flag": recoverable,
                "canonical_source": "driver360_history_weekly",
                "source_version": SOURCE_VERSION,
            })

            segment_counts[segment] = segment_counts.get(segment, 0) + 1

        if not rows_to_upsert:
            logger.info("No sub-target drivers found (all above target=%s)", target)
            return _empty_summary(target)

        _upsert_canonical(cur, rows_to_upsert)
        conn.commit()

        driver_count = len(rows_to_upsert)
        return {
            "drivers_total": driver_count,
            "target_weekly_trips": target,
            "segments_dynamic": segment_counts,
            "recoverable_count": recoverable_count,
            "high_supply_low_orders_count": high_supply_low_orders_count,
            "avg_orders_week": round(sum(all_orders) / len(all_orders), 2) if all_orders else 0,
            "avg_supply_hours_week": round(avg_supply, 2),
            "canonical_source": "driver360_history_weekly",
        }


def _upsert_canonical(cur, rows: list) -> None:
    sql = """
        INSERT INTO growth.yango_lima_loyalty_sub50_weekly (
            week_start_date, week_end_date, driver_profile_id,
            completed_orders_week, supply_hours_week, trips_per_supply_hour_week,
            productivity_band, driver_state,
            segment, distance_to_50, growth_priority,
            target_weekly_trips,
            avg_orders_4w, avg_orders_8w, avg_orders_12w,
            best_week_12w, historical_band,
            recoverable_flag, canonical_source, source_version,
            last_calculated_at, source
        ) VALUES (
            %(week_start_date)s, %(week_end_date)s, %(driver_profile_id)s,
            %(completed_orders_week)s, %(supply_hours_week)s, %(trips_per_supply_hour_week)s,
            %(productivity_band)s, %(driver_state)s,
            %(segment)s, %(distance_to_50)s, %(growth_priority)s,
            %(target_weekly_trips)s,
            %(avg_orders_4w)s, %(avg_orders_8w)s, %(avg_orders_12w)s,
            %(best_week_12w)s, %(historical_band)s,
            %(recoverable_flag)s, %(canonical_source)s, %(source_version)s,
            now(), 'loyalty_sub50'
        )
        ON CONFLICT (week_start_date, driver_profile_id) DO UPDATE SET
            week_end_date = EXCLUDED.week_end_date,
            completed_orders_week = EXCLUDED.completed_orders_week,
            supply_hours_week = EXCLUDED.supply_hours_week,
            trips_per_supply_hour_week = EXCLUDED.trips_per_supply_hour_week,
            productivity_band = EXCLUDED.productivity_band,
            driver_state = EXCLUDED.driver_state,
            segment = EXCLUDED.segment,
            distance_to_50 = EXCLUDED.distance_to_50,
            growth_priority = EXCLUDED.growth_priority,
            target_weekly_trips = EXCLUDED.target_weekly_trips,
            avg_orders_4w = EXCLUDED.avg_orders_4w,
            avg_orders_8w = EXCLUDED.avg_orders_8w,
            avg_orders_12w = EXCLUDED.avg_orders_12w,
            best_week_12w = EXCLUDED.best_week_12w,
            historical_band = EXCLUDED.historical_band,
            recoverable_flag = EXCLUDED.recoverable_flag,
            canonical_source = EXCLUDED.canonical_source,
            source_version = EXCLUDED.source_version,
            last_calculated_at = now(),
            source = EXCLUDED.source
    """
    for row in rows:
        cur.execute(sql, row)


def _empty_summary(target: int) -> Dict[str, Any]:
    return {
        "drivers_total": 0,
        "target_weekly_trips": target,
        "segments_dynamic": {},
        "recoverable_count": 0,
        "high_supply_low_orders_count": 0,
        "avg_orders_week": 0,
        "avg_supply_hours_week": 0,
        "canonical_source": "driver360_history_weekly",
    }


# =====================================================================
# QUERY ENDPOINTS — read from loyalty_sub50_weekly
# =====================================================================

def get_sub50_summary(week_start_date_str: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if week_start_date_str:
            ws_filter = "WHERE week_start_date = %(ws)s"
            params = {"ws": week_start_date_str}
        else:
            cur.execute(f"SELECT MAX(week_start_date) FROM {TABLE_OUT}")
            latest = cur.fetchone()
            if not latest or not latest["max"]:
                return {"error": "No data. Run POST /build-loyalty-sub50 first."}
            ws_filter = "WHERE week_start_date = %(ws)s"
            params = {"ws": latest["max"]}

        cur.execute(f"""
            SELECT segment, COUNT(*) AS driver_count,
                   ROUND(AVG(distance_to_50), 1) AS avg_distance,
                   ROUND(AVG(supply_hours_week), 2) AS avg_supply,
                   ROUND(AVG(trips_per_supply_hour_week), 2) AS avg_tph,
                   SUM(CASE WHEN recoverable_flag THEN 1 ELSE 0 END) AS recoverable_count,
                   MAX(target_weekly_trips) AS target
            FROM {TABLE_OUT} {ws_filter}
            GROUP BY segment ORDER BY MIN(growth_priority)
        """, params)
        segments = [dict(r) for r in cur.fetchall()]

        cur.execute(f"""
            SELECT COUNT(*) AS drivers_total,
                   ROUND(AVG(distance_to_50), 1) AS avg_distance,
                   ROUND(AVG(supply_hours_week), 2) AS avg_supply,
                   ROUND(AVG(trips_per_supply_hour_week), 2) AS avg_tph,
                   SUM(CASE WHEN recoverable_flag THEN 1 ELSE 0 END) AS recoverable_total,
                   MAX(target_weekly_trips) AS target
            FROM {TABLE_OUT} {ws_filter}
        """, params)
        totals = dict(cur.fetchone() or {})

        return {"week_start_date": params.get("ws"), "segments": segments, "totals": totals}


def get_top_opportunities(week_start_date_str: Optional[str] = None, limit: int = 100) -> list:
    return _query_ranked(week_start_date_str, limit, order="growth_priority ASC, distance_to_50 ASC")


def get_supply_opportunities(week_start_date_str: Optional[str] = None, limit: int = 100) -> list:
    return _query_ranked(week_start_date_str, limit, where_extra="""
        AND supply_hours_week > (SELECT AVG(supply_hours_week) FROM growth.yango_lima_loyalty_sub50_weekly {ws})
        AND completed_orders_week < (SELECT AVG(completed_orders_week) FROM growth.yango_lima_loyalty_sub50_weekly {ws})
    """.replace("{ws}", _week_filter_sql(week_start_date_str)), order="supply_hours_week DESC, completed_orders_week ASC")


def get_recoverable(week_start_date_str: Optional[str] = None, limit: int = 100) -> list:
    return _query_ranked(week_start_date_str, limit, where_extra="AND recoverable_flag = true",
                         order="avg_orders_12w DESC NULLS LAST, distance_to_50 ASC")


def _week_filter_sql(week_start_date_str: Optional[str]) -> str:
    return f"WHERE week_start_date = '{week_start_date_str}'" if week_start_date_str else "WHERE week_start_date = (SELECT MAX(week_start_date) FROM growth.yango_lima_loyalty_sub50_weekly)"


def _query_ranked(week_start_date_str: Optional[str], limit: int, where_extra: str = "",
                  order: str = "growth_priority ASC, distance_to_50 ASC") -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        if week_start_date_str:
            ws_filter = "week_start_date = %(ws)s"
            params = {"ws": week_start_date_str, "limit": min(limit, 500)}
        else:
            cur.execute(f"SELECT MAX(week_start_date) FROM {TABLE_OUT}")
            latest = cur.fetchone()
            if not latest or not latest["max"]:
                return []
            ws_filter = "week_start_date = %(ws)s"
            params = {"ws": latest["max"], "limit": min(limit, 500)}

        where_clause = f"WHERE {ws_filter} {where_extra}"

        cur.execute(f"""
            SELECT driver_profile_id, completed_orders_week, distance_to_50,
                   supply_hours_week, trips_per_supply_hour_week,
                   segment, productivity_band, driver_state,
                   avg_orders_4w, avg_orders_8w, avg_orders_12w,
                   best_week_12w, historical_band, recoverable_flag
            FROM {TABLE_OUT}
            {where_clause}
            ORDER BY {order}
            LIMIT %(limit)s
        """, params)

        result = []
        for row in cur.fetchall():
            item = dict(row)
            item["driver_profile_id_masked"] = _mask_driver_id(item.pop("driver_profile_id", ""))
            for k in ("supply_hours_week", "avg_orders_4w", "avg_orders_8w", "avg_orders_12w"):
                if item.get(k) is not None:
                    item[k] = round(float(item[k]), 2) if isinstance(item[k], float) else item[k]
            if item.get("trips_per_supply_hour_week") is not None:
                item["trips_per_supply_hour_week"] = round(float(item["trips_per_supply_hour_week"]), 4)
            result.append(item)
        return result
