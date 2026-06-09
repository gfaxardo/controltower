"""
YEGO Lima Growth — Intraday Signal Builder Service (LG-INFRA-R1.3)

Observes live driver activity post-action without altering the base list.
Non-causal observation layer. Uses language "observed after action" — NOT "caused by action".

Rules:
- Idempotent per driver/date/action (upsert)
- Does NOT change queue base
- Does NOT change prioritization
- Does NOT assert attribution
- Does NOT calculate ROI
- Source: YANGO_API_LIVE (raw_yango.orders_raw)
"""
from __future__ import annotations

import json
import logging
from datetime import date as DateType, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_SIGNAL = "growth.yego_lima_intraday_driver_signal"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"
TABLE_ORDERS = "growth.yango_lima_orders_raw"


def _now():
    return datetime.now(timezone.utc)


SIGNAL_BUILD_LOCK_ID = 9002
SIGNAL_COOLDOWN_MINUTES = 4


def _should_skip_signal_build(action_date: str) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT MAX(observed_at) FROM %s WHERE signal_date = %%s" % TABLE_SIGNAL,
            [action_date]
        )
        last = cur.fetchone()[0]
        if last:
            age_s = (datetime.now(timezone.utc) - last).total_seconds()
            return age_s < (SIGNAL_COOLDOWN_MINUTES * 60)


def build_intraday_signals(action_date: str) -> Dict[str, Any]:
    """
    Build intraday signals for all drivers actioned on action_date.
    Fetches active actions from assignment_queue, checks live Yango activity,
    and upserts signals. Idempotent.

    LG-CF-HOTFIX-1B: Cooldown check skips rebuild if signals were
    updated < SIGNAL_COOLDOWN_MINUTES ago. Prevents overlap.
    """
    result = {
        "action_date": action_date,
        "signal_count": 0,
        "new_signals": 0,
        "updated_signals": 0,
        "errors": [],
    }

    if _should_skip_signal_build(action_date):
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM %s WHERE signal_date = %%s" % TABLE_SIGNAL,
                [action_date]
            )
            count = cur.fetchone()[0]
        result["signal_count"] = count
        result["message"] = "Signal build skipped (cooldown: built < %d min ago)" % SIGNAL_COOLDOWN_MINUTES
        result["success"] = True
        return result

    try:
        active_actions = fetch_active_actions(action_date)
        if not active_actions:
            result["message"] = f"No active actions found for {action_date}"
            return result

        result["actions_processed"] = len(active_actions)

        driver_ids = list({a["driver_id"] for a in active_actions if a.get("driver_id")})
        if not driver_ids:
            result["message"] = "No valid driver IDs in active actions"
            return result

        live_activity = fetch_live_yango_activity(driver_ids, action_date)
        result["drivers_with_activity"] = live_activity.get("drivers_with_activity", 0)

        for action in active_actions:
            try:
                driver_id = action.get("driver_id")
                if not driver_id:
                    continue
                signal = compute_signal_for_driver(action, live_activity)
                upsert_signals([signal])
                result["signal_count"] += 1
                if signal.get("_is_new"):
                    result["new_signals"] += 1
                else:
                    result["updated_signals"] += 1
            except Exception as e:
                result["errors"].append({
                    "driver_id": action.get("driver_id"),
                    "error": str(e)[:200],
                })

        result["success"] = True
    except Exception as e:
        result["success"] = False
        result["error"] = str(e)[:300]

    return result


def fetch_active_actions(action_date: str) -> List[Dict[str, Any]]:
    """
    Fetch drivers that were actioned (exported or ready) on action_date.
    Returns list of actions with driver_id, queue_id, campaign_id, channel, sent_at.
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                id AS queue_id,
                driver_id,
                assignment_date AS action_date,
                campaign_id_external,
                assigned_channel AS action_channel,
                exported_at AS action_sent_at,
                program_code,
                program_name,
                queue_status
            FROM {TABLE_QUEUE}
            WHERE assignment_date = %(d)s
              AND queue_status IN ('EXPORTED', 'READY')
              AND driver_id IS NOT NULL
            ORDER BY priority_rank NULLS LAST
            """,
            {"d": action_date}
        )
        rows = cur.fetchall()
        return [
            {
                "queue_id": r[0],
                "driver_id": r[1],
                "action_date": str(r[2]) if r[2] else None,
                "campaign_id_external": r[3],
                "action_channel": r[4],
                "action_sent_at": r[5].isoformat() if r[5] else None,
                "program_code": r[6],
                "program_name": r[7],
                "queue_status": r[8],
            }
            for r in rows
        ]


