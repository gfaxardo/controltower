"""
Driver Segment Migration Service — HOTFIX H3.5A + SH2 + SH3
Control Foundation: Same-driver segment migration between periods.

SH3: Fact-first with controlled runtime fallback.
No automatic heavy runtime in public/UI mode.

Computes per-driver movement between segments from one period to the next.
Segment = trips/week classification:
  DORMANT=0, OCCASIONAL=1-4, CASUAL=5-29, PT=30-59, FT=60-119, ELITE=120-179, LEGEND=180+

Movement types:
  - SAME_SEGMENT: stayed in same segment
  - UPGRADE: moved to higher segment
  - DOWNGRADE: moved to lower segment
  - BECAME_DORMANT: went from active to 0 trips
  - REACTIVATED: went from dormant to active
  - NEW_ACTIVE: first appearance with trips
  - CHURNED: last appearance, no trips in current period

Principles:
  - Per driver_id comparison (not aggregate)
  - Uses ops.driver_daily_activity_fact
  - Lightweight queries per period
  - No full table scans
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.driver_serving_freshness_service import require_fact

logger = logging.getLogger(__name__)

TIMEOUT_MS = 30000

SEGMENT_BOUNDS = [
    (0, 0, "DORMANT"),
    (1, 4, "OCCASIONAL"),
    (5, 29, "CASUAL"),
    (30, 59, "PT"),
    (60, 119, "FT"),
    (120, 179, "ELITE"),
    (180, 999999, "LEGEND"),
]

SEGMENT_ORDER = {s: i for i, (_, _, s) in enumerate(SEGMENT_BOUNDS)}


def _classify_segment(trips: int) -> str:
    for lo, hi, label in SEGMENT_BOUNDS:
        if lo <= trips <= hi:
            return label
    return "DORMANT"


def _classify_movement(from_seg: str, to_seg: str, prev_trips: int, curr_trips: int) -> str:
    if prev_trips == 0 and curr_trips == 0:
        return "CHURNED"
    if prev_trips == 0 and curr_trips > 0:
        return "REACTIVATED" if from_seg == "DORMANT" else "NEW_ACTIVE"
    if prev_trips > 0 and curr_trips == 0:
        return "BECAME_DORMANT"
    if from_seg == to_seg:
        return "SAME_SEGMENT"

    from_order = SEGMENT_ORDER.get(from_seg, 99)
    to_order = SEGMENT_ORDER.get(to_seg, 99)

    if to_order < from_order:
        return "DOWNGRADE"
    return "UPGRADE"


def compute_segment_migration(
    country=None, city=None, park_id=None,
    period_grain="weekly",
    current_period=None, previous_period=None,
    include_same_segment=False,
    limit=100, offset=0,
    allow_runtime=False,
) -> dict:
    """SH3: Try serving fact first. Only runtime if allow_runtime=True (dev only)."""
    # Check fact readiness
    freshness = require_fact("driver_segment_migration_fact", allow_runtime=allow_runtime)

    if freshness["ready"]:
        result = _migration_from_fact(country, city, park_id, include_same_segment, limit, offset)
        if result:
            return result

    if allow_runtime:
        return _migration_runtime(country, city, park_id, period_grain,
                                  current_period, previous_period,
                                  include_same_segment, limit, offset)

    # Fact not ready + no runtime allowed → controlled failure
    return {
        "status": freshness["freshness_status"],
        "error": "Serving fact not ready",
        "serving_source": None,
        "freshness_status": freshness["freshness_status"],
        "remediation": freshness.get("remediation", "Run refresh_driver_supply_facts.py"),
        "blocking_gaps": [f"Fact driver_segment_migration_fact is {freshness['freshness_status']}"],
        "warnings": [],
        "summary": {},
        "matrix": [],
        "drivers_sample": [],
        "total": 0,
    }


def _migration_from_fact(country, city, park_id, include_same_segment, limit, offset):
    """Read from driver_segment_migration_fact with freshness check."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET LOCAL statement_timeout = '15000'")

            # Check fact freshness
            cur.execute("""
                SELECT freshness_status, refreshed_at, max_operational_period, row_count
                FROM ops.driver_serving_freshness_fact
                WHERE fact_name = 'driver_segment_migration_fact'
            """)
            fresh = cur.fetchone()
            if not fresh or fresh["freshness_status"] == "blocked":
                return None  # Fall back to runtime

            serving_source = "driver_segment_migration_fact"
            current_period_val = str(fresh["max_operational_period"])[:10] if fresh["max_operational_period"] else None
            freshness_status = fresh["freshness_status"]

            conditions = ["1=1"]
            params = {}
            if park_id:
                conditions.append("park_id = %(park_id)s")
                params["park_id"] = park_id
            elif country or city:
                try:
                    geo_conds = []
                    geo_params = {}
                    if country:
                        geo_conds.append("country = %(geo_country)s")
                        geo_params["geo_country"] = country
                    if city:
                        geo_conds.append("city = %(geo_city)s")
                        geo_params["geo_city"] = city
                    cur.execute(f"""
                        SELECT ARRAY_AGG(DISTINCT park_id) FILTER (WHERE park_id IS NOT NULL)
                        FROM dim.dim_park WHERE {' AND '.join(geo_conds)}
                    """, geo_params)
                    row_g = cur.fetchone()
                    resolved = row_g[0] if row_g and row_g[0] else None
                    if resolved:
                        conditions.append("park_id = ANY(%(resolved_pids)s)")
                        params["resolved_pids"] = resolved
                    else:
                        if country:
                            conditions.append("country = %(country)s")
                            params["country"] = country
                        if city:
                            conditions.append("city = %(city)s")
                            params["city"] = city
                except Exception:
                    if country:
                        conditions.append("country = %(country)s")
                        params["country"] = country
                    if city:
                        conditions.append("city = %(city)s")
                        params["city"] = city
            if not include_same_segment:
                conditions.append("movement_type != 'SAME_SEGMENT'")

            where = " AND ".join(conditions)

            # Summary
            cur.execute(f"""
                SELECT
                    COUNT(*) as total_drivers_compared,
                    COUNT(CASE WHEN movement_type = 'UPGRADE' THEN 1 END) as upgrades,
                    COUNT(CASE WHEN movement_type = 'DOWNGRADE' THEN 1 END) as downgrades,
                    COUNT(CASE WHEN movement_type = 'SAME_SEGMENT' THEN 1 END) as same_segment,
                    COUNT(CASE WHEN movement_type = 'BECAME_DORMANT' THEN 1 END) as became_dormant,
                    COUNT(CASE WHEN movement_type = 'REACTIVATED' THEN 1 END) as reactivated,
                    COUNT(CASE WHEN movement_type = 'NEW_ACTIVE' THEN 1 END) as new_active,
                    COUNT(CASE WHEN movement_type = 'CHURNED' THEN 1 END) as churned
                FROM ops.driver_segment_migration_fact
                WHERE {where}
            """, params)
            summary = cur.fetchone() or {}

            # Matrix
            cur.execute(f"""
                SELECT from_segment, to_segment, COUNT(*) as drivers_count
                FROM ops.driver_segment_migration_fact
                WHERE {where} AND movement_type != 'SAME_SEGMENT'
                GROUP BY from_segment, to_segment
                ORDER BY drivers_count DESC
                LIMIT 50
            """, params)
            matrix = [dict(r) for r in cur.fetchall()]

            # Driver sample
            cur.execute(f"""
                SELECT m.driver_id, d.full_name as driver_name, d.phone,
                       m.from_segment, m.to_segment, m.trips_previous, m.trips_current,
                       m.movement_type, m.country, m.city, m.park_id
                FROM ops.driver_segment_migration_fact m
                LEFT JOIN public.drivers d ON m.driver_id = d.driver_id
                WHERE {where} AND movement_type != 'SAME_SEGMENT'
                ORDER BY ABS(m.trips_current - m.trips_previous) DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, {**params, "limit": limit, "offset": offset})
            sample = [dict(r) for r in cur.fetchall()]

            warnings_list = []
            if freshness_status != "fresh":
                warnings_list.append(f"Serving fact is {freshness_status}. Refreshed at {fresh.get('refreshed_at')}")

            return {
                "status": "warning" if warnings_list else "ok",
                "serving_source": serving_source,
                "period_current": current_period_val,
                "period_previous": None,
                "period_grain": "weekly",
                "summary": dict(summary) if summary else {},
                "matrix": matrix,
                "drivers_sample": sample,
                "total": summary.get("total_drivers_compared", 0) if summary else 0,
                "limit": limit,
                "offset": offset,
                "freshness_status": freshness_status,
                "refreshed_at": fresh["refreshed_at"].isoformat() if fresh.get("refreshed_at") else None,
                "warnings": warnings_list,
                "blocking_gaps": [],
            }
    except Exception:
        return None


def _migration_runtime(country, city, park_id, period_grain, current_period, previous_period, include_same_segment, limit, offset):
    """Legacy runtime compute. Only used when serving fact is unavailable."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Determine periods from activity fact
            cur.execute("SELECT MAX(activity_date) FROM ops.driver_daily_activity_fact")
            max_date_row = cur.fetchone()
            max_date = max_date_row["max"] if max_date_row and max_date_row["max"] else None

            if not max_date:
                return {"status": "blocked", "error": "No activity data available", "blocking_gaps": ["driver_daily_activity_fact empty"]}

            if not current_period:
                if period_grain == "weekly":
                    # Get latest complete week (Monday-Sunday)
                    cur.execute("""
                        SELECT date_trunc('week', activity_date)::date as week_start
                        FROM ops.driver_daily_activity_fact
                        WHERE activity_date < date_trunc('week', CURRENT_DATE)::date
                        GROUP BY 1 ORDER BY 1 DESC LIMIT 1
                    """)
                    week_row = cur.fetchone()
                    current_period = str(week_row["week_start"]) if week_row else str(max_date)
                else:
                    current_period = str(max_date)[:7] + "-01"

            if not previous_period:
                if period_grain == "weekly":
                    prev = (datetime.strptime(str(current_period)[:10], "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
                else:
                    dt = datetime.strptime(str(current_period)[:10], "%Y-%m-%d")
                    if dt.month == 1:
                        prev = dt.replace(year=dt.year - 1, month=12, day=1).strftime("%Y-%m-%d")
                    else:
                        prev = dt.replace(month=dt.month - 1, day=1).strftime("%Y-%m-%d")
                previous_period = prev

            curr_start = str(current_period)[:10]
            prev_start = str(previous_period)[:10]

            if period_grain == "weekly":
                curr_end = (datetime.strptime(curr_start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
                prev_end = (datetime.strptime(prev_start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
            else:
                curr_end = (datetime.strptime(curr_start, "%Y-%m-%d").replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                curr_end = curr_end.strftime("%Y-%m-%d")
                prev_end = (datetime.strptime(prev_start, "%Y-%m-%d").replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                prev_end = prev_end.strftime("%Y-%m-%d")

            # Build geo filter
            geo_conditions = []
            geo_params = {}
            if country:
                geo_conditions.append("country = %(country)s")
                geo_params["country"] = country
            if city:
                geo_conditions.append("city = %(city)s")
                geo_params["city"] = city
            if park_id:
                geo_conditions.append("park_id = %(park_id)s")
                geo_params["park_id"] = park_id
            geo_where = " AND " + " AND ".join(geo_conditions) if geo_conditions else ""

            # Query: driver activity per period
            prev_query = f"""
                SELECT driver_id, COALESCE(SUM(completed_trips), 0) as total_trips
                FROM ops.driver_daily_activity_fact
                WHERE activity_date >= %(prev_start)s AND activity_date <= %(prev_end)s
                {geo_where}
                GROUP BY driver_id
            """
            curr_query = f"""
                SELECT driver_id, COALESCE(SUM(completed_trips), 0) as total_trips
                FROM ops.driver_daily_activity_fact
                WHERE activity_date >= %(curr_start)s AND activity_date <= %(curr_end)s
                {geo_where}
                GROUP BY driver_id
            """

            params_prev = {"prev_start": prev_start, "prev_end": prev_end, **geo_params}
            params_curr = {"curr_start": curr_start, "curr_end": curr_end, **geo_params}

            cur.execute(prev_query, params_prev)
            prev_data = {r["driver_id"]: int(r["total_trips"] or 0) for r in cur.fetchall()}

            cur.execute(curr_query, params_curr)
            curr_data = {r["driver_id"]: int(r["total_trips"] or 0) for r in cur.fetchall()}

            # Compute migration for all drivers
            all_driver_ids = set(list(prev_data.keys()) + list(curr_data.keys()))
            movements = []
            summary = {
                "total_drivers_compared": 0,
                "upgrades": 0, "downgrades": 0, "same_segment": 0,
                "became_dormant": 0, "reactivated": 0, "new_active": 0, "churned": 0,
            }
            matrix_data = {}  # (from, to) -> count

            for did in all_driver_ids:
                prev_trips = prev_data.get(did, 0)
                curr_trips = curr_data.get(did, 0)
                from_seg = _classify_segment(prev_trips)
                to_seg = _classify_segment(curr_trips)
                movement = _classify_movement(from_seg, to_seg, prev_trips, curr_trips)

                summary["total_drivers_compared"] += 1
                if movement == "UPGRADE":
                    summary["upgrades"] += 1
                elif movement == "DOWNGRADE":
                    summary["downgrades"] += 1
                elif movement == "SAME_SEGMENT":
                    summary["same_segment"] += 1
                elif movement == "BECAME_DORMANT":
                    summary["became_dormant"] += 1
                elif movement == "REACTIVATED":
                    summary["reactivated"] += 1
                elif movement == "NEW_ACTIVE":
                    summary["new_active"] += 1
                elif movement == "CHURNED":
                    summary["churned"] += 1

                if movement != "SAME_SEGMENT" or include_same_segment:
                    key = (from_seg, to_seg)
                    matrix_data[key] = matrix_data.get(key, 0) + 1

                movements.append({
                    "driver_id": did,
                    "from_segment": from_seg,
                    "to_segment": to_seg,
                    "trips_previous": prev_trips,
                    "trips_current": curr_trips,
                    "delta_trips": curr_trips - prev_trips,
                    "movement_type": movement,
                })

            # Build matrix
            matrix = []
            for (from_s, to_s), cnt in sorted(matrix_data.items()):
                matrix.append({"from_segment": from_s, "to_segment": to_s, "drivers_count": cnt})

            # Get driver names/phones for sample
            driver_sample = []
            significant_moves = [m for m in movements if m["movement_type"] not in ("SAME_SEGMENT", "CHURNED")]
            significant_moves.sort(key=lambda m: abs(m["delta_trips"]), reverse=True)
            sample_ids = [m["driver_id"] for m in significant_moves[:min(50, len(significant_moves))]]

            if sample_ids:
                try:
                    cur.execute("""
                        SELECT driver_id, driver_name, phone, country, city, park_id
                        FROM public.drivers
                        WHERE driver_id IN %(ids)s
                        LIMIT 50
                    """, {"ids": tuple(sample_ids)})
                    driver_info = {r["driver_id"]: r for r in cur.fetchall()}
                except Exception:
                    driver_info = {}

                for m in significant_moves[:min(50, len(significant_moves))]:
                    info = driver_info.get(m["driver_id"], {})
                    driver_sample.append({
                        "driver_id": m["driver_id"],
                        "driver_name": info.get("driver_name"),
                        "phone": info.get("phone"),
                        "country": info.get("country"),
                        "city": info.get("city"),
                        "park_id": info.get("park_id"),
                        "from_segment": m["from_segment"],
                        "to_segment": m["to_segment"],
                        "trips_previous": m["trips_previous"],
                        "trips_current": m["trips_current"],
                        "delta_trips": m["delta_trips"],
                        "movement_type": m["movement_type"],
                    })

            # Paginate
            paged_movements = significant_moves[offset:offset + limit]

            warnings_list = []
            if summary["total_drivers_compared"] < 5:
                warnings_list.append("Very low driver count. Verify activity data freshness.")

            return {
                "status": "warning" if warnings_list else "ok",
                "period_previous": prev_start,
                "period_current": curr_start,
                "period_grain": period_grain,
                "summary": summary,
                "matrix": matrix[:50],
                "drivers_sample": driver_sample[:limit],
                "total": summary["total_drivers_compared"],
                "limit": limit,
                "offset": offset,
                "warnings": warnings_list,
                "blocking_gaps": [],
            }

    except Exception as e:
        logger.exception("Segment migration compute failed")
        return {"status": "blocked", "error": str(e)[:300], "blocking_gaps": ["Migration computation failed"]}
