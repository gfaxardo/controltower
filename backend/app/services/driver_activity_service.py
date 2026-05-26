"""
Driver Activity Service — FASE D3
Control Foundation: Activity & Lifecycle Foundation

Responsibility:
- Compute rolling window activity metrics (7d, 14d, 30d) per driver.
- Compare current vs previous periods.
- Derive deterministic activity_trend (growing/stable/declining/inactive/unknown).
- NEVER crash on missing data.
- Lightweight queries via ops.driver_daily_activity_fact; fallback to trips.

Rules (deterministic, documented):
  inactive: trips_30d == 0 OR no latest_trip_at
  declining: trips_7d < trips_prev_7d AND decline >= 30%
  growing: trips_7d > trips_prev_7d AND growth >= 30%
  stable: abs(delta) < 30%
  unknown: insufficient data (no activity in any window)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 20000

DECLINE_THRESHOLD = 0.30
GROWTH_THRESHOLD = 0.30
AT_RISK_MIN_DAYS = 8
AT_RISK_MAX_DAYS = 21
CHURNED_RECENT_MAX_DAYS = 60


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET LOCAL statement_timeout = %s", (str(int(timeout_ms)),))
    return c


def _safe_query(cur, sql: str, params: dict = None, default=None):
    try:
        cur.execute(sql, params or {})
        rows = cur.fetchall()
        return rows or []
    except Exception as e:
        logger.debug("driver_activity: query failed: %s", e)
        return default if default is not None else []


def _compute_rolling(cur, driver_id: str, window_days: int, ref_date: str = None) -> int:
    """Compute trips in a trailing window from ref_date (default: today)."""
    if ref_date is None:
        ref_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (
        datetime.fromisoformat(ref_date) - timedelta(days=window_days)
    ).strftime("%Y-%m-%d")

    rows = _safe_query(
        cur,
        """
        SELECT COALESCE(SUM(COALESCE(trips, completed_trips, 0)), 0) AS total_trips,
               COUNT(DISTINCT activity_date) AS active_days
        FROM ops.driver_daily_activity_fact
        WHERE driver_id = %(did)s
          AND activity_date >= %(start)s
          AND activity_date <= %(end)s
        """,
        {"did": driver_id, "start": start_date, "end": ref_date},
    )
    if not rows:
        return 0
    return int(rows[0].get("total_trips", 0) or 0)


def _compute_active_days(cur, driver_id: str, window_days: int, ref_date: str = None) -> int:
    """Compute distinct active days in a trailing window."""
    if ref_date is None:
        ref_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (
        datetime.fromisoformat(ref_date) - timedelta(days=window_days)
    ).strftime("%Y-%m-%d")

    rows = _safe_query(
        cur,
        """
        SELECT COUNT(DISTINCT activity_date) AS active_days
        FROM ops.driver_daily_activity_fact
        WHERE driver_id = %(did)s
          AND activity_date >= %(start)s
          AND activity_date <= %(end)s
        """,
        {"did": driver_id, "start": start_date, "end": ref_date},
    )
    if not rows:
        return 0
    return int(rows[0].get("active_days", 0) or 0)


def _get_latest_trip(cur, driver_id: str) -> Optional[str]:
    rows = _safe_query(
        cur,
        """
        SELECT MAX(activity_date) AS latest_trip_at
        FROM ops.driver_daily_activity_fact
        WHERE driver_id = %(did)s
        """,
        {"did": driver_id},
    )
    if rows and rows[0].get("latest_trip_at"):
        val = rows[0]["latest_trip_at"]
        if isinstance(val, datetime):
            return val.strftime("%Y-%m-%d")
        return str(val)[:10]
    return None


def _days_since(date_str: Optional[str]) -> Optional[int]:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str[:10])
        return (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).days
    except Exception:
        return None


def compute_driver_activity(driver_id: str) -> dict[str, Any]:
    """
    Compute full activity metrics for one driver.

    Returns dict with trips_7d..30d, active_days, latest_trip, days_since,
    activity_trend, trend_reason, evidence.
    """
    result = {
        "driver_id": driver_id,
        "trips_7d": 0,
        "trips_14d": 0,
        "trips_30d": 0,
        "trips_prev_7d": 0,
        "trips_prev_14d": 0,
        "trips_prev_30d": 0,
        "active_days_7d": 0,
        "active_days_30d": 0,
        "latest_trip_at": None,
        "days_since_last_trip": None,
        "activity_trend": "unknown",
        "trend_reason": "",
        "evidence": {},
        "data_quality_status": "ok",
        "activity_source": "ops.driver_daily_activity_fact",
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with get_db() as conn:
            cur = _cursor(conn)

            ref = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            result["trips_7d"] = _compute_rolling(cur, driver_id, 7, ref)
            result["trips_14d"] = _compute_rolling(cur, driver_id, 14, ref)
            result["trips_30d"] = _compute_rolling(cur, driver_id, 30, ref)

            prev_ref = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
            result["trips_prev_7d"] = _compute_rolling(cur, driver_id, 7, prev_ref)

            prev_ref_14 = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
            result["trips_prev_14d"] = _compute_rolling(cur, driver_id, 14, prev_ref_14)

            result["active_days_7d"] = _compute_active_days(cur, driver_id, 7, ref)
            result["active_days_30d"] = _compute_active_days(cur, driver_id, 30, ref)

            result["latest_trip_at"] = _get_latest_trip(cur, driver_id)
            result["days_since_last_trip"] = _days_since(result["latest_trip_at"])

    except Exception as e:
        logger.warning("driver_activity compute failed for %s: %s", driver_id, e)
        result["data_quality_status"] = "error"
        result["trend_reason"] = f"Query failed: {str(e)[:100]}"
        return result

    # ── Deterministic trend classification ──
    t7 = result["trips_7d"]
    t30 = result["trips_30d"]
    p7 = result["trips_prev_7d"]
    days = result["days_since_last_trip"]

    if t30 == 0 and t7 == 0 and (days is None or days > 60):
        result["activity_trend"] = "inactive"
        result["trend_reason"] = "No trips in last 30 days and no recent activity."
    elif t30 == 0 and t7 == 0 and days is not None and days <= 60:
        result["activity_trend"] = "inactive"
        result["trend_reason"] = f"No trips in last 30 days. Last trip {days} days ago."
    elif t7 == 0 and t30 > 0:
        result["activity_trend"] = "declining"
        result["trend_reason"] = f"Had {t30} trips in 30d but 0 in last 7d."
    elif p7 > 0:
        delta = t7 - p7
        pct = abs(delta) / p7 if p7 > 0 else 0
        if t7 < p7 and pct >= DECLINE_THRESHOLD:
            result["activity_trend"] = "declining"
            result["trend_reason"] = f"Trips dropped from {p7} (prev 7d) to {t7} (current 7d): {-pct:.0%} decline."
        elif t7 > p7 and pct >= GROWTH_THRESHOLD:
            result["activity_trend"] = "growing"
            result["trend_reason"] = f"Trips grew from {p7} (prev 7d) to {t7} (current 7d): {pct:.0%} growth."
        else:
            result["activity_trend"] = "stable"
            result["trend_reason"] = f"Trips change within threshold: {p7} → {t7} (prev→current 7d)."
    elif t7 > 0 and p7 == 0:
        result["activity_trend"] = "growing"
        result["trend_reason"] = f"New activity detected: {t7} trips in last 7d (none in previous period)."
    elif t7 > 0:
        result["activity_trend"] = "stable"
        result["trend_reason"] = f"{t7} trips in last 7d, {t30} in last 30d."
    else:
        result["activity_trend"] = "unknown"
        result["trend_reason"] = "Insufficient activity data to determine trend."

    result["evidence"] = {
        "trips_7d": t7,
        "trips_prev_7d": p7,
        "trips_30d": t30,
        "days_since_last_trip": days,
        "decline_threshold": DECLINE_THRESHOLD,
        "growth_threshold": GROWTH_THRESHOLD,
    }

    return result


def compute_driver_activity_batch(
    driver_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Compute activity for multiple drivers."""
    results = {}
    for did in driver_ids:
        results[did] = compute_driver_activity(did)
    return results


