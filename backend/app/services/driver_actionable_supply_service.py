"""
Driver Actionable Supply Service — FASE D4
Control Foundation: Actionable Supply Engine

Bridges identity + activity + lifecycle into deterministic operational queues.

5 Queue Types (P0):
  REGISTERED_NO_FIRST_TRIP  → drivers without first trip
  DECLINING_DRIVERS         → drivers with declining activity
  AT_RISK_DRIVERS           → drivers at risk of churn
  CHURNED_RECENT            → recently churned drivers (recoverable)
  HIGH_POTENTIAL_UNDERUTILIZED → active high-performers with recent decline

Priority Engine (deterministic):
  CRITICAL → AT_RISK with phone and severe decline
  HIGH     → DECLINING severe, REGISTERED recent, AT_RISK
  MEDIUM   → CHURNED_RECENT with phone, UNDERUTILIZED with phone
  LOW      → no phone, low confidence, stale data

Rules:
  - No phone → priority drops one level
  - Stale data → priority drops, marked warning
  - Identity confidence low → priority drops
  - Every entry has action_reason + evidence + recommended_action
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 30000

QUEUE_TYPES = [
    "REGISTERED_NO_FIRST_TRIP",
    "DECLINING_DRIVERS",
    "AT_RISK_DRIVERS",
    "CHURNED_RECENT",
    "HIGH_POTENTIAL_UNDERUTILIZED",
]

PRIORITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

QUEUE_META = {
    "REGISTERED_NO_FIRST_TRIP": {
        "label": "Registered — No First Trip",
        "objective": "activate",
        "recommended_action": "Contactar y asistir activación del primer viaje.",
        "target_lifecycle": "REGISTERED_NO_TRIPS",
    },
    "DECLINING_DRIVERS": {
        "label": "Declining Drivers",
        "objective": "retention",
        "recommended_action": "Revisar caída operativa reciente. Contactar para retención preventiva.",
        "target_lifecycle": "DECLINING",
    },
    "AT_RISK_DRIVERS": {
        "label": "At-Risk Drivers",
        "objective": "early_recovery",
        "recommended_action": "Contactar antes de churn. Última actividad entre 8-21 días.",
        "target_lifecycle": "AT_RISK",
    },
    "CHURNED_RECENT": {
        "label": "Recently Churned",
        "objective": "reactivation",
        "recommended_action": "Intentar reactivación. Churn reciente (22-60 días). Evaluar incentivo.",
        "target_lifecycle": "CHURNED_RECENT",
    },
    "HIGH_POTENTIAL_UNDERUTILIZED": {
        "label": "High Potential — Underutilized",
        "objective": "supply_growth",
        "recommended_action": "Driver con buen historial pero utilización baja reciente. Contactar para incrementar actividad.",
        "target_lifecycle": "ACTIVE",
    },
}


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET LOCAL statement_timeout = %s", (str(int(timeout_ms)),))
    return c


def _safe_query(cur, sql: str, params: dict = None, default=None):
    try:
        cur.execute(sql, params or {})
        return cur.fetchall() or []
    except Exception as e:
        logger.debug("actionable_supply query failed: %s", e)
        return default if default is not None else []


def _days_since(date_val) -> Optional[int]:
    if not date_val:
        return None
    try:
        if isinstance(date_val, datetime):
            dt = date_val
        else:
            dt = datetime.fromisoformat(str(date_val)[:10])
        return (datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).days
    except Exception:
        return None


def _compute_priority(
    queue_type: str,
    lifecycle_stage: str,
    has_phone: bool,
    days_since: Optional[int],
    trips_7d: int,
    identity_confidence: str,
    data_quality_status: str,
) -> tuple[str, str]:
    """
    Deterministic priority assignment.

    Returns (priority, priority_reason).
    """
    if data_quality_status in ("error", "blocked"):
        return "LOW", "Data quality degraded. Review freshness and sources."
    if identity_confidence == "low":
        return "LOW", "Identity confidence low. Verify driver record."

    phone_penalty = not has_phone

    if queue_type == "AT_RISK_DRIVERS":
        if has_phone and days_since is not None and days_since <= 14:
            return "CRITICAL", "AT_RISK with phone, last activity ≤ 14d. Critical recovery window."
        if has_phone:
            return "HIGH", "AT_RISK with phone. Recoverable."
        return "MEDIUM", "AT_RISK without phone. Limited contactability."

    if queue_type == "DECLINING_DRIVERS":
        if trips_7d == 0:
            if has_phone:
                return "CRITICAL", "DECLINING and stopped completely (0 trips in 7d). Critical retention case."
            return "HIGH", "DECLINING and stopped completely. No phone for contact."
        if has_phone:
            return "HIGH", "DECLINING with phone. Retention window open."
        return "MEDIUM", "DECLINING without phone. Limited retention options."

    if queue_type == "REGISTERED_NO_FIRST_TRIP":
        if has_phone:
            return "HIGH", "New driver without first trip. Has phone — contactable."
        return "MEDIUM", "New driver without first trip. No phone available."

    if queue_type == "CHURNED_RECENT":
        if has_phone and days_since is not None and days_since <= 30:
            return "HIGH", "Very recent churn (≤30d) with phone. High reactivation potential."
        if has_phone:
            return "MEDIUM", "Recent churn (30-60d) with phone. Moderate reactivation potential."
        return "LOW", "Churned without phone. Low contactability."

    if queue_type == "HIGH_POTENTIAL_UNDERUTILIZED":
        if has_phone and trips_7d < 5:
            return "HIGH", "High potential driver severely underutilized (<5 trips/7d). Has phone."
        if has_phone:
            return "MEDIUM", "High potential driver underutilized. Has phone."
        return "LOW", "High potential driver underutilized but no phone."

    return "MEDIUM", "Default priority."


def _derive_action_reason(queue_type: str, trips_7d: int, trips_30d: int, days_since: Optional[int]) -> str:
    """Generate deterministic action_reason text."""
    if queue_type == "REGISTERED_NO_FIRST_TRIP":
        return "Driver registrado sin primer viaje completado. Sin actividad operacional registrada."

    if queue_type == "DECLINING_DRIVERS":
        if trips_7d == 0:
            return f"Driver stopped completely. Had {trips_30d} trips in last 30d but 0 in last 7d."
        return f"Activity declining. {trips_7d} trips in last 7d vs higher baseline."

    if queue_type == "AT_RISK_DRIVERS":
        return f"No trips in last {days_since} days. Previously had {trips_30d} trips in last 30d."

    if queue_type == "CHURNED_RECENT":
        return f"Churned {days_since} days ago. Previously had {trips_30d} trips in last 30d before churn."

    if queue_type == "HIGH_POTENTIAL_UNDERUTILIZED":
        return f"Active driver with {trips_30d} trips in 30d but only {trips_7d} in last 7d. Potential underutilization."

    return "Actionable driver requiring operational attention."


def generate_actionable_list(
    queue_type: Optional[str] = None,
    queue_priority: Optional[str] = None,
    lifecycle_stage: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    has_phone: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Generate actionable supply queues from identity + activity + lifecycle data.

    Returns structured response with queues + summary.
    """
    from collections import Counter

    params = {}
    conditions = ["1=1"]

    if country:
        conditions.append("(dp.country = %(country)s OR prk.country = %(country)s)")
        params["country"] = country
    if city:
        conditions.append("(dp.city = %(city)s OR prk.city = %(city)s)")
        params["city"] = city
    if park_id:
        conditions.append("d.park_id = %(park_id)s")
        params["park_id"] = park_id

    where_clause = " AND ".join(conditions)

    ref = datetime.now(timezone.utc)
    s7 = (ref - timedelta(days=7)).strftime("%Y-%m-%d")
    s30 = (ref - timedelta(days=30)).strftime("%Y-%m-%d")
    s60 = (ref - timedelta(days=60)).strftime("%Y-%m-%d")
    ref_str = ref.strftime("%Y-%m-%d")

    base_sql = f"""
    WITH driver_base AS (
        SELECT
            d.driver_id,
            COALESCE(vr.driver_name) AS driver_name,
            COALESCE(dd.driver_phone, d.phone::text) AS phone,
            COALESCE(dp.city, prk.city) AS city,
            COALESCE(dp.country, prk.country) AS country,
            d.park_id,
            COALESCE(dp.park_name, prk.park_name) AS park_name,
            COALESCE(dd.driver_phone IS NOT NULL OR d.phone IS NOT NULL, false) AS has_phone,
            CASE WHEN vr.driver_name IS NOT NULL THEN 'high'
                 WHEN dd.full_name IS NOT NULL THEN 'medium'
                 ELSE 'low' END AS identity_confidence,
            CASE WHEN dd.driver_phone IS NULL AND d.phone IS NULL THEN 'warning'
                 ELSE 'ok' END AS data_quality_status,
            d.created_at AS first_seen_at,
            lb.activation_ts AS first_trip_at
        FROM public.drivers d
        LEFT JOIN ops.v_dim_driver_resolved vr ON d.driver_id = vr.driver_id
        LEFT JOIN public.drivers_data dd ON d.driver_id = dd.driver_id
        LEFT JOIN dim.dim_park dp ON d.park_id = dp.park_id
        LEFT JOIN ops.v_dim_park_resolved prk ON d.park_id = prk.park_id
        LEFT JOIN ops.mv_driver_lifecycle_base lb ON d.driver_id = lb.driver_key
        WHERE {where_clause}
    ),
    driver_activity AS (
        SELECT
            driver_id,
            COALESCE(SUM(CASE WHEN activity_date >= %(s7)s AND activity_date <= %(ref)s
                THEN COALESCE(trips, completed_trips, 0) END), 0) AS trips_7d,
            COALESCE(SUM(CASE WHEN activity_date >= %(s30)s AND activity_date <= %(ref)s
                THEN COALESCE(trips, completed_trips, 0) END), 0) AS trips_30d,
            COALESCE(SUM(CASE WHEN activity_date >= %(s60)s AND activity_date <= %(ref)s
                THEN COALESCE(trips, completed_trips, 0) END), 0) AS trips_60d,
            MAX(activity_date) AS latest_activity
        FROM ops.driver_daily_activity_fact
        WHERE driver_id IN (SELECT driver_id FROM driver_base)
        GROUP BY driver_id
    ),
    driver_enriched AS (
        SELECT
            b.*,
            COALESCE(a.trips_7d, 0) AS trips_7d,
            COALESCE(a.trips_30d, 0) AS trips_30d,
            COALESCE(a.trips_60d, 0) AS trips_60d,
            a.latest_activity AS latest_activity_at
        FROM driver_base b
        LEFT JOIN driver_activity a ON b.driver_id = a.driver_id
    )
    SELECT
        driver_id, driver_name, phone, has_phone,
        city, country, park_id, park_name,
        identity_confidence, data_quality_status,
        first_seen_at, first_trip_at,
        trips_7d, trips_30d, trips_60d,
        latest_activity_at
    FROM driver_enriched
    """

    params.update({"s7": s7, "s30": s30, "s60": s60, "ref": ref_str})

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            rows = _safe_query(cur, base_sql, params)
    except Exception as e:
        logger.error("actionable_supply: base query failed: %s", e)
        return {"status": "blocked", "summary": {}, "queues": [], "warnings": [], "blocking_gaps": [str(e)]}

    queues = []
    priority_counts = Counter()
    queue_counts = Counter()

    for row in rows:
        did = row["driver_id"]
        days_since = _days_since(row.get("latest_activity_at"))
        t7 = int(row.get("trips_7d", 0) or 0)
        t30 = int(row.get("trips_30d", 0) or 0)
        t60 = int(row.get("trips_60d", 0) or 0)
        has_phone_flag = bool(row.get("has_phone", False))
        has_first = row.get("first_trip_at") is not None
        identity_conf = row.get("identity_confidence", "low")
        dq_status = row.get("data_quality_status", "ok")

        # ── Lifecycle classification ──
        lifecycle = "NO_ACTIVITY_DATA"
        if not has_first and t30 == 0 and t7 == 0:
            lifecycle = "REGISTERED_NO_TRIPS"
        elif days_since is not None and days_since > 60:
            lifecycle = "CHURNED_LONG" if t30 == 0 else "CHURNED_RECENT"
        elif days_since is not None and days_since > 21:
            lifecycle = "CHURNED_RECENT"
        elif days_since is not None and days_since >= 8:
            lifecycle = "AT_RISK"
        elif t7 > 0:
            lifecycle = "ACTIVE"
        elif t30 > 0:
            lifecycle = "ACTIVE_LOW"
        else:
            lifecycle = "NO_ACTIVITY_DATA"

        # ── Activity trend ──
        trend = "unknown"
        if t30 == 0 and t7 == 0:
            trend = "inactive"
        elif t7 == 0 and t30 > 0:
            trend = "declining"
        elif t7 > 0:
            trend = "stable"

        # ── Queue assignment ──
        assigned_queues = []

        if lifecycle == "REGISTERED_NO_TRIPS":
            assigned_queues.append("REGISTERED_NO_FIRST_TRIP")

        if lifecycle == "DECLINING" or (lifecycle == "ACTIVE_LOW" and t7 == 0 and t30 > 10):
            assigned_queues.append("DECLINING_DRIVERS")
        elif trend == "declining" and t30 > 0:
            assigned_queues.append("DECLINING_DRIVERS")

        if lifecycle == "AT_RISK":
            assigned_queues.append("AT_RISK_DRIVERS")

        if lifecycle == "CHURNED_RECENT":
            assigned_queues.append("CHURNED_RECENT")

        if lifecycle == "ACTIVE" and t30 > 0 and t7 < (t30 / 4):
            assigned_queues.append("HIGH_POTENTIAL_UNDERUTILIZED")

        for qtype in assigned_queues:
            priority, priority_reason = _compute_priority(
                qtype, lifecycle, has_phone_flag, days_since, t7, identity_conf, dq_status,
            )

            if queue_type and qtype != queue_type:
                continue
            if queue_priority and priority != queue_priority:
                continue
            if lifecycle_stage and lifecycle != lifecycle_stage:
                continue
            if has_phone is not None and has_phone_flag != has_phone:
                continue

            action_reason = _derive_action_reason(qtype, t7, t30, days_since)
            meta = QUEUE_META.get(qtype, {})

            entry = {
                "queue_type": qtype,
                "queue_label": meta.get("label", qtype),
                "queue_priority": priority,
                "priority_reason": priority_reason,
                "driver_id": did,
                "driver_name": (row.get("driver_name") or "").strip() if row.get("driver_name") else None,
                "phone": (row.get("phone") or "").strip() if row.get("phone") else None,
                "has_phone": has_phone_flag,
                "country": row.get("country"),
                "city": row.get("city"),
                "park_id": row.get("park_id"),
                "park_name": row.get("park_name"),
                "lifecycle_stage": lifecycle,
                "activity_trend": trend,
                "trips_7d": t7,
                "trips_30d": t30,
                "days_since_last_trip": days_since,
                "action_reason": action_reason,
                "evidence": {
                    "trips_7d": t7, "trips_30d": t30, "trips_60d": t60,
                    "days_since_last_trip": days_since,
                    "has_first_trip": has_first,
                    "has_phone": has_phone_flag,
                },
                "recommended_action": meta.get("recommended_action", ""),
                "freshness_status": "stale" if dq_status != "ok" else "fresh",
                "data_quality_status": dq_status,
                "identity_confidence": identity_conf,
                "assigned_owner": None,
                "queue_generated_at": datetime.now(timezone.utc).isoformat(),
            }
            queues.append(entry)
            priority_counts[priority] += 1
            queue_counts[qtype] += 1

    # Sort: CRITICAL → HIGH → MEDIUM → LOW
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    queues.sort(key=lambda x: priority_order.get(x["queue_priority"], 4))

    total = len(queues)
    sliced = queues[offset:offset + limit] if limit > 0 else queues

    summary = {
        "total_in_all_queues": total,
        "critical": priority_counts.get("CRITICAL", 0),
        "high": priority_counts.get("HIGH", 0),
        "medium": priority_counts.get("MEDIUM", 0),
        "low": priority_counts.get("LOW", 0),
        "by_queue": {k: queue_counts.get(k, 0) for k in QUEUE_TYPES},
    }

    return {
        "status": "ok",
        "summary": summary,
        "queues": sliced,
        "total": total,
        "limit": limit,
        "offset": offset,
        "warnings": [],
        "blocking_gaps": [],
    }


