"""
YEGO Lima Growth — Impact Tracking Service (IF-1 V1).

Measures whether contacted drivers returned to operate after contact.
Uses driver_360_daily for post-contact activity. Deterministic only.
NO revenue. NO ROI. NO attribution.
"""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_IMPACT = "growth.yego_lima_impact_tracking"
TABLE_RESULT = "growth.yego_lima_loopcontrol_result_sync"
TABLE_DRIVER_360 = "growth.yango_lima_driver_360_daily"
TABLE_STATE = "growth.yango_lima_driver_state_snapshot"

MIN_POST_WINDOW_DAYS = 1
DEFAULT_POST_WINDOW_DAYS = 7


def rebuild_impact_tracking(
    date_str: str,
    contact_status_filter: Optional[str] = None,
    post_window_days: int = DEFAULT_POST_WINDOW_DAYS,
) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        conditions = ["last_call_at::date = %(d)s"]
        params: Dict[str, Any] = {"d": date_str}

        if contact_status_filter:
            conditions.append("status = %(st)s")
            params["st"] = contact_status_filter

        where = " AND ".join(conditions)

        cur.execute(
            f"""
            SELECT id, driver_id, assignment_queue_id, campaign_id_external,
                   status, disposition, last_call_at, phone
            FROM {TABLE_RESULT}
            WHERE {where}
              AND driver_id IS NOT NULL
            ORDER BY last_call_at ASC
        """,
            params,
        )
        results = [dict(r) for r in cur.fetchall()]

    if not results:
        return {
            "date": date_str,
            "total_processed": 0,
            "returned": 0,
            "not_returned": 0,
            "pending_window": 0,
            "not_contacted": 0,
        }

    processed = 0
    returned = 0
    not_returned = 0
    pending_window = 0
    not_contacted = 0

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        for r in results:
            result_id = r["id"]
            driver_id = r["driver_id"]
            contact_status = r["status"]
            contact_date = r["last_call_at"]
            aq_id = r.get("assignment_queue_id")
            campaign_id = r.get("campaign_id_external")
            disposition = r.get("disposition")

            if contact_status != "CONTACTED":
                _upsert_impact(cur, driver_id, aq_id, campaign_id, contact_status,
                               disposition, contact_date, 0, None, 0, None,
                               "NOT_CONTACTED")
                not_contacted += 1
                processed += 1
                continue

            if not contact_date:
                _upsert_impact(cur, driver_id, aq_id, campaign_id, contact_status,
                               disposition, None, 0, None, 0, None,
                               "PENDING_WINDOW")
                pending_window += 1
                processed += 1
                continue

            cd = contact_date.date() if hasattr(contact_date, 'date') else contact_date
            if isinstance(cd, str):
                cd = datetime.fromisoformat(cd.replace('Z', '+00:00')).date()

            end_date = cd + timedelta(days=post_window_days)
            today = date_type.today()

            baseline_trips, baseline_last_trip = _get_baseline_metrics(cur, driver_id, cd)
            post_trips, post_last_trip = _get_post_contact_metrics(cur, driver_id, cd, end_date)

            if today < cd + timedelta(days=MIN_POST_WINDOW_DAYS):
                impact = "PENDING_WINDOW"
                pending_window += 1
            elif post_trips > 0:
                impact = "RETURNED"
                returned += 1
            else:
                impact = "NOT_RETURNED"
                not_returned += 1

            _upsert_impact(cur, driver_id, aq_id, campaign_id, contact_status,
                           disposition, cd.isoformat(), baseline_trips, baseline_last_trip,
                           post_trips, post_last_trip, impact)
            processed += 1

        conn.commit()

    return {
        "date": date_str,
        "total_processed": processed,
        "returned": returned,
        "not_returned": not_returned,
        "pending_window": pending_window,
        "not_contacted": not_contacted,
    }


def _get_baseline_metrics(cur, driver_id: str, contact_date: date_type):
    start = contact_date - timedelta(days=7)
    cur.execute(
        f"""
        SELECT COALESCE(SUM(completed_orders), 0) as trips,
               MAX(date) as last_day
        FROM {TABLE_DRIVER_360}
        WHERE driver_profile_id = %(did)s
          AND date >= %(sd)s
          AND date < %(ed)s
    """,
        {"did": driver_id, "sd": start.isoformat(), "ed": contact_date.isoformat()},
    )
    row = cur.fetchone()
    if not row or not row["trips"]:
        return 0, None

    last_trip = None
    if row["last_day"]:
        last_trip = row["last_day"]

    return int(row["trips"]), last_trip


def _get_post_contact_metrics(cur, driver_id: str, contact_date: date_type, end_date: date_type):
    cur.execute(
        f"""
        SELECT COALESCE(SUM(completed_orders), 0) as trips,
               MAX(date) as last_day
        FROM {TABLE_DRIVER_360}
        WHERE driver_profile_id = %(did)s
          AND date > %(sd)s
          AND date <= %(ed)s
    """,
        {"did": driver_id, "sd": contact_date.isoformat(), "ed": end_date.isoformat()},
    )
    row = cur.fetchone()
    if not row or not row["trips"]:
        return 0, None

    last_trip = None
    if row["last_day"]:
        last_trip = row["last_day"]

    return int(row["trips"]), last_trip