def fetch_live_yango_activity(driver_ids: List[str], action_date: str) -> Dict[str, Any]:
    """
    Fetch live activity from raw_yango orders for a set of drivers on action_date.
    Returns per-driver activity map: trips today, first trip at, last activity at.
    """
    if not driver_ids:
        return {"drivers_with_activity": 0, "activity_map": {}}

    with get_db() as conn:
        cur = conn.cursor()

        try:
            cur.execute(
                f"""
                SELECT
                    driver_profile_id,
                    COUNT(*) AS trips_today,
                    MIN(ended_at) AS first_trip_at,
                    MAX(ended_at) AS last_trip_at
                FROM {TABLE_ORDERS}
                WHERE driver_profile_id = ANY(%(ids)s)
                  AND ended_at::date = %(d)s::date
                  AND status = 'complete'
                GROUP BY driver_profile_id
                """,
                {"ids": driver_ids, "d": action_date}
            )
            rows = cur.fetchall()
        except Exception:
            cur.execute(
                f"""
                SELECT
                    driver_profile_id,
                    COUNT(*) AS trips_today,
                    MIN(ended_at) AS first_trip_at,
                    MAX(ended_at) AS last_trip_at
                FROM {TABLE_ORDERS}
                WHERE driver_profile_id IN %(ids)s
                  AND ended_at::date = %(d)s::date
                  AND status = 'complete'
                GROUP BY driver_profile_id
                """,
                {"ids": tuple(driver_ids), "d": action_date}
            )
            rows = cur.fetchall()

    activity_map = {}
    drivers_with_activity = 0

    for r in rows:
        did = r[0]
        trips = int(r[1]) if r[1] else 0
        first_at = r[2]
        last_at = r[3]

        activity_map[did] = {
            "trips_today": trips,
            "first_trip_at": first_at.isoformat() if first_at else None,
            "last_trip_at": last_at.isoformat() if last_at else None,
        }
        if trips > 0:
            drivers_with_activity += 1

    return {
        "drivers_with_activity": drivers_with_activity,
        "activity_map": activity_map,
    }


