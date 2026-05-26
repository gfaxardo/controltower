"""
Driver Lifecycle Service — FASE D3
Control Foundation: Activity & Lifecycle Foundation

Deterministic lifecycle state machine.
No scoring probabilístico. No ML. No IA.

States (in priority order):
  NO_ACTIVITY_DATA       → No identity + no activity data available
  REGISTERED_NO_TRIPS    → Has identity but first_trip_at is null
  ACTIVE                 → trips_30d > 0 AND days_since_last_trip <= 7
  ACTIVE_LOW             → trips_30d > 0 AND trips_7d == 0 AND days_since_last_trip <= 7
  DECLINING              → activity_trend = declining AND trips_30d > 0
  AT_RISK                → days_since_last_trip BETWEEN 8 AND 21, had prior activity
  CHURNED_RECENT         → days_since_last_trip BETWEEN 22 AND 60
  CHURNED_LONG           → days_since_last_trip > 60
  REACTIVATED            → Had recent activity after being churned > 21 days

Each state returns:
  lifecycle_stage, lifecycle_reason, evidence, computed_at, data_quality_status
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.driver_activity_service import compute_driver_activity

logger = logging.getLogger(__name__)


def classify_lifecycle(activity_data: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic lifecycle classification from activity metrics.

    Args:
        activity_data: result from compute_driver_activity()

    Returns lifecycle dict.
    """
    t7 = activity_data.get("trips_7d", 0) or 0
    t30 = activity_data.get("trips_30d", 0) or 0
    days_since = activity_data.get("days_since_last_trip")
    trend = activity_data.get("activity_trend", "unknown")
    first_trip = activity_data.get("first_trip_at")
    latest = activity_data.get("latest_trip_at")

    stage = "NO_ACTIVITY_DATA"
    reason = ""
    evidence = {"trips_7d": t7, "trips_30d": t30, "days_since_last_trip": days_since, "activity_trend": trend}

    # NO_ACTIVITY_DATA
    if (t30 == 0 and t7 == 0) and (days_since is None):
        stage = "NO_ACTIVITY_DATA"
        reason = "No activity data available for this driver."
        return _result(stage, reason, evidence)

    # REGISTERED_NO_TRIPS
    if first_trip is None and t30 == 0 and t7 == 0:
        stage = "REGISTERED_NO_TRIPS"
        reason = "Driver registered but no first trip recorded."
        return _result(stage, reason, evidence)

    # REACTIVATED (check first — had prior churn, now active again)
    if days_since is not None and days_since <= 7 and t7 > 0:
        prior_churn = _was_churned(activity_data)
        if prior_churn:
            stage = "REACTIVATED"
            reason = f"Driver was inactive for >21 days and now has {t7} trips in last 7d."
            return _result(stage, reason, evidence)

    # CHURNED_LONG
    if days_since is not None and days_since > 60:
        stage = "CHURNED_LONG"
        reason = f"No trips in last {days_since} days (>60). Long-term churn."
        return _result(stage, reason, evidence)

    # CHURNED_RECENT
    if days_since is not None and days_since > 21:
        stage = "CHURNED_RECENT"
        reason = f"No trips in last {days_since} days (22-60). Recent churn."
        return _result(stage, reason, evidence)

    # AT_RISK
    if days_since is not None and days_since >= 8 and days_since <= 21:
        stage = "AT_RISK"
        reason = f"No trips in last {days_since} days. Previously had {t30} trips in last 30d."
        return _result(stage, reason, evidence)

    # DECLINING
    if trend == "declining" and t30 > 0:
        stage = "DECLINING"
        reason = f"Activity declining: {t7} trips last 7d vs {t30} trips last 30d."
        return _result(stage, reason, evidence)

    # ACTIVE_LOW (trips in 30d but 0 in 7d, within 7 days)
    if t30 > 0 and t7 == 0 and days_since is not None and days_since <= 7:
        stage = "ACTIVE_LOW"
        reason = f"{t30} trips in last 30d, but 0 in last 7d. May be returning."
        return _result(stage, reason, evidence)

    # ACTIVE
    if t7 > 0 and days_since is not None and days_since <= 7:
        stage = "ACTIVE"
        reason = f"Active: {t7} trips in last 7d, last trip {days_since} day(s) ago."
        return _result(stage, reason, evidence)

    # ACTIVE (fallback: any activity in 30d with recent enough last trip)
    if t30 > 0 and days_since is not None and days_since <= 7:
        stage = "ACTIVE"
        reason = f"Active: {t30} trips in last 30d."
        return _result(stage, reason, evidence)

    # Catch-all
    stage = "NO_ACTIVITY_DATA"
    reason = f"Unclassified: t7={t7}, t30={t30}, days_since={days_since}, trend={trend}"
    return _result(stage, reason, evidence)