def generate_actionable_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Aggregate summary of actionable queues with quality metadata.
    """
    full = generate_actionable_list(
        country=country, city=city, park_id=park_id, limit=10000, offset=0,
    )

    queues_data = full.get("queues", [])
    summary = full.get("summary", {})

    with_phone_count = sum(1 for q in queues_data if q.get("has_phone"))
    without_phone_count = len(queues_data) - with_phone_count

    stale_count = sum(1 for q in queues_data if q.get("freshness_status") == "stale")

    quality = {
        "total_actionable": len(queues_data),
        "with_phone": with_phone_count,
        "without_phone": without_phone_count,
        "phone_coverage_pct": round(with_phone_count / len(queues_data) * 100, 1) if queues_data else 0,
        "stale_entries": stale_count,
        "freshness_status": "ok" if stale_count == 0 else "warning",
    }

    warnings_list = []
    if without_phone_count > 0:
        warnings_list.append({
            "type": "phone_gap",
            "message": f"{without_phone_count} actionable drivers without phone. Contactability limited.",
            "count": without_phone_count,
        })
    if stale_count > 0:
        warnings_list.append({
            "type": "stale_data",
            "message": f"{stale_count} entries with stale/unknown data quality.",
            "count": stale_count,
        })

    return {
        "status": "ok" if not warnings_list else "warning",
        "summary": summary,
        "quality": quality,
        "queues_meta": {k: QUEUE_META.get(k, {}) for k in QUEUE_TYPES},
        "warnings": warnings_list,
        "blocking_gaps": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