def compute_signal_for_driver(
    action: Dict[str, Any],
    live_activity: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compute signal for a single driver given their action record and live activity data.
    Returns a signal dict ready for upsert. Non-causal language throughout.
    """
    driver_id = action.get("driver_id")
    action_date = action.get("action_date")
    action_sent_at = action.get("action_sent_at")

    activity_map = live_activity.get("activity_map", {})
    driver_activity = activity_map.get(driver_id, {})

    trips_after = driver_activity.get("trips_today", 0)
    first_trip_at = driver_activity.get("first_trip_at")
    has_activity = trips_after > 0

    signal_status = "ACTIONED_NO_ACTIVITY"
    reactivation = False

    if has_activity:
        if action_sent_at and first_trip_at:
            if first_trip_at > action_sent_at:
                signal_status = "TRIP_DETECTED"
            else:
                signal_status = "OBSERVED"
        else:
            signal_status = "TRIP_DETECTED"

    if trips_after >= 1:
        reactivation = True
        signal_status = "REACTIVATED"

    observed_at = _now()

    evidence = {
        "action": {
            "queue_status": action.get("queue_status"),
            "program_code": action.get("program_code"),
            "action_channel": action.get("action_channel"),
            "action_sent_at": action_sent_at,
        },
        "activity": {
            "trips_today_after_action": trips_after,
            "first_trip_at": first_trip_at,
            "driver_had_activity": has_activity,
        },
        "computed_at": observed_at.isoformat(),
    }

    signal = {
        "signal_id": str(uuid4()),
        "signal_date": action_date,
        "driver_profile_id": driver_id,
        "action_date": action_date,
        "queue_id": action.get("queue_id"),
        "campaign_id_external": action.get("campaign_id_external"),
        "action_channel": action.get("action_channel"),
        "action_sent_at": action_sent_at,
        "observed_at": observed_at.isoformat(),
        "source_system": "YANGO_API_LIVE",
        "source_loaded_at": observed_at.isoformat(),
        "trips_after_action": trips_after,
        "supply_hours_after_action": 0,
        "first_trip_after_action_at": first_trip_at,
        "first_supply_after_action_at": None,
        "reactivation_detected": reactivation,
        "activity_detected_today": has_activity,
        "signal_status": signal_status,
        "evidence_json": json.dumps(evidence, default=str),
        "_is_new": True,
    }

    return signal


def upsert_signals(signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Upsert signals into the intraday driver signal table.
    Batch upsert: single round-trip using ON CONFLICT.

    LG-CF-HOTFIX-1B: Replaced per-driver loop with batch INSERT ON CONFLICT.
    Reduces 620 queries to 1 per build call.
    """
    if not signals:
        return {"inserted": 0, "updated": 0, "total": 0}

    inserted = 0
    updated = 0

    with get_db() as conn:
        cur = conn.cursor()

        existing_ids = set()
        if signals:
            qids = [s["queue_id"] for s in signals if s.get("queue_id")]
            if qids:
                cur.execute(
                    "SELECT queue_id FROM %s WHERE signal_date = %%s AND queue_id = ANY(%%s)" % TABLE_SIGNAL,
                    [signals[0]["signal_date"], qids]
                )
                existing_ids = {r[0] for r in cur.fetchall()}
                updated = len(existing_ids)

        for s in signals:
            cur.execute(
                "INSERT INTO %s "
                "(signal_id, signal_date, driver_profile_id, action_date, queue_id, "
                " campaign_id_external, action_channel, action_sent_at, observed_at, "
                " source_system, source_loaded_at, trips_after_action, "
                " supply_hours_after_action, first_trip_after_action_at, "
                " first_supply_after_action_at, reactivation_detected, "
                " activity_detected_today, signal_status, evidence_json) "
                "VALUES (%%s, %%s, %%s, %%s, %%s, "
                " %%s, %%s, %%s, %%s, "
                " %%s, %%s, %%s, "
                " %%s, %%s, "
                " %%s, %%s, "
                " %%s, %%s, %%s::jsonb) "
                "ON CONFLICT (signal_date, driver_profile_id, queue_id) DO UPDATE SET "
                " observed_at = EXCLUDED.observed_at, "
                " trips_after_action = EXCLUDED.trips_after_action, "
                " supply_hours_after_action = EXCLUDED.supply_hours_after_action, "
                " first_trip_after_action_at = EXCLUDED.first_trip_after_action_at, "
                " first_supply_after_action_at = EXCLUDED.first_supply_after_action_at, "
                " reactivation_detected = EXCLUDED.reactivation_detected, "
                " activity_detected_today = EXCLUDED.activity_detected_today, "
                " signal_status = EXCLUDED.signal_status, "
                " evidence_json = EXCLUDED.evidence_json, "
                " source_loaded_at = EXCLUDED.source_loaded_at, "
                " updated_at = now()" % TABLE_SIGNAL,
                (
                    s["signal_id"], s["signal_date"], s["driver_profile_id"],
                    s["action_date"], s["queue_id"],
                    s.get("campaign_id_external"), s.get("action_channel"),
                    s.get("action_sent_at"), s["observed_at"],
                    s["source_system"], s["source_loaded_at"], s["trips_after_action"],
                    s["supply_hours_after_action"], s["first_trip_after_action_at"],
                    s["first_supply_after_action_at"], s["reactivation_detected"],
                    s["activity_detected_today"], s["signal_status"], s["evidence_json"],
                )
            )
            if s.get("queue_id") in existing_ids:
                s["_is_new"] = False
            else:
                s["_is_new"] = True
                inserted += 1

        conn.commit()

    return {"inserted": inserted, "updated": updated, "total": inserted + updated}


def get_signal_summary(action_date: str) -> Dict[str, Any]:
    """
    Get summary of intraday signals for a date.
    Returns counts by status, activity buckets, and freshness info.
    """
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_QUEUE} "
            f"WHERE assignment_date = %(d)s "
            f"AND queue_status IN ('EXPORTED', 'READY')",
            {"d": action_date}
        )
        total_actions = cur.fetchone()[0] or 0

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_SIGNAL} WHERE signal_date = %(d)s",
            {"d": action_date}
        )
        total_signals = cur.fetchone()[0] or 0

        cur.execute(
            f"""
            SELECT signal_status, COUNT(*) AS cnt
            FROM {TABLE_SIGNAL}
            WHERE signal_date = %(d)s
            GROUP BY signal_status
            ORDER BY cnt DESC
            """,
            {"d": action_date}
        )
        status_counts = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_SIGNAL} "
            f"WHERE signal_date = %(d)s AND trips_after_action > 0",
            {"d": action_date}
        )
        drivers_with_trips = cur.fetchone()[0] or 0

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_SIGNAL} "
            f"WHERE signal_date = %(d)s AND activity_detected_today = true",
            {"d": action_date}
        )
        drivers_with_activity = cur.fetchone()[0] or 0

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_SIGNAL} "
            f"WHERE signal_date = %(d)s AND reactivation_detected = true",
            {"d": action_date}
        )
        drivers_reactivated = cur.fetchone()[0] or 0

        cur.execute(
            f"SELECT MAX(observed_at) FROM {TABLE_SIGNAL} WHERE signal_date = %(d)s",
            {"d": action_date}
        )
        last_updated = cur.fetchone()[0]

    return {
        "signal_date": action_date,
        "monitored_actions": total_actions,
        "total_signals": total_signals,
        "signals_by_status": status_counts,
        "drivers_with_trips_after_action": drivers_with_trips,
        "drivers_with_activity_detected": drivers_with_activity,
        "drivers_reactivated_observed": drivers_reactivated,
        "last_updated_at": last_updated.isoformat() if last_updated else None,
        "source_system": "YANGO_API_LIVE",
        "disclaimer": "observed after action, not causal attribution",
    }