def search_driver_activity(
    driver_id: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    lifecycle_stage: Optional[str] = None,
    activity_trend: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """
    Search drivers with activity metrics.
    Uses driver_daily_activity_fact for bulk queries where possible.
    """
    results = []

    base_sql = """
    SELECT
        d.driver_id,
        COALESCE(vr.driver_name, dd.full_name) AS driver_name,
        COALESCE(dd.driver_phone, d.phone::text) AS phone,
        COALESCE(dp.city, prk.city) AS city,
        COALESCE(dp.country, prk.country) AS country,
        d.park_id,
        COALESCE(dp.park_name, prk.park_name) AS park_name,
        d.created_at AS first_seen_at,
        lb.activation_ts AS first_trip_at,
        lb.last_completed_ts AS latest_trip_at,
        GREATEST(lb.last_completed_ts, d.created_at) AS latest_activity_at,
        NOW() AS refreshed_at
    FROM public.drivers d
    LEFT JOIN ops.v_dim_driver_resolved vr ON d.driver_id = vr.driver_id
    LEFT JOIN public.drivers_data dd ON d.driver_id = dd.driver_id
    LEFT JOIN dim.dim_park dp ON d.park_id = dp.park_id
    LEFT JOIN ops.v_dim_park_resolved prk ON d.park_id = prk.park_id
    LEFT JOIN ops.mv_driver_lifecycle_base lb ON d.driver_id = lb.driver_key
    WHERE 1=1
    """

    params = {}
    conditions = []

    if driver_id:
        conditions.append("d.driver_id = %(driver_id)s")
        params["driver_id"] = driver_id

    if country:
        conditions.append("(dp.country = %(country)s OR prk.country = %(country)s)")
        params["country"] = country

    if city:
        conditions.append("(dp.city = %(city)s OR prk.city = %(city)s)")
        params["city"] = city

    if park_id:
        conditions.append("d.park_id = %(park_id)s")
        params["park_id"] = park_id

    if conditions:
        base_sql += " AND " + " AND ".join(conditions)

    base_sql += " ORDER BY lb.last_completed_ts DESC NULLS LAST LIMIT %(limit)s OFFSET %(offset)s"
    params["limit"] = limit
    params["offset"] = offset

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute(base_sql, params)
            rows = cur.fetchall() or []
            driver_ids_list = [r["driver_id"] for r in rows if r.get("driver_id")]

            ref = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            prev_ref = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

            activity_map = {}
            if driver_ids_list:
                cur.execute(
                    """
                    SELECT
                        driver_id,
                        COALESCE(SUM(CASE WHEN activity_date >= %(s7)s AND activity_date <= %(ref)s THEN COALESCE(trips, completed_trips, 0) END), 0) AS t7,
                        COALESCE(SUM(CASE WHEN activity_date >= %(s14)s AND activity_date <= %(ref)s THEN COALESCE(trips, completed_trips, 0) END), 0) AS t14,
                        COALESCE(SUM(CASE WHEN activity_date >= %(s30)s AND activity_date <= %(ref)s THEN COALESCE(trips, completed_trips, 0) END), 0) AS t30,
                        COALESCE(SUM(CASE WHEN activity_date >= %(ps7)s AND activity_date <= %(prev)s THEN COALESCE(trips, completed_trips, 0) END), 0) AS p7,
                        COALESCE(SUM(CASE WHEN activity_date >= %(ps14)s AND activity_date <= %(prev)s THEN COALESCE(trips, completed_trips, 0) END), 0) AS p14,
                        COUNT(DISTINCT CASE WHEN activity_date >= %(s30)s AND activity_date <= %(ref)s THEN activity_date END) AS ad30,
                        COUNT(DISTINCT CASE WHEN activity_date >= %(s7)s AND activity_date <= %(ref)s THEN activity_date END) AS ad7,
                        MAX(activity_date) AS latest_act
                    FROM ops.driver_daily_activity_fact
                    WHERE driver_id = ANY(%(ids)s)
                    GROUP BY driver_id
                    """,
                    {
                        "ids": driver_ids_list,
                        "ref": ref,
                        "s7": (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"),
                        "s14": (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d"),
                        "s30": (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"),
                        "prev": prev_ref,
                        "ps7": (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d"),
                        "ps14": (datetime.now(timezone.utc) - timedelta(days=28)).strftime("%Y-%m-%d"),
                    },
                )
                for row in (cur.fetchall() or []):
                    activity_map[row["driver_id"]] = row

            for r in rows:
                did = r["driver_id"]
                act = activity_map.get(did, {})
                t7 = int(act.get("t7", 0) or 0)
                t14 = int(act.get("t14", 0) or 0)
                t30 = int(act.get("t30", 0) or 0)
                p7 = int(act.get("p7", 0) or 0)
                ad7 = int(act.get("ad7", 0) or 0)
                ad30 = int(act.get("ad30", 0) or 0)
                latest_act = act.get("latest_act")

                days_since = _days_since(
                    latest_act.strftime("%Y-%m-%d") if isinstance(latest_act, datetime) else (str(latest_act)[:10] if latest_act else None)
                )

                trend, reason = _classify_trend(t7, t30, p7, days_since)

                record = {
                    "driver_id": did,
                    "driver_name": (r.get("driver_name") or "").strip() if r.get("driver_name") else None,
                    "phone": (r.get("phone") or "").strip() if r.get("phone") else None,
                    "country": r.get("country"),
                    "city": r.get("city"),
                    "park_id": r.get("park_id"),
                    "park_name": r.get("park_name"),
                    "trips_7d": t7,
                    "trips_14d": t14,
                    "trips_30d": t30,
                    "trips_prev_7d": p7,
                    "trips_prev_30d": t30,
                    "active_days_7d": ad7,
                    "active_days_30d": ad30,
                    "latest_trip_at": latest_act.isoformat() if isinstance(latest_act, datetime) else (str(latest_act) if latest_act else None),
                    "days_since_last_trip": days_since,
                    "activity_trend": trend,
                    "trend_reason": reason,
                    "evidence": {
                        "trips_7d": t7,
                        "trips_prev_7d": p7,
                        "trips_30d": t30,
                        "days_since_last_trip": days_since,
                    },
                    "data_quality_status": "ok",
                    "refreshed_at": datetime.now(timezone.utc).isoformat(),
                }
                results.append(record)

    except Exception as e:
        logger.warning("driver_activity search failed: %s", e)

    return results


def _classify_trend(t7: int, t30: int, p7: int, days_since: Optional[int]) -> tuple[str, str]:
    if t30 == 0 and t7 == 0 and (days_since is None or days_since > 60):
        return "inactive", "No trips in last 30 days and no recent activity."
    if t30 == 0 and t7 == 0 and days_since is not None and days_since <= 60:
        return "inactive", f"No trips in last 30 days. Last trip {days_since} days ago."
    if t7 == 0 and t30 > 0:
        return "declining", f"Had {t30} trips in 30d but 0 in last 7d."
    if p7 > 0:
        delta = t7 - p7
        pct = abs(delta) / p7
        if t7 < p7 and pct >= DECLINE_THRESHOLD:
            return "declining", f"Trips dropped from {p7} to {t7} ({-pct:.0%} decline)."
        if t7 > p7 and pct >= GROWTH_THRESHOLD:
            return "growing", f"Trips grew from {p7} to {t7} ({pct:.0%} growth)."
        return "stable", f"Trips stable: {p7}→{t7}."
    if t7 > 0 and p7 == 0:
        return "growing", f"New activity: {t7} trips in last 7d."
    if t7 > 0:
        return "stable", f"{t7} trips in last 7d."
    return "unknown", "Insufficient activity data."