def _upsert_impact(cur, driver_id, aq_id, campaign_id, contact_status,
                   disposition, contact_date, baseline_trips, baseline_last,
                   post_trips, post_last, impact_status):
    cur.execute(
        f"""
        SELECT id FROM {TABLE_IMPACT}
        WHERE driver_id = %(did)s
          AND campaign_id_external IS NOT DISTINCT FROM %(cid)s
          AND contact_date = %(cd)s
        LIMIT 1
    """,
        {"did": driver_id, "cid": campaign_id, "cd": contact_date},
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            f"""
            UPDATE {TABLE_IMPACT}
            SET contact_status = %(cs)s,
                disposition = %(dp)s,
                baseline_trips = %(bt)s,
                baseline_last_trip_at = %(bl)s,
                post_contact_trips = %(pt)s,
                post_contact_last_trip_at = %(pl)s,
                impact_status = %(is)s,
                measured_at = now(),
                updated_at = now()
            WHERE id = %(eid)s
        """,
            {
                "cs": contact_status,
                "dp": disposition,
                "bt": baseline_trips,
                "bl": baseline_last,
                "pt": post_trips,
                "pl": post_last,
                "is": impact_status,
                "eid": existing["id"],
            },
        )
    else:
        cur.execute(
            f"""
            INSERT INTO {TABLE_IMPACT} (
                driver_id, assignment_queue_id, campaign_id_external,
                contact_status, disposition, contact_date,
                baseline_trips, baseline_last_trip_at,
                post_contact_trips, post_contact_last_trip_at,
                impact_status, measured_at
            ) VALUES (
                %(did)s, %(aq)s, %(cid)s,
                %(cs)s, %(dp)s, %(cd)s,
                %(bt)s, %(bl)s,
                %(pt)s, %(pl)s,
                %(is)s, now()
            )
        """,
            {
                "did": driver_id,
                "aq": aq_id,
                "cid": campaign_id,
                "cs": contact_status,
                "dp": disposition,
                "cd": contact_date,
                "bt": baseline_trips,
                "bl": baseline_last,
                "pt": post_trips,
                "pl": post_last,
                "is": impact_status,
            },
        )


def get_impact_summary(date_str: Optional[str] = None,
                       campaign_id_external: Optional[str] = None) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {}

    if date_str:
        conditions.append("contact_date = %(d)s")
        params["d"] = date_str
    if campaign_id_external:
        conditions.append("campaign_id_external = %(cid)s")
        params["cid"] = campaign_id_external

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"SELECT COUNT(*) as cnt FROM {TABLE_IMPACT} WHERE {where}", params)
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"""
            SELECT impact_status, COUNT(*) as cnt
            FROM {TABLE_IMPACT}
            WHERE {where}
            GROUP BY impact_status
            ORDER BY cnt DESC
        """,
            params,
        )
        by_impact = [dict(r) for r in cur.fetchall()]

    return {
        "date": date_str,
        "campaign_id_external": campaign_id_external,
        "total_tracked": total,
        "by_impact_status": by_impact,
    }


def get_impact_records(date_str: Optional[str] = None,
                       campaign_id_external: Optional[str] = None,
                       impact_status: Optional[str] = None,
                       limit: int = 200) -> Dict[str, Any]:
    conditions = []
    params: Dict[str, Any] = {"lim": min(limit, 500)}

    if date_str:
        conditions.append("i.contact_date = %(d)s")
        params["d"] = date_str
    if campaign_id_external:
        conditions.append("i.campaign_id_external = %(cid)s")
        params["cid"] = campaign_id_external
    if impact_status:
        conditions.append("i.impact_status = %(is)s")
        params["is"] = impact_status

    where = " AND ".join(conditions) if conditions else "TRUE"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"SELECT COUNT(*) as cnt FROM {TABLE_IMPACT} i WHERE {where}",
            {k: v for k, v in params.items() if k != "lim"},
        )
        total = cur.fetchone()["cnt"]

        cur.execute(
            f"""
            SELECT i.*, q.driver_name as queue_driver_name
            FROM {TABLE_IMPACT} i
            LEFT JOIN growth.yego_lima_assignment_queue q ON q.id = i.assignment_queue_id
            WHERE {where}
            ORDER BY i.measured_at DESC NULLS LAST
            LIMIT %(lim)s
        """,
            params,
        )
        rows = cur.fetchall()

    records = []
    for r in rows:
        records.append({
            "id": str(r["id"]),
            "driver_id": r["driver_id"],
            "driver_name": r.get("queue_driver_name"),
            "assignment_queue_id": str(r["assignment_queue_id"]) if r.get("assignment_queue_id") else None,
            "campaign_id_external": r.get("campaign_id_external"),
            "contact_status": r.get("contact_status"),
            "disposition": r.get("disposition"),
            "contact_date": r["contact_date"].isoformat() if hasattr(r.get("contact_date"), 'isoformat') else str(r.get("contact_date")) if r.get("contact_date") else None,
            "baseline_trips": r.get("baseline_trips", 0),
            "post_contact_trips": r.get("post_contact_trips", 0),
            "impact_status": r["impact_status"],
            "measured_at": r["measured_at"].isoformat() if r.get("measured_at") else None,
        })

    return {"total_records": total, "records": records}