def get_signals_by_campaign(action_date: str) -> List[Dict[str, Any]]:
    """
    Get signal summary grouped by campaign for a date.
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                COALESCE(campaign_id_external, 'UNKNOWN') AS campaign,
                COUNT(*) AS total_signals,
                SUM(CASE WHEN trips_after_action > 0 THEN 1 ELSE 0 END) AS with_trips,
                SUM(CASE WHEN reactivation_detected THEN 1 ELSE 0 END) AS reactivated,
                MAX(observed_at) AS last_updated
            FROM {TABLE_SIGNAL}
            WHERE signal_date = %(d)s
            GROUP BY campaign_id_external
            ORDER BY total_signals DESC
            """,
            {"d": action_date}
        )
        rows = cur.fetchall()
        return [
            {
                "campaign_id": r[0],
                "total_signals": r[1],
                "drivers_with_trips": r[2],
                "drivers_reactivated": r[3],
                "last_updated": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ]


def get_signals_by_program(action_date: str) -> List[Dict[str, Any]]:
    """
    Get signal summary grouped by program for a date.
    Joins back to assignment_queue for program_code.
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
                COALESCE(aq.program_code, 'UNKNOWN') AS program_code,
                COALESCE(aq.program_name, 'Unknown Program') AS program_name,
                COUNT(*) AS total_signals,
                SUM(CASE WHEN s.trips_after_action > 0 THEN 1 ELSE 0 END) AS with_trips,
                SUM(CASE WHEN s.reactivation_detected THEN 1 ELSE 0 END) AS reactivated
            FROM {TABLE_SIGNAL} s
            LEFT JOIN {TABLE_QUEUE} aq ON s.queue_id = aq.id
            WHERE s.signal_date = %(d)s
            GROUP BY aq.program_code, aq.program_name
            ORDER BY total_signals DESC
            """,
            {"d": action_date}
        )
        rows = cur.fetchall()
        return [
            {
                "program_code": r[0],
                "program_name": r[1],
                "total_signals": r[2],
                "drivers_with_trips": r[3],
                "drivers_reactivated": r[4],
            }
            for r in rows
        ]


def get_signals_list(
    action_date: str,
    limit: int = 100,
    offset: int = 0,
    signal_status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get paginated list of individual signals for a date.
    Optional filter by signal_status.
    """
    with get_db() as conn:
        cur = conn.cursor()

        where = "WHERE signal_date = %(d)s"
        params: Dict[str, Any] = {"d": action_date, "lim": limit, "off": offset}

        if signal_status:
            where += " AND signal_status = %(st)s"
            params["st"] = signal_status

        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_SIGNAL} {where}",
            params
        )
        total = cur.fetchone()[0] or 0

        cur.execute(
            f"""
            SELECT
                signal_id, signal_date, driver_profile_id, action_date,
                queue_id, campaign_id_external, action_channel, action_sent_at,
                observed_at, source_system, trips_after_action,
                supply_hours_after_action, first_trip_after_action_at,
                first_supply_after_action_at, reactivation_detected,
                activity_detected_today, signal_status, evidence_json
            FROM {TABLE_SIGNAL}
            {where}
            ORDER BY observed_at DESC
            LIMIT %(lim)s OFFSET %(off)s
            """,
            params
        )
        rows = cur.fetchall()
        signals = []
        for r in rows:
            signals.append({
                "signal_id": str(r[0]),
                "signal_date": str(r[1]),
                "driver_profile_id": r[2],
                "action_date": str(r[3]) if r[3] else None,
                "queue_id": str(r[4]) if r[4] else None,
                "campaign_id_external": r[5],
                "action_channel": r[6],
                "action_sent_at": r[7].isoformat() if r[7] else None,
                "observed_at": r[8].isoformat() if r[8] else None,
                "source_system": r[9],
                "trips_after_action": r[10] or 0,
                "supply_hours_after_action": float(r[11]) if r[11] else 0,
                "first_trip_after_action_at": r[12].isoformat() if r[12] else None,
                "first_supply_after_action_at": r[13].isoformat() if r[13] else None,
                "reactivation_detected": r[14] or False,
                "activity_detected_today": r[15] or False,
                "signal_status": r[16],
                "evidence_json": r[17] if isinstance(r[17], dict) else None,
            })

    return {
        "signal_date": action_date,
        "total": total,
        "limit": limit,
        "offset": offset,
        "signals": signals,
    }
