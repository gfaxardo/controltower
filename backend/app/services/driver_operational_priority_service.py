"""
Driver Operational Priority Service — FASE H3.5B + SH3
Execution Intelligence: Movement-first operational prioritization.

SH3: Fact-first with controlled runtime fallback.
No automatic heavy runtime in public/UI mode.

Deterministic rules engine for converting driver movement intelligence
into operational priorities. NO AI, NO ML, NO probabilistic scoring.

Priorities:
  P0_CRITICAL, P1_HIGH, P2_MEDIUM, P3_LOW, MONITOR, SUCCESS_TRACKING

Recoverability bands: HIGH, MEDIUM, LOW, UNKNOWN
Execution readiness: READY, MISSING_PHONE, CONTACT_LIMIT_REACHED,
                     ALREADY_IN_CAMPAIGN, STALE_DATA, BLOCKED

Principles:
  - movement > isolated state
  - rapid deterioration = high priority
  - top performers declining = maximum priority
  - recently reactivated = nurturing
  - stable FT/Elite = monitor
  - fully traceable, no black boxes
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.driver_segment_migration_service import (
    _classify_segment, _classify_movement, SEGMENT_ORDER,
)
from app.services.driver_serving_freshness_service import require_fact

logger = logging.getLogger(__name__)

TIMEOUT_MS = 30000

# Segment severity (higher = more critical to lose)
SEGMENT_VALUE = {
    "LEGEND": 7,
    "ELITE": 6,
    "FT": 5,
    "PT": 4,
    "CASUAL": 3,
    "OCCASIONAL": 2,
    "DORMANT": 0,
}

# Priority rules: (from_segment_value, to_segment_value, movement_type, days_without_trips_condition)
PRIORITY_RULES = [
    # P0_CRITICAL — top performers declining severely
    {
        "condition": lambda sv, days: sv >= 4 and days >= 7,
        "priority": "P0_CRITICAL",
        "reason": "High-value driver lost {days}d without trips after dropping from {from_seg} to {to_seg}",
    },
    # P1_HIGH — moderate performers declining or severe drops
    {
        "condition": lambda sv, days: sv >= 2 and days >= 3,
        "priority": "P1_HIGH",
        "reason": "Driver dropped from {from_seg} to {to_seg} with {days}d inactive",
    },
    # P1_HIGH — any driver with 14+ days without trips who had prior activity
    {
        "condition": lambda sv, days: days >= 14,
        "priority": "P1_HIGH",
        "reason": "Inactive {days}d after prior activity in {from_seg}",
    },
    # P2_MEDIUM — low performers declining
    {
        "condition": lambda sv, days: sv >= 0 and days >= 1,
        "priority": "P2_MEDIUM",
        "reason": "Low-activity driver further declining ({from_seg} → {to_seg})",
    },
]

# ─── Recoverability Assessment ────────────────────────────────────────────────

def _get_recoverability(from_seg: str, to_seg: str, movement_type: str) -> dict:
    """Deterministic recoverability assessment."""
    sv_from = SEGMENT_VALUE.get(from_seg, 0)
    sv_to = SEGMENT_VALUE.get(to_seg, 0)
    loss = sv_from - sv_to

    if movement_type in ("UPGRADE", "REACTIVATED", "NEW_ACTIVE"):
        return {"band": "HIGH", "reason": "Positive movement — nurture momentum"}

    if movement_type == "BECAME_DORMANT":
        if sv_from >= 5:
            return {"band": "HIGH", "reason": "High-value driver became dormant"}
        if sv_from >= 3:
            return {"band": "MEDIUM", "reason": "Mid-value driver became dormant"}
        return {"band": "LOW", "reason": "Low-value driver became dormant"}

    if movement_type == "DOWNGRADE":
        if loss >= 3:
            return {"band": "HIGH", "reason": "Severe multi-segment downgrade"}
        if loss >= 2:
            return {"band": "MEDIUM", "reason": "Moderate downgrade"}
        return {"band": "LOW", "reason": "Minor downgrade"}

    if movement_type == "CHURNED":
        if sv_from >= 4:
            return {"band": "MEDIUM", "reason": "High-value driver churned — may still be recoverable"}
        return {"band": "LOW", "reason": "Low-value churn"}

    return {"band": "UNKNOWN", "reason": "No rule defined for this movement type"}


def _compute_operational_priority(
    movement_type: str,
    from_seg: str,
    to_seg: str,
    days_without_trips: int,
    has_phone: bool,
    contact_attempts: int,
) -> dict:
    """Deterministic priority computation."""
    # SUCCESS_TRACKING cases
    if movement_type in ("UPGRADE", "REACTIVATED", "NEW_ACTIVE"):
        return {
            "operational_priority": "SUCCESS_TRACKING",
            "operational_reason": f"Positive movement: {movement_type} ({from_seg} → {to_seg})",
            "recoverability_band": _get_recoverability(from_seg, to_seg, movement_type)["band"],
        }

    # SAME_SEGMENT
    if movement_type == "SAME_SEGMENT":
        sv = SEGMENT_VALUE.get(from_seg, 0)
        if sv >= 5:
            return {
                "operational_priority": "MONITOR",
                "operational_reason": f"Stable high-value driver in {from_seg}. Monitor for changes.",
                "recoverability_band": "LOW",
            }
        return {
            "operational_priority": "P3_LOW",
            "operational_reason": f"Stable in {from_seg}. Low priority.",
            "recoverability_band": "LOW",
        }

    # Deterioration cases: DOWNGRADE, BECAME_DORMANT, CHURNED
    segment_value_loss = SEGMENT_VALUE.get(from_seg, 0) - SEGMENT_VALUE.get(to_seg, 0)

    if segment_value_loss >= 4:
        priority = "P0_CRITICAL"
        reason = f"Severe drop: {from_seg} → {to_seg} ({segment_value_loss} levels lost). {days_without_trips}d inactive."
    elif segment_value_loss >= 2:
        priority = "P1_HIGH"
        reason = f"Significant decline: {from_seg} → {to_seg}. {days_without_trips}d without trips."
    elif days_without_trips >= 14:
        priority = "P1_HIGH"
        reason = f"Extended inactivity: {days_without_trips}d without trips from {from_seg}."
    elif days_without_trips >= 7:
        priority = "P2_MEDIUM"
        reason = f"Moderate inactivity: {days_without_trips}d from {from_seg}."
    else:
        priority = "P3_LOW"
        reason = f"Minor change: {from_seg} → {to_seg}."

    recoverability = _get_recoverability(from_seg, to_seg, movement_type)

    return {
        "operational_priority": priority,
        "operational_reason": reason,
        "recoverability_band": recoverability["band"],
    }


def _compute_execution_readiness(
    has_phone: bool,
    contact_attempts: int,
    already_in_campaign: bool,
    data_stale: bool,
) -> str:
    if not has_phone:
        return "MISSING_PHONE"
    if contact_attempts >= 3:
        return "CONTACT_LIMIT_REACHED"
    if already_in_campaign:
        return "ALREADY_IN_CAMPAIGN"
    if data_stale:
        return "STALE_DATA"
    return "READY"


def _recommend_queue(priority: str, movement_type: str, recoverability: str) -> str:
    if priority == "P0_CRITICAL":
        return "RECOVERY_P0"
    if priority == "P1_HIGH":
        return "HIGH_VALUE_RECOVERY" if recoverability == "HIGH" else "REACTIVATION_STANDARD"
    if priority == "P2_MEDIUM":
        return "REACTIVATION_STANDARD"
    if priority == "SUCCESS_TRACKING":
        return "SUCCESS_NURTURING"
    if priority == "MONITOR":
        return "MONITOR_ONLY"
    if movement_type == "BECAME_DORMANT":
        return "REACTIVATION_STANDARD"
    return "MONITOR_ONLY"


# ─── Main actionable query ────────────────────────────────────────────────────

def get_actionable_movements(
    country=None, city=None, park_id=None,
    operational_priority=None, movement_type=None,
    recoverability_band=None,
    execution_ready_only=False,
    campaignable_only=False,
    allow_runtime=False,
    limit=100, offset=0,
) -> dict:
    """SH3: Try serving fact first. Only runtime if allow_runtime=True."""
    freshness = require_fact("driver_operational_priority_fact", allow_runtime=allow_runtime)

    if freshness["ready"]:
        result = _priorities_from_fact(country, city, park_id, operational_priority,
                                       movement_type, recoverability_band,
                                       execution_ready_only, campaignable_only, limit, offset)
        if result:
            return result

    if allow_runtime:
        return _priorities_runtime(country, city, park_id, operational_priority,
                                   movement_type, recoverability_band,
                                   execution_ready_only, campaignable_only, limit, offset)

    return {
        "status": freshness["freshness_status"],
        "error": "Serving fact not ready",
        "serving_source": None,
        "freshness_status": freshness["freshness_status"],
        "remediation": freshness.get("remediation", "Run refresh_driver_supply_facts.py"),
        "blocking_gaps": [f"Fact driver_operational_priority_fact is {freshness['freshness_status']}"],
        "warnings": [],
        "summary": {},
        "drivers": [],
        "total": 0,
    }


def _priorities_from_fact(country, city, park_id, op, mt, rb, ero, co, limit, offset):
    """Read from driver_operational_priority_fact."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET LOCAL statement_timeout = '15000'")

            cur.execute("""
                SELECT freshness_status, refreshed_at, max_operational_period
                FROM ops.driver_serving_freshness_fact
                WHERE fact_name = 'driver_operational_priority_fact'
            """)
            fresh = cur.fetchone()
            if not fresh or fresh["freshness_status"] == "blocked":
                return None

            conditions = ["1=1"]
            params = {}
            if country:
                conditions.append("country = %(country)s"); params["country"] = country
            if city:
                conditions.append("city = %(city)s"); params["city"] = city
            if park_id:
                conditions.append("park_id = %(park_id)s"); params["park_id"] = park_id
            if op:
                conditions.append("operational_priority = %(op)s"); params["op"] = op
            if mt:
                conditions.append("movement_type = %(mt)s"); params["mt"] = mt
            if rb:
                conditions.append("recoverability_band = %(rb)s"); params["rb"] = rb

            where = " AND ".join(conditions)

            # Summary
            cur.execute(f"""
                SELECT
                    COUNT(CASE WHEN operational_priority = 'P0_CRITICAL' THEN 1 END) as p0,
                    COUNT(CASE WHEN operational_priority = 'P1_HIGH' THEN 1 END) as p1,
                    COUNT(CASE WHEN operational_priority = 'P2_MEDIUM' THEN 1 END) as p2,
                    COUNT(CASE WHEN operational_priority = 'P3_LOW' THEN 1 END) as p3,
                    COUNT(CASE WHEN operational_priority = 'SUCCESS_TRACKING' THEN 1 END) as success,
                    COUNT(CASE WHEN operational_priority = 'MONITOR' THEN 1 END) as monitor,
                    COUNT(CASE WHEN recoverability_band = 'HIGH' THEN 1 END) as recoverable_high,
                    COUNT(CASE WHEN NOT (CASE WHEN operational_priority IN ('SUCCESS_TRACKING','MONITOR') THEN true ELSE false END) THEN 1 END) as critical_count
                FROM ops.driver_operational_priority_fact
                WHERE {where}
            """, params)
            summary = cur.fetchone() or {}

            # Drivers
            cur.execute(f"""
                SELECT p.driver_id, d.full_name as driver_name, d.phone,
                       p.country, p.city, p.park_id,
                       p.from_segment, p.to_segment, p.movement_type,
                       p.delta_trips as trips_delta,
                       p.operational_priority, p.operational_reason,
                       p.recommended_queue, p.recoverability_band,
                       p.recommended_contact_window
                FROM ops.driver_operational_priority_fact p
                LEFT JOIN public.drivers d ON p.driver_id = d.driver_id
                WHERE {where}
                ORDER BY
                    CASE p.operational_priority
                        WHEN 'P0_CRITICAL' THEN 1 WHEN 'P1_HIGH' THEN 2
                        WHEN 'P2_MEDIUM' THEN 3 ELSE 4
                    END
                LIMIT %(limit)s OFFSET %(offset)s
            """, {**params, "limit": limit, "offset": offset})
            drivers = [dict(r) for r in cur.fetchall()]

            # Enrich with execution readiness
            for d in drivers:
                d["execution_readiness"] = "READY" if d.get("phone") else "MISSING_PHONE"
                d["trips_previous"] = None
                d["trips_current"] = None
                d["days_without_trips"] = None

            warnings_list = []
            if fresh["freshness_status"] != "fresh":
                warnings_list.append(f"Fact is {fresh['freshness_status']}")

            cur.execute(f"SELECT COUNT(*) as total FROM ops.driver_operational_priority_fact WHERE {where}", params)
            total = cur.fetchone()["total"] if cur.rowcount > 0 else 0

            return {
                "status": "warning" if warnings_list else "ok",
                "serving_source": "driver_operational_priority_fact",
                "period_current": str(fresh["max_operational_period"])[:10] if fresh.get("max_operational_period") else None,
                "freshness_status": fresh["freshness_status"],
                "summary": {k: (v or 0) for k, v in (summary or {}).items()},
                "drivers": drivers,
                "total": total,
                "limit": limit, "offset": offset,
                "warnings": warnings_list,
                "blocking_gaps": [],
            }
    except Exception:
        return None


