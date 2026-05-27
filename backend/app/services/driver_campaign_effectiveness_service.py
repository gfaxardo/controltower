"""
Driver Campaign Effectiveness Service — FASE H3.4
Execution & Campaign Layer: Campaign Effectiveness Analytics

Provides:
  - Pre/post campaign trip activity measurement
  - Reactivation detection across windows (D+1, D+3, D+7, D+14, D+30)
  - Group analysis (by owner, queue, lifecycle, priority, city, park)
  - Effectiveness summary across campaigns
  - Data quality warnings (low sample, stale activity, incomplete sync)

Principles:
  - "Observed lift", NOT "caused by campaign"
  - No causal claims. No ML. No scoring.
  - Uses ops.driver_daily_activity_fact for trip data
  - Graceful degradation: partial data → warning, not failure
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 20000
EFFECTIVENESS_WINDOWS = [1, 3, 7, 14, 30]
TABLE_CREATED = False


def _ensure_schema():
    global TABLE_CREATED
    if TABLE_CREATED:
        return
    ddl = [
        "CREATE SCHEMA IF NOT EXISTS ops;",
        """
        CREATE TABLE IF NOT EXISTS ops.driver_campaign_effectiveness (
            effectiveness_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID NOT NULL REFERENCES ops.driver_campaigns(campaign_id) ON DELETE CASCADE,
            campaign_member_id UUID NOT NULL REFERENCES ops.driver_campaign_members(campaign_member_id) ON DELETE CASCADE,
            driver_id TEXT NOT NULL,
            window_days INTEGER NOT NULL DEFAULT 7,
            trips_before INTEGER DEFAULT 0,
            trips_after INTEGER DEFAULT 0,
            first_trip_after_campaign_at TIMESTAMPTZ,
            days_to_first_trip_after INTEGER,
            reactivated_flag BOOLEAN DEFAULT FALSE,
            computed_at TIMESTAMPTZ DEFAULT NOW(),
            data_quality_status VARCHAR(20) DEFAULT 'ok',
            UNIQUE (campaign_id, campaign_member_id, window_days)
        );
        """,
    ]
    try:
        with get_db() as conn:
            cur = conn.cursor()
            for sql in ddl:
                cur.execute(sql)
            conn.commit()
        TABLE_CREATED = True
    except Exception as e:
        logger.warning("Effectiveness schema creation deferred: %s", e)


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET LOCAL statement_timeout = %s", (str(int(timeout_ms)),))
    return c


# ─── Compute Effectiveness ────────────────────────────────────────────────────

def compute_campaign_effectiveness(campaign_id: str, window_days: int = 7, include_members: bool = False, group_by: str = None) -> dict:
    _ensure_schema()

    if window_days not in EFFECTIVENESS_WINDOWS:
        return {"status": "warning", "message": f"window_days must be one of {EFFECTIVENESS_WINDOWS}", "window_days": window_days}

    warnings_list = []
    blocking = []

    try:
        with get_db() as conn:
            cur = _cursor(conn)

            # Get campaign
            cur.execute("""
                SELECT campaign_id, campaign_name, campaign_status, crm_sync_status, created_at
                FROM ops.driver_campaigns WHERE campaign_id = %(id)s
            """, {"id": campaign_id})
            campaign = cur.fetchone()
            if not campaign:
                return {"status": "error", "error": "Campaign not found"}

            # Check CRM sync
            crm_status = campaign.get("crm_sync_status", "NOT_SYNCED")
            if crm_status in ("NOT_SYNCED", "READY"):
                warnings_list.append("Campaign not yet synced to CRM. Effectiveness numbers are preliminary.")

            # Get campaign reference date (use created_at or first sync)
            reference_date = campaign.get("created_at")
            cur.execute("""
                SELECT MIN(sync_started_at) as first_sync
                FROM ops.driver_campaign_sync
                WHERE campaign_id = %(id)s AND sync_direction = 'DRIVERS_TO_CRM'
            """, {"id": campaign_id})
            sync_row = cur.fetchone()
            if sync_row and sync_row.get("first_sync"):
                reference_date = sync_row["first_sync"]

            if not reference_date:
                return {"status": "blocked", "error": "No reference date available (no campaign created_at or sync timestamp)", "blocking_gaps": ["No campaign start date"]}

            # Get members with their snapshots and execution status
            cur.execute("""
                SELECT campaign_member_id, driver_id, driver_name_snapshot,
                       country_snapshot, city_snapshot, queue_type_snapshot,
                       lifecycle_stage_snapshot, priority_snapshot,
                       execution_status, phone_snapshot, created_at as member_created_at
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
                ORDER BY
                    CASE priority_snapshot
                        WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4
                    END
            """, {"id": campaign_id})
            members = cur.fetchall()

            if not members:
                return {"status": "blocked", "error": "Campaign has no members"}

            # Compute effectiveness per member
            ref_date_str = reference_date.isoformat() if hasattr(reference_date, 'isoformat') else str(reference_date)
            before_start = ref_date_str[:10]  # day of campaign as baseline reference
            after_start = (reference_date + timedelta(days=1)).isoformat()[:10] if hasattr(reference_date, '__add__') else ref_date_str[:10]

            # Query activity for all campaign members in relevant windows
            driver_ids = [m["driver_id"] for m in members]
            if not driver_ids:
                return {"status": "blocked", "error": "No valid driver_ids in campaign members"}

            # Build effectiveness data
            results = []
            total_contacted = 0
            total_reactivated = 0
            total_trips_before = 0
            total_trips_after = 0
            total_first_trip_days = 0
            members_with_first_trip = 0

            for member in members:
                did = member["driver_id"]
                try:
                    eff = _compute_member_effectiveness(cur, did, campaign_id, member["campaign_member_id"], reference_date, window_days)
                    results.append({
                        "campaign_member_id": str(member["campaign_member_id"]),
                        "driver_id": did,
                        "driver_name": member.get("driver_name_snapshot"),
                        "queue_type": member.get("queue_type_snapshot"),
                        "lifecycle_stage": member.get("lifecycle_stage_snapshot"),
                        "priority": member.get("priority_snapshot"),
                        "execution_status": member.get("execution_status"),
                        "country": member.get("country_snapshot"),
                        "city": member.get("city_snapshot"),
                        "trips_before": eff["trips_before"],
                        "trips_after": eff["trips_after"],
                        "first_trip_after_campaign_at": eff["first_trip_after_campaign_at"],
                        "days_to_first_trip": eff["days_to_first_trip"],
                        "reactivated": eff["reactivated"],
                        "data_quality": eff.get("data_quality", "ok"),
                    })
                    if member.get("execution_status") == "CONTACTED":
                        total_contacted += 1
                    if eff["reactivated"]:
                        total_reactivated += 1
                    total_trips_before += eff["trips_before"]
                    total_trips_after += eff["trips_after"]
                    if eff["days_to_first_trip"] is not None:
                        total_first_trip_days += eff["days_to_first_trip"]
                        members_with_first_trip += 1
                except Exception as e:
                    logger.warning("Effectiveness compute failed for driver %s: %s", did, e)

            total_members = len(members)
            contact_rate = round((total_contacted / max(1, total_members)) * 100, 1)
            reactivation_rate = round(total_reactivated / max(1, total_members), 3)

            # Group by analysis
            segments = []
            group_key = group_by or None
            if group_key in ("owner", "queue_type", "lifecycle_stage", "priority", "city", "country"):
                segments = _group_effectiveness(results, cur, campaign_id, group_key)

            # Data quality
            if total_members < 5:
                warnings_list.append("Very low sample (< 5 members). Results are directional only.")
            elif total_members < 20:
                warnings_list.append("Low sample (< 20 members). Interpret with caution.")

            # Check activity freshness
            try:
                cur.execute("SELECT MAX(activity_date) as latest FROM ops.driver_daily_activity_fact")
                latest_activity = cur.fetchone()
                if latest_activity and latest_activity.get("latest"):
                    days_stale = (datetime.now(timezone.utc).date() - latest_activity["latest"]).days
                    if days_stale > 3:
                        warnings_list.append(f"Activity data may be stale ({days_stale} days since last refresh)")
            except Exception:
                warnings_list.append("Could not verify activity data freshness")

            # Check window sufficiency
            days_since_campaign = 0
            if hasattr(reference_date, 'date'):
                days_since_campaign = (datetime.now(timezone.utc).date() - reference_date.date()).days
            if days_since_campaign < window_days:
                warnings_list.append(f"D+{window_days} window not yet elapsed. Only {days_since_campaign} days since campaign. Results are partial.")

            response = {
                "status": "warning" if warnings_list else "ok",
                "campaign_id": campaign_id,
                "campaign_name": campaign.get("campaign_name"),
                "reference_date": ref_date_str[:19] if len(ref_date_str) > 10 else ref_date_str,
                "window_days": window_days,
                "days_since_campaign": days_since_campaign,
                "summary": {
                    "target_count": total_members,
                    "contacted_count": total_contacted,
                    "reactivated_count": total_reactivated,
                    "reactivation_rate": reactivation_rate,
                    "trips_before_window": total_trips_before,
                    "trips_after_window": total_trips_after,
                    "observed_trip_delta": total_trips_after - total_trips_before,
                    "avg_days_to_first_trip_after": round(total_first_trip_days / max(1, members_with_first_trip), 1) if members_with_first_trip > 0 else None,
                },
                "segments": segments,
                "warnings": warnings_list,
                "blocking_gaps": blocking,
            }

            if include_members:
                response["members"] = results[:100]

            return response

    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


def _compute_member_effectiveness(cur, driver_id: str, campaign_id: str, member_id: str, reference_date, window_days: int) -> dict:
    """Compute before/after activity for a single campaign member."""
    result = {
        "trips_before": 0,
        "trips_after": 0,
        "first_trip_after_campaign_at": None,
        "days_to_first_trip": None,
        "reactivated": False,
        "data_quality": "ok",
    }

    try:
        ref_str = reference_date.isoformat() if hasattr(reference_date, 'isoformat') else str(reference_date)
        ref_date = datetime.fromisoformat(ref_str[:19]) if 'T' in ref_str else datetime.fromisoformat(ref_str[:10] + "T00:00:00")
    except Exception:
        return result

    before_start = (ref_date - timedelta(days=window_days)).strftime("%Y-%m-%d")
    before_end = ref_date.strftime("%Y-%m-%d")
    after_start = (ref_date + timedelta(days=1)).strftime("%Y-%m-%d")
    after_end = (ref_date + timedelta(days=window_days)).strftime("%Y-%m-%d")

    # Trips before
    try:
        cur.execute("""
            SELECT COALESCE(SUM(completed_trips), 0) as trips
            FROM ops.driver_daily_activity_fact
            WHERE driver_id = %(did)s AND activity_date >= %(start)s AND activity_date <= %(end)s
        """, {"did": driver_id, "start": before_start, "end": before_end})
        row = cur.fetchone()
        result["trips_before"] = int(row["trips"]) if row and row["trips"] is not None else 0
    except Exception:
        result["data_quality"] = "warning"

    # Trips after
    try:
        cur.execute("""
            SELECT COALESCE(SUM(completed_trips), 0) as trips,
                   MIN(activity_date) as first_trip_date
            FROM ops.driver_daily_activity_fact
            WHERE driver_id = %(did)s AND activity_date >= %(start)s AND activity_date <= %(end)s
        """, {"did": driver_id, "start": after_start, "end": after_end})
        row = cur.fetchone()
        result["trips_after"] = int(row["trips"]) if row and row["trips"] is not None else 0
        if row and row.get("first_trip_date"):
            result["first_trip_after_campaign_at"] = row["first_trip_date"].isoformat() if hasattr(row["first_trip_date"], 'isoformat') else str(row["first_trip_date"])
            result["days_to_first_trip"] = (row["first_trip_date"] - ref_date.date()).days if hasattr(row["first_trip_date"], 'date') else None
    except Exception:
        pass

    # Reactivation: had 0 trips before, now has trips after
    if result["trips_before"] == 0 and result["trips_after"] > 0:
        result["reactivated"] = True

    # Persist snapshot
    try:
        cur.execute("""
            INSERT INTO ops.driver_campaign_effectiveness
                (campaign_id, campaign_member_id, driver_id, window_days,
                 trips_before, trips_after, first_trip_after_campaign_at,
                 days_to_first_trip_after, reactivated_flag, data_quality_status)
            VALUES (%(cid)s, %(mid)s, %(did)s, %(wd)s,
                    %(tb)s, %(ta)s, %(fta)s, %(dtf)s, %(rf)s, %(dq)s)
            ON CONFLICT (campaign_id, campaign_member_id, window_days) DO UPDATE SET
                trips_before = EXCLUDED.trips_before,
                trips_after = EXCLUDED.trips_after,
                first_trip_after_campaign_at = EXCLUDED.first_trip_after_campaign_at,
                days_to_first_trip_after = EXCLUDED.days_to_first_trip_after,
                reactivated_flag = EXCLUDED.reactivated_flag,
                computed_at = NOW()
        """, {
            "cid": campaign_id, "mid": member_id, "did": driver_id,
            "wd": window_days, "tb": result["trips_before"],
            "ta": result["trips_after"],
            "fta": result["first_trip_after_campaign_at"],
            "dtf": result["days_to_first_trip"],
            "rf": result["reactivated"],
            "dq": result["data_quality"],
        })
    except Exception:
        pass

    return result


def _group_effectiveness(results, cur, campaign_id, group_key):
    """Group results by a dimension."""
    groups = {}
    for r in results:
        key = str(r.get(group_key, "unknown") or "unknown")
        if key not in groups:
            groups[key] = {"key": key, "total": 0, "contacted": 0, "reactivated": 0, "trips_before": 0, "trips_after": 0, "avg_days_to_first_trip": 0, "members_with_first_trip": 0, "total_first_trip_days": 0}
        g = groups[key]
        g["total"] += 1
        if r.get("execution_status") == "CONTACTED":
            g["contacted"] += 1
        if r.get("reactivated"):
            g["reactivated"] += 1
        g["trips_before"] += r["trips_before"]
        g["trips_after"] += r["trips_after"]
        if r.get("days_to_first_trip") is not None:
            g["total_first_trip_days"] += r["days_to_first_trip"]
            g["members_with_first_trip"] += 1

    result = []
    for key, g in sorted(groups.items()):
        total = max(1, g["total"])
        result.append({
            "key": g["key"],
            "total": g["total"],
            "contacted_count": g["contacted"],
            "reactivated_count": g["reactivated"],
            "reactivation_rate": round(g["reactivated"] / total, 3),
            "trips_before": g["trips_before"],
            "trips_after": g["trips_after"],
            "trip_delta": g["trips_after"] - g["trips_before"],
            "avg_days_to_first_trip": round(g["total_first_trip_days"] / max(1, g["members_with_first_trip"]), 1) if g["members_with_first_trip"] > 0 else None,
        })

    return result


# ─── Effectiveness Summary ────────────────────────────────────────────────────

def get_effectiveness_summary() -> dict:
    _ensure_schema()

    try:
        with get_db() as conn:
            cur = _cursor(conn)

            # Campaigns with outcomes
            cur.execute("""
                SELECT
                    c.campaign_id, c.campaign_name, c.campaign_type,
                    c.campaign_status, c.crm_sync_status,
                    c.target_count, c.with_phone_count,
                    COUNT(DISTINCT m.campaign_member_id) as member_count,
                    COUNT(DISTINCT CASE WHEN m.execution_status = 'CONTACTED' THEN m.campaign_member_id END) as contacted,
                    COUNT(DISTINCT CASE WHEN m.execution_status = 'RECOVERED' THEN m.campaign_member_id END) as recovered,
                    COUNT(DISTINCT CASE WHEN m.execution_status = 'BAD_PHONE' THEN m.campaign_member_id END) as bad_phone,
                    MAX(e.computed_at) as last_effectiveness_computed
                FROM ops.driver_campaigns c
                LEFT JOIN ops.driver_campaign_members m ON c.campaign_id = m.campaign_id
                LEFT JOIN ops.driver_campaign_effectiveness e ON c.campaign_id = e.campaign_id
                GROUP BY c.campaign_id
                ORDER BY c.created_at DESC
                LIMIT 20
            """)
            campaigns = []
            for r in cur.fetchall():
                campaigns.append({
                    "campaign_id": str(r["campaign_id"]),
                    "campaign_name": r.get("campaign_name"),
                    "campaign_type": r.get("campaign_type"),
                    "campaign_status": r.get("campaign_status"),
                    "crm_sync_status": r.get("crm_sync_status"),
                    "target_count": r.get("target_count", 0),
                    "with_phone": r.get("with_phone_count", 0),
                    "member_count": r.get("member_count", 0),
                    "contacted": r.get("contacted", 0),
                    "recovered": r.get("recovered", 0),
                    "bad_phone": r.get("bad_phone", 0),
                    "last_computed": r["last_effectiveness_computed"].isoformat() if r.get("last_effectiveness_computed") else None,
                })

            # Overall stats
            cur.execute("""
                SELECT
                    COUNT(DISTINCT campaign_id) as campaigns_with_effectiveness,
                    COUNT(DISTINCT campaign_id) FILTER (WHERE reactivated_flag = true) as campaigns_with_reactivations,
                    COUNT(*) as total_members_analyzed,
                    SUM(trips_before) as total_trips_before,
                    SUM(trips_after) as total_trips_after,
                    COUNT(*) FILTER (WHERE reactivated_flag = true) as total_reactivated,
                    AVG(days_to_first_trip_after) FILTER (WHERE days_to_first_trip_after IS NOT NULL) as avg_days_to_first
                FROM ops.driver_campaign_effectiveness
                WHERE window_days = 7
            """)
            stats = cur.fetchone()

            overview = {
                "campaigns_with_effectiveness": stats["campaigns_with_effectiveness"] if stats else 0,
                "campaigns_with_reactivations": stats["campaigns_with_reactivations"] if stats else 0,
                "total_members_analyzed": stats["total_members_analyzed"] if stats else 0,
                "total_reactivated": stats["total_reactivated"] if stats else 0,
                "overall_reactivation_rate": round((stats["total_reactivated"] or 0) / max(1, stats["total_members_analyzed"] or 1), 3),
                "total_trips_delta": (stats["total_trips_after"] or 0) - (stats["total_trips_before"] or 0),
                "avg_days_to_first_trip": round(stats["avg_days_to_first"] or 0, 1),
            }

        return {
            "status": "ok",
            "overview": overview,
            "campaigns": campaigns,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300], "campaigns": []}