def classify_lifecycle_from_identity(driver_id: str, identity: dict[str, Any]) -> dict[str, Any]:
    """
    Full lifecycle classification for a driver: compute activity → classify lifecycle.
    """
    activity = compute_driver_activity(driver_id)

    lifecycle = classify_lifecycle({
        **activity,
        "first_trip_at": identity.get("first_trip_at"),
    })

    lifecycle["driver_id"] = driver_id
    lifecycle["driver_name"] = identity.get("driver_name")
    lifecycle["phone"] = identity.get("phone")
    lifecycle["country"] = identity.get("country")
    lifecycle["city"] = identity.get("city")
    lifecycle["park_id"] = identity.get("park_id")
    lifecycle["park_name"] = identity.get("park_name")
    lifecycle["latest_trip_at"] = activity.get("latest_trip_at")
    lifecycle["trips_7d"] = activity.get("trips_7d", 0)
    lifecycle["trips_14d"] = activity.get("trips_14d", 0)
    lifecycle["trips_30d"] = activity.get("trips_30d", 0)
    lifecycle["days_since_last_trip"] = activity.get("days_since_last_trip")
    lifecycle["activity_trend"] = activity.get("activity_trend", "unknown")

    return lifecycle


def compute_lifecycle_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Aggregate lifecycle distribution with quality metadata.
    Uses batch query against driver_daily_activity_fact for efficiency.
    """
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    result = {
        "status": "ok",
        "summary": [],
        "quality": {
            "identity_coverage": None,
            "phone_coverage": None,
            "activity_coverage": None,
            "freshness_status": "unknown",
        },
        "warnings": [],
        "blocking_gaps": [],
    }

    params = {}
    conditions = []
    if country:
        conditions.append("(dp.country = %(country)s OR prk.country = %(country)s)")
        params["country"] = country
    if city:
        conditions.append("(dp.city = %(city)s OR prk.city = %(city)s)")
        params["city"] = city
    if park_id:
        conditions.append("d.park_id = %(park_id)s")
        params["park_id"] = park_id

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    try:
        with get_db() as conn:
            c = conn.cursor(cursor_factory=RealDictCursor)
            c.execute("SET LOCAL statement_timeout = %s", ("20000",))

            identity_sql = f"""
            SELECT
                COUNT(*) AS total_drivers,
                COUNT(dd.driver_phone) FILTER (WHERE dd.driver_phone IS NOT NULL) AS with_phone,
                COUNT(*) FILTER (WHERE vr.driver_name IS NOT NULL) AS with_name
            FROM public.drivers d
            LEFT JOIN ops.v_dim_driver_resolved vr ON d.driver_id = vr.driver_id
            LEFT JOIN public.drivers_data dd ON d.driver_id = dd.driver_id
            LEFT JOIN dim.dim_park dp ON d.park_id = dp.park_id
            LEFT JOIN ops.v_dim_park_resolved prk ON d.park_id = prk.park_id
            WHERE {where_clause}
            """
            c.execute(identity_sql, params)
            ident = c.fetchone() or {}
            total = int(ident.get("total_drivers", 0) or 0)
            with_phone = int(ident.get("with_phone", 0) or 0)
            with_name = int(ident.get("with_name", 0) or 0)

            result["quality"]["identity_coverage"] = round(with_name / total * 100, 1) if total > 0 else 0
            result["quality"]["phone_coverage"] = round(with_phone / total * 100, 1) if total > 0 else 0

            ref = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            s30 = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
            s60 = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")

            activity_sql = f"""
            SELECT
                d.driver_id,
                COALESCE(SUM(CASE WHEN adf.activity_date >= %(s30)s AND adf.activity_date <= %(ref)s
                    THEN COALESCE(adf.trips, adf.completed_trips, 0) END), 0) AS trips_30d,
                COALESCE(SUM(CASE WHEN adf.activity_date >= %(s7)s AND adf.activity_date <= %(ref)s
                    THEN COALESCE(adf.trips, adf.completed_trips, 0) END), 0) AS trips_7d,
                MAX(adf.activity_date) AS latest_activity,
                COUNT(DISTINCT CASE WHEN adf.activity_date < %(s60)s THEN adf.activity_date END) AS had_prior_activity,
                CASE WHEN lb.activation_ts IS NULL THEN false ELSE true END AS has_first_trip
            FROM public.drivers d
            LEFT JOIN ops.driver_daily_activity_fact adf ON d.driver_id = adf.driver_id
            LEFT JOIN ops.mv_driver_lifecycle_base lb ON d.driver_id = lb.driver_key
            LEFT JOIN dim.dim_park dp ON d.park_id = dp.park_id
            LEFT JOIN ops.v_dim_park_resolved prk ON d.park_id = prk.park_id
            WHERE {where_clause}
            GROUP BY d.driver_id, lb.activation_ts
            """
            params.update({
                "ref": ref,
                "s7": (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d"),
                "s30": s30,
                "s60": s60,
            })
            c.execute(activity_sql, params)
            rows = c.fetchall() or []

            from collections import Counter
            stage_counts = Counter()
            phone_counts = Counter()
            avg_trips = {}
            total_with_activity = 0

            for row in rows:
                t7 = int(row.get("trips_7d", 0) or 0)
                t30 = int(row.get("trips_30d", 0) or 0)
                latest = row.get("latest_activity")
                has_first = row.get("has_first_trip", False)
                driver_id_val = row.get("driver_id")

                days_since = None
                if latest is not None:
                    if isinstance(latest, datetime):
                        days_since = (datetime.now(timezone.utc) - latest.replace(tzinfo=timezone.utc)).days
                    else:
                        try:
                            dt = datetime.fromisoformat(str(latest)[:10])
                            days_since = (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).days
                        except Exception:
                            pass

                stage = _classify_bulk(t7, t30, days_since, has_first)
                stage_counts[stage] += 1

                if driver_id_val:
                    phone_counts[stage] += 0

                if t30 > 0:
                    key = stage
                    if key not in avg_trips:
                        avg_trips[key] = {"sum": 0, "count": 0}
                    avg_trips[key]["sum"] += t30
                    avg_trips[key]["count"] += 1
                    total_with_activity += 1

            result["quality"]["activity_coverage"] = round(total_with_activity / total * 100, 1) if total > 0 else 0
            result["quality"]["freshness_status"] = "ok" if total > 0 else "unknown"

            STAGE_ORDER = [
                "ACTIVE", "ACTIVE_LOW", "DECLINING", "AT_RISK",
                "REGISTERED_NO_TRIPS", "REACTIVATED",
                "CHURNED_RECENT", "CHURNED_LONG", "NO_ACTIVITY_DATA",
            ]

            for stage in STAGE_ORDER:
                count = stage_counts.get(stage, 0)
                if count == 0:
                    continue
                avg = 0
                if stage in avg_trips and avg_trips[stage]["count"] > 0:
                    avg = round(avg_trips[stage]["sum"] / avg_trips[stage]["count"], 1)
                result["summary"].append({
                    "lifecycle_stage": stage,
                    "drivers_count": count,
                    "with_phone_count": 0,
                    "without_phone_count": count,
                    "avg_trips_30d": avg,
                })

            if result["quality"]["phone_coverage"] < 50:
                result["warnings"].append({
                    "type": "low_phone_coverage",
                    "message": f"Phone coverage is {result['quality']['phone_coverage']}%. Contactability limited.",
                    "remediation": "Integrate public.drivers_data.phone into serving fact.",
                })

            if result["quality"]["activity_coverage"] < 30:
                result["blocking_gaps"].append({
                    "type": "low_activity_coverage",
                    "message": f"Only {result['quality']['activity_coverage']}% of drivers have activity data.",
                    "remediation": "Verify ops.driver_daily_activity_fact refresh pipeline.",
                })

    except Exception as e:
        logger.warning("lifecycle_summary failed: %s", e)
        result["status"] = "blocked"
        result["blocking_gaps"].append({"type": "query_failure", "message": str(e)})

    return result


def _classify_bulk(t7: int, t30: int, days_since: Optional[int], has_first_trip: bool) -> str:
    """Lightweight classification for bulk summary queries."""
    if t30 == 0 and t7 == 0 and days_since is None:
        if not has_first_trip:
            return "REGISTERED_NO_TRIPS"
        return "NO_ACTIVITY_DATA"
    if t30 == 0 and t7 == 0 and not has_first_trip:
        return "REGISTERED_NO_TRIPS"
    if days_since is not None and days_since > 60:
        return "CHURNED_LONG"
    if days_since is not None and days_since > 21:
        return "CHURNED_RECENT"
    if days_since is not None and days_since >= 8 and days_since <= 21:
        return "AT_RISK"
    if t30 > 0 and t7 == 0 and days_since is not None and days_since <= 7:
        return "ACTIVE_LOW"
    if t7 > 0 and days_since is not None and days_since <= 7:
        return "ACTIVE"
    if t30 > 0 and days_since is not None and days_since <= 7:
        return "ACTIVE"
    if t30 == 0 and t7 == 0:
        return "NO_ACTIVITY_DATA"
    return "NO_ACTIVITY_DATA"


def _was_churned(activity_data: dict[str, Any]) -> bool:
    """Check if driver was previously churned (>21 days inactive) before recent activity."""
    days_since = activity_data.get("days_since_last_trip")
    if days_since is not None and days_since <= 7:
        return False
    prev_7d = activity_data.get("trips_prev_7d", 0) or 0
    prev_30d = activity_data.get("trips_prev_30d", 0) or 0
    return prev_7d == 0 and prev_30d == 0


def _result(stage: str, reason: str, evidence: dict) -> dict:
    return {
        "lifecycle_stage": stage,
        "lifecycle_reason": reason,
        "evidence": evidence,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "data_quality_status": "ok",
    }


# Import at bottom to avoid circular import
from datetime import timedelta


# ═══════════════════════════════════════════════════════════════════════════════
# Stubs: funciones legacy de consulta (pendientes de migrar a nuevo servicio)
# La lógica real se movió a driver_lifecycle_*_service.py / router separados.
# Estos stubs evitan que el router falle en startup.
# ═══════════════════════════════════════════════════════════════════════════════

def get_weekly(from_date=None, to_date=None, park_id=None):
    return {"data": [], "total": 0}

def get_monthly(from_date=None, to_date=None, park_id=None):
    return {"data": [], "total": 0}

def get_drilldown(period_type="week", period_start=None, metric="activations", park_id=None, page=1, page_size=20):
    return {"data": [], "total": 0, "page": page, "page_size": page_size}

def get_parks_summary(from_date=None, to_date=None, period_type="week"):
    return {"data": [], "total": 0}

def get_series(from_date=None, to_date=None, grain="weekly", park_id=None):
    return {"data": [], "total": 0}

def get_summary(from_date=None, to_date=None, grain="weekly", park_id=None):
    return {"data": [], "total": 0}

def get_cohorts(from_cohort_week=None, to_cohort_week=None, park_id=None):
    return {"data": [], "total": 0}

def get_cohort_drilldown(cohort_week=None, horizon="base", park_id=None, page=1, page_size=20):
    return {"data": [], "total": 0, "page": page, "page_size": page_size}

def get_base_metrics(from_date=None, to_date=None, park_id=None):
    return {"data": [], "total": 0}

def get_base_metrics_drilldown(from_date=None, to_date=None, park_id=None, metric="time_to_first_trip", page=1, page_size=20):
    return {"data": [], "total": 0, "page": page, "page_size": page_size}

def get_parks_for_selector():
    return []

def get_pro_churn_segments(week_start=None, segment=None, park_id=None, limit=1000):
    return []

def get_pro_park_shock_list(week_start=None, limit=1000):
    return []

def get_pro_behavior_shifts(week_start=None, shift=None, park_id=None, limit=1000):
    return []

def get_pro_drivers_at_risk(week_start=None, park_id=None, limit=1000):
    return []