def _priorities_runtime(country, city, park_id, op, mt, rb, ero, co, limit, offset):
    """Legacy runtime compute. Only used when serving fact is unavailable."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get current and previous period
            cur.execute("SELECT MAX(activity_date) FROM ops.driver_daily_activity_fact")
            max_date = cur.fetchone()["max"] if cur.rowcount > 0 else None
            if not max_date:
                return {"status": "blocked", "error": "No activity data", "blocking_gaps": ["activity_fact empty"]}

            curr_start = (max_date - timedelta(days=max_date.weekday())).strftime("%Y-%m-%d")
            prev_start = (datetime.strptime(curr_start, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
            curr_end = (datetime.strptime(curr_start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
            prev_end = curr_start

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

            # Query activity per driver
            cur.execute(f"""
                SELECT driver_id,
                       COALESCE(SUM(CASE WHEN activity_date >= %(prev)s AND activity_date < %(curr)s THEN completed_trips END), 0) as prev_trips,
                       COALESCE(SUM(CASE WHEN activity_date >= %(curr)s AND activity_date <= %(end)s THEN completed_trips END), 0) as curr_trips
                FROM ops.driver_daily_activity_fact
                WHERE activity_date >= %(prev)s AND activity_date <= %(end)s
                {geo_where}
                GROUP BY driver_id
            """, {
                "prev": prev_start, "curr": curr_start, "end": curr_end, **geo_params,
            })
            rows = cur.fetchall()

            if not rows:
                return {"status": "warning", "drivers": [], "summary": {}, "warnings": ["No drivers in period"]}

            # Enrich with driver info
            driver_ids = [r["driver_id"] for r in rows]
            driver_info = {}
            if driver_ids:
                try:
                    cur.execute("""
                        SELECT driver_id, full_name as driver_name, phone, country, city, park_id
                        FROM public.drivers
                        WHERE driver_id IN %(ids)s
                    """, {"ids": tuple(driver_ids[:500])})
                    driver_info = {r["driver_id"]: dict(r) for r in cur.fetchall()}
                except Exception:
                    pass

            # Compute priorities
            enriched = []
            summary = {"p0": 0, "p1": 0, "p2": 0, "p3": 0, "success": 0, "monitor": 0, "recoverable_high": 0, "non_campaignable": 0}
            warnings_list = []

            for r in rows:
                did = r["driver_id"]
                prev_trips = int(r["prev_trips"] or 0)
                curr_trips = int(r["curr_trips"] or 0)
                from_seg = _classify_segment(prev_trips)
                to_seg = _classify_segment(curr_trips)
                movement = _classify_movement(from_seg, to_seg, prev_trips, curr_trips)

                info = driver_info.get(did, {})
                has_phone = bool(info.get("phone"))
                days_without = 0
                if curr_trips == 0:
                    # Calculate days since last activity
                    try:
                        cur.execute("""
                            SELECT MAX(activity_date) as last_trip
                            FROM ops.driver_daily_activity_fact
                            WHERE driver_id = %(did)s AND completed_trips > 0
                        """, {"did": did})
                        last_row = cur.fetchone()
                        if last_row and last_row["last_trip"]:
                            days_without = (datetime.now(timezone.utc).date() - last_row["last_trip"]).days
                    except Exception:
                        pass

                priority_result = _compute_operational_priority(
                    movement, from_seg, to_seg, days_without, has_phone, 0,
                )

                readiness = _compute_execution_readiness(has_phone, 0, False, False)

                rec_band = priority_result.get("recoverability_band", "UNKNOWN")
                driver_record = {
                    "driver_id": did,
                    "driver_name": info.get("driver_name"),
                    "phone": info.get("phone"),
                    "country": info.get("country"),
                    "city": info.get("city"),
                    "park_id": info.get("park_id"),
                    "from_segment": from_seg,
                    "to_segment": to_seg,
                    "trips_previous": prev_trips,
                    "trips_current": curr_trips,
                    "delta_trips": curr_trips - prev_trips,
                    "movement_type": movement,
                    "operational_priority": priority_result["operational_priority"],
                    "operational_reason": priority_result["operational_reason"].format(
                        from_seg=from_seg, to_seg=to_seg, days=days_without,
                    ),
                    "days_without_trips": days_without,
                    "execution_readiness": readiness,
                    "recommended_queue": _recommend_queue(
                        priority_result["operational_priority"], movement, rec_band,
                    ),
                    "recommended_contact_window": "24h" if priority_result["operational_priority"] in ("P0_CRITICAL", "P1_HIGH") else "72h" if priority_result["operational_priority"] == "P2_MEDIUM" else "7d",
                    "recoverability_band": rec_band,
                }

                # Apply filters
                if operational_priority and driver_record["operational_priority"] != operational_priority:
                    continue
                if movement_type and driver_record["movement_type"] != movement_type:
                    continue
                if recoverability_band and driver_record["recoverability_band"] != recoverability_band:
                    continue
                if execution_ready_only and driver_record["execution_readiness"] != "READY":
                    continue
                if campaignable_only and not has_phone:
                    continue

                enriched.append(driver_record)

                # Summary
                p = driver_record["operational_priority"]
                if p == "P0_CRITICAL":
                    summary["p0"] += 1
                elif p == "P1_HIGH":
                    summary["p1"] += 1
                elif p == "P2_MEDIUM":
                    summary["p2"] += 1
                elif p == "P3_LOW":
                    summary["p3"] += 1
                elif p == "SUCCESS_TRACKING":
                    summary["success"] += 1
                elif p == "MONITOR":
                    summary["monitor"] += 1

                if rec_band == "HIGH":
                    summary["recoverable_high"] += 1
                if not has_phone:
                    summary["non_campaignable"] += 1

            # Sort: P0 first, then P1, etc.
            priority_order = {"P0_CRITICAL": 0, "P1_HIGH": 1, "P2_MEDIUM": 2, "P3_LOW": 3, "SUCCESS_TRACKING": 4, "MONITOR": 5}
            enriched.sort(key=lambda d: (priority_order.get(d["operational_priority"], 99), -abs(d["delta_trips"])))

            total = len(enriched)
            paged = enriched[offset:offset + limit]

            if total < 5:
                warnings_list.append("Low driver count in period. Verify activity data freshness.")

            return {
                "status": "warning" if warnings_list else "ok",
                "period_current": curr_start,
                "period_previous": prev_start,
                "summary": summary,
                "drivers": paged,
                "total": total,
                "limit": limit,
                "offset": offset,
                "warnings": warnings_list,
                "blocking_gaps": [],
            }

    except Exception as e:
        logger.exception("Actionable movements compute failed")
        return {"status": "blocked", "error": str(e)[:300], "blocking_gaps": ["Compute failed"]}
