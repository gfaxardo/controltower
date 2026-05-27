"""
Driver Campaign Service — FASE H3.2
Execution & Campaign Layer: Campaign Intelligence Foundation

Provides:
  - Schema creation (ops.driver_campaigns, ops.driver_campaign_members)
  - Preview campaign cohort (from actionable queues)
  - Create campaign with frozen member snapshots
  - List/search campaigns
  - Campaign detail with member summary
  - Member export for CRM consumption
  - Outcome ingest (CRM → Control Tower)

Principles:
  - Drivers define universe; CRM executes communication
  - No auto-send, no auto-message, no WhatsApp integration
  - Every campaign must have cohort_source and evidence
  - Snapshots frozen at creation for traceability
  - No duplicate identity tables as live source
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.driver_raw_freshness_service import get_raw_freshness_map
from app.services.driver_actionable_supply_service import generate_actionable_list, generate_actionable_summary
from app.services.driver_lifecycle_service import compute_lifecycle_summary

logger = logging.getLogger(__name__)

TIMEOUT_MS = 15000
SCHEMA_CREATED = False

CAMPAIGN_STATUSES = ["DRAFT", "READY_FOR_CRM", "SENT_TO_CRM", "IN_EXECUTION", "COMPLETED", "CANCELLED"]
CRM_SYNC_STATUSES = ["NOT_SYNCED", "READY", "SYNCED", "PARTIAL", "FAILED"]
CAMPAIGN_TYPES = ["RECOVERY", "REACTIVATION", "LOYALTY", "ACTIVATION", "RETENTION", "CROSS_SELL", "OTHER"]
MEMBER_CRM_STATUSES = ["PENDING", "CONTACTED", "NO_RESPONSE", "BAD_PHONE", "PROMISED_RETURN", "RETURNED", "IRRECOVERABLE", "OTHER"]


def _ensure_schema():
    global SCHEMA_CREATED
    if SCHEMA_CREATED:
        return
    ddl = [
        "CREATE SCHEMA IF NOT EXISTS ops;",
        """
        CREATE TABLE IF NOT EXISTS ops.driver_campaigns (
            campaign_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_name TEXT NOT NULL,
            campaign_type VARCHAR(30) NOT NULL DEFAULT 'RECOVERY',
            campaign_objective TEXT,
            source_layer VARCHAR(50),
            source_queue_types TEXT[],
            cohort_definition_json JSONB,
            country TEXT,
            city TEXT,
            park_id TEXT,
            fleet_or_slice TEXT,
            lifecycle_stage TEXT,
            priority_filter TEXT,
            target_count INTEGER DEFAULT 0,
            with_phone_count INTEGER DEFAULT 0,
            without_phone_count INTEGER DEFAULT 0,
            campaign_status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
            crm_sync_status VARCHAR(20) NOT NULL DEFAULT 'NOT_SYNCED',
            created_by VARCHAR(128),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS ops.driver_campaign_members (
            campaign_member_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID NOT NULL REFERENCES ops.driver_campaigns(campaign_id) ON DELETE CASCADE,
            driver_id TEXT NOT NULL,
            driver_name_snapshot TEXT,
            phone_snapshot TEXT,
            country_snapshot TEXT,
            city_snapshot TEXT,
            park_id_snapshot TEXT,
            queue_type_snapshot TEXT,
            lifecycle_stage_snapshot TEXT,
            priority_snapshot TEXT,
            reason_snapshot TEXT,
            evidence_snapshot JSONB,
            crm_status VARCHAR(20) DEFAULT 'PENDING',
            latest_outcome TEXT,
            outcome_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (campaign_id, driver_id)
        );
        """,
    ]
    try:
        with get_db() as conn:
            cur = conn.cursor()
            for sql in ddl:
                cur.execute(sql)
            conn.commit()
        SCHEMA_CREATED = True
    except Exception as e:
        logger.warning("Campaign schema creation deferred: %s", e)


# ─── Preview ──────────────────────────────────────────────────────────────────

def preview_campaign(
    campaign_name="",
    campaign_type="RECOVERY",
    campaign_objective="",
    source_queue_types=None,
    country=None,
    city=None,
    park_id=None,
    priority=None,
    lifecycle_stage=None,
    has_phone=None,
    max_drivers=1000,
) -> dict:
    source_queue_types = source_queue_types or ["AT_RISK_DRIVERS", "CHURNED_RECENT"]
    priority = priority or ["HIGH", "MEDIUM"]

    all_drivers = []
    warnings_list = []
    per_queue = {}

    for qt in source_queue_types:
        try:
            result = generate_actionable_list(
                queue_type=qt,
                country=country,
                city=city,
                park_id=park_id,
                lifecycle_stage=lifecycle_stage,
                has_phone=has_phone,
                limit=min(max_drivers, 1000),
                offset=0,
            )
            queues = result.get("queues", []) if result else []
            per_queue[qt] = len(queues)
            for q in queues:
                if priority and q.get("queue_priority") not in priority:
                    continue
                all_drivers.append(q)
        except Exception as e:
            warnings_list.append(f"Queue {qt} failed: {str(e)[:100]}")
            per_queue[qt] = 0

    seen = set()
    unique = []
    for d in all_drivers:
        did = d.get("driver_id")
        if did and did not in seen:
            seen.add(did)
            unique.append(d)

    unique = unique[:max_drivers]

    with_phone = sum(1 for d in unique if d.get("has_phone"))
    without_phone = len(unique) - with_phone

    by_priority = {}
    by_lifecycle = {}
    for d in unique:
        p = d.get("queue_priority", "LOW")
        by_priority[p] = by_priority.get(p, 0) + 1
        ls = d.get("lifecycle_stage", "UNKNOWN")
        by_lifecycle[ls] = by_lifecycle.get(ls, 0) + 1

    # Data quality check
    quality_checks = []
    try:
        freshness = get_raw_freshness_map()
        blocking = freshness.get("blocking_gaps", [])
        if blocking:
            quality_checks.append({"status": "blocked", "message": f"{len(blocking)} blocking gaps in freshness"})
        else:
            quality_checks.append({"status": "ok", "message": "Freshness OK"})
    except Exception as e:
        quality_checks.append({"status": "warning", "message": f"Freshness check failed: {str(e)[:100]}"})

    try:
        ls_summary = compute_lifecycle_summary()
        total = sum(s.get("drivers_count", 0) for s in ls_summary.get("summary", []))
        quality_checks.append({"status": "ok", "message": f"Lifecycle active: {total} drivers"})
    except Exception:
        quality_checks.append({"status": "warning", "message": "Lifecycle unavailable"})

    blocking_gaps = [c for c in quality_checks if c["status"] == "blocked"]
    go_no_go = "NO_GO" if blocking_gaps or len(unique) == 0 else "GO" if len(unique) >= 5 else "WARNING"

    return {
        "status": "ok",
        "estimated_total": len(unique),
        "with_phone_count": with_phone,
        "without_phone_count": without_phone,
        "by_queue": per_queue,
        "by_priority": by_priority,
        "by_lifecycle": by_lifecycle,
        "sample_drivers": unique[:10],
        "data_quality": quality_checks,
        "warnings": warnings_list,
        "blocking_gaps": blocking_gaps,
        "recommended_go_no_go": go_no_go,
    }


# ─── Create Campaign ───────────────────────────────────────────────────────────

def create_campaign(
    campaign_name="",
    campaign_type="RECOVERY",
    campaign_objective="",
    source_queue_types=None,
    country=None,
    city=None,
    park_id=None,
    priority=None,
    lifecycle_stage=None,
    has_phone=None,
    max_drivers=1000,
    created_by="system",
) -> dict:
    _ensure_schema()

    preview = preview_campaign(
        campaign_name=campaign_name,
        campaign_type=campaign_type,
        campaign_objective=campaign_objective,
        source_queue_types=source_queue_types,
        country=country,
        city=city,
        park_id=park_id,
        priority=priority,
        lifecycle_stage=lifecycle_stage,
        has_phone=has_phone,
        max_drivers=max_drivers,
    )

    if preview["recommended_go_no_go"] == "NO_GO":
        return {
            "status": "blocked",
            "error": "Campaign cannot be created: no eligible drivers or blocking data gaps",
            "preview": preview,
            "campaign_id": None,
            "members_inserted": 0,
        }

    campaign_id = str(uuid.uuid4())
    definition = {
        "source_queue_types": source_queue_types,
        "country": country, "city": city, "park_id": park_id,
        "priority": priority, "lifecycle_stage": lifecycle_stage,
        "has_phone": has_phone, "max_drivers": max_drivers,
    }

    with_phone = preview["with_phone_count"]
    without_phone = preview["without_phone_count"]

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ops.driver_campaigns
                    (campaign_id, campaign_name, campaign_type, campaign_objective,
                     source_queue_types, cohort_definition_json,
                     country, city, park_id, lifecycle_stage, priority_filter,
                     target_count, with_phone_count, without_phone_count,
                     campaign_status, crm_sync_status, created_by)
                VALUES (%(id)s, %(name)s, %(type)s, %(objective)s,
                        %(queues)s, %(def)s::jsonb,
                        %(country)s, %(city)s, %(park)s, %(ls)s, %(prio)s,
                        %(target)s, %(phone)s, %(nophone)s,
                        'DRAFT', 'NOT_SYNCED', %(by)s)
            """, {
                "id": campaign_id, "name": campaign_name, "type": campaign_type,
                "objective": campaign_objective, "queues": source_queue_types,
                "def": (definition and str(definition).replace("'", '"')) or "{}",
                "country": country, "city": city, "park": park_id,
                "ls": lifecycle_stage, "prio": (priority and ",".join(priority)),
                "target": preview["estimated_total"], "phone": with_phone,
                "nophone": without_phone, "by": created_by,
            })

            # Freeze members
            inserted = 0
            errors = []
            for d in preview["sample_drivers"]:
                try:
                    evidence = {
                        "trips_7d": d.get("trips_7d", 0),
                        "trips_30d": d.get("trips_30d", 0),
                        "days_since_last_trip": d.get("days_since_last_trip"),
                        "has_phone": d.get("has_phone", False),
                    }
                    cur.execute("""
                        INSERT INTO ops.driver_campaign_members
                            (campaign_id, driver_id, driver_name_snapshot, phone_snapshot,
                             country_snapshot, city_snapshot, park_id_snapshot,
                             queue_type_snapshot, lifecycle_stage_snapshot, priority_snapshot,
                             reason_snapshot, evidence_snapshot)
                        VALUES (%(cid)s, %(did)s, %(name)s, %(phone)s,
                                %(country)s, %(city)s, %(park)s,
                                %(qt)s, %(ls)s, %(prio)s,
                                %(reason)s, %(ev)s::jsonb)
                        ON CONFLICT (campaign_id, driver_id) DO NOTHING
                    """, {
                        "cid": campaign_id, "did": d.get("driver_id"),
                        "name": d.get("driver_name"), "phone": d.get("phone"),
                        "country": d.get("country"), "city": d.get("city"),
                        "park": d.get("park_id"), "qt": d.get("queue_type"),
                        "ls": d.get("lifecycle_stage"), "prio": d.get("queue_priority"),
                        "reason": d.get("action_reason"),
                        "ev": str(evidence).replace("'", '"'),
                    })
                    inserted += cur.rowcount
                except Exception as ie:
                    errors.append(str(ie)[:200])

            # Update target count with actual inserted
            cur.execute("""
                UPDATE ops.driver_campaigns
                SET target_count = %(cnt)s, with_phone_count = %(phone)s, without_phone_count = %(nophone)s, updated_at = NOW()
                WHERE campaign_id = %(id)s
            """, {
                "cnt": inserted, "phone": with_phone, "nophone": without_phone, "id": campaign_id,
            })

            conn.commit()

        return {
            "status": "ok",
            "campaign_id": campaign_id,
            "members_inserted": inserted,
            "errors": errors[:5] if errors else [],
            "preview": preview,
        }
    except Exception as e:
        return {"status": "blocked", "error": str(e)[:300], "campaign_id": campaign_id, "members_inserted": 0}


# ─── List Campaigns ────────────────────────────────────────────────────────────

def list_campaigns(
    campaign_status=None,
    campaign_type=None,
    country=None,
    city=None,
    created_from=None,
    created_to=None,
    limit=50,
    offset=0,
) -> dict:
    _ensure_schema()
    conditions = []
    params = {}

    if campaign_status:
        conditions.append("campaign_status = %(status)s")
        params["status"] = campaign_status
    if campaign_type:
        conditions.append("campaign_type = %(type)s")
        params["type"] = campaign_type
    if country:
        conditions.append("country = %(country)s")
        params["country"] = country
    if city:
        conditions.append("city = %(city)s")
        params["city"] = city
    if created_from:
        conditions.append("created_at >= %(from)s")
        params["from"] = created_from
    if created_to:
        conditions.append("created_at <= %(to)s")
        params["to"] = created_to

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params["limit"] = min(limit, 200)
    params["offset"] = offset

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"""
                SELECT campaign_id, campaign_name, campaign_type, campaign_objective,
                       target_count, with_phone_count, without_phone_count,
                       campaign_status, crm_sync_status, country, city,
                       source_queue_types, created_by, created_at, updated_at
                FROM ops.driver_campaigns
                {where}
                ORDER BY created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, params)
            rows = cur.fetchall()

            for r in rows:
                for ts_field in ("created_at", "updated_at"):
                    if r.get(ts_field):
                        r[ts_field] = r[ts_field].isoformat()

            cur.execute(f"SELECT COUNT(*) as total FROM ops.driver_campaigns {where}", params)
            total_row = cur.fetchone()
            total = total_row["total"] if total_row else 0

        return {"status": "ok", "total": total, "campaigns": rows}
    except Exception as e:
        return {"status": "error", "error": str(e)[:300], "campaigns": []}


# ─── Campaign Detail ──────────────────────────────────────────────────────────

def get_campaign_detail(campaign_id: str) -> dict:
    _ensure_schema()
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT * FROM ops.driver_campaigns WHERE campaign_id = %(id)s
            """, {"id": campaign_id})
            campaign = cur.fetchone()
            if not campaign:
                return {"status": "error", "error": "Campaign not found"}

            for ts_field in ("created_at", "updated_at"):
                if campaign.get(ts_field):
                    campaign[ts_field] = campaign[ts_field].isoformat()

            # Members summary
            cur.execute("""
                SELECT
                    COUNT(*) as total_members,
                    COUNT(CASE WHEN phone_snapshot IS NOT NULL AND phone_snapshot != '' THEN 1 END) as with_phone,
                    COUNT(CASE WHEN phone_snapshot IS NULL OR phone_snapshot = '' THEN 1 END) as without_phone,
                    crm_status, COUNT(*) as cnt
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
                GROUP BY crm_status
            """, {"id": campaign_id})
            status_counts = {r["crm_status"]: r["cnt"] for r in cur.fetchall()}
            total_members = sum(status_counts.values())

            # Member sample
            cur.execute("""
                SELECT campaign_member_id, driver_id, driver_name_snapshot, phone_snapshot,
                       queue_type_snapshot, lifecycle_stage_snapshot, priority_snapshot,
                       crm_status, latest_outcome
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
                ORDER BY
                    CASE priority_snapshot
                        WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4
                    END
                LIMIT 20
            """, {"id": campaign_id})
            sample = cur.fetchall()

            # Data quality
            quality = {
                "freshness": _check_freshness_simple(),
                "coverage": {
                    "phone_coverage": round((status_counts.get("CONTACTED", 0) / max(1, total_members)) * 100, 1) if total_members > 0 else 0,
                },
            }

            return {
                "status": "ok",
                "campaign": campaign,
                "members_summary": {
                    "total": total_members,
                    "with_phone": sum(1 for s in sample if s.get("phone_snapshot")),
                    "by_crm_status": status_counts,
                },
                "members_sample": [dict(r) for r in sample],
                "data_quality": quality,
            }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


# ─── Members for CRM ──────────────────────────────────────────────────────────

def get_campaign_members(
    campaign_id: str,
    limit=200,
    offset=0,
    only_with_phone=True,
) -> dict:
    _ensure_schema()
    conditions = ["campaign_id = %(id)s"]
    params = {"id": campaign_id}

    if only_with_phone:
        conditions.append("(phone_snapshot IS NOT NULL AND phone_snapshot != '')")

    where = "WHERE " + " AND ".join(conditions)
    params["limit"] = min(limit, 500)
    params["offset"] = offset

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"""
                SELECT campaign_member_id, campaign_id, driver_id,
                       driver_name_snapshot as driver_name,
                       phone_snapshot as phone,
                       country_snapshot as country,
                       city_snapshot as city,
                       park_id_snapshot as park_id,
                       queue_type_snapshot as queue_type,
                       lifecycle_stage_snapshot as lifecycle_stage,
                       priority_snapshot as priority,
                       reason_snapshot as reason,
                       evidence_snapshot as evidence,
                       crm_status, latest_outcome
                FROM ops.driver_campaign_members
                {where}
                ORDER BY
                    CASE priority_snapshot
                        WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4
                    END
                LIMIT %(limit)s OFFSET %(offset)s
            """, params)
            rows = cur.fetchall()

            # Recommended action by queue type
            actions = {
                "AT_RISK_DRIVERS": "Contactar antes de churn. Última actividad entre 8-21 días.",
                "CHURNED_RECENT": "Intentar reactivación. Evaluar incentivo.",
                "DECLINING_DRIVERS": "Revisar caída operativa reciente. Contactar para retención.",
                "REGISTERED_NO_FIRST_TRIP": "Contactar y asistir activación del primer viaje.",
                "HIGH_POTENTIAL_UNDERUTILIZED": "Explorar disponibilidad para más horas/viajes.",
            }
            for r in rows:
                r["recommended_action"] = actions.get(r.get("queue_type", ""), "Contactar y evaluar situación.")

            cur.execute(f"SELECT COUNT(*) as total FROM ops.driver_campaign_members {where}", params)
            total_row = cur.fetchone()
            total = total_row["total"] if total_row else 0

        return {
            "status": "ok",
            "campaign_id": campaign_id,
            "total": total,
            "limit": min(limit, 500),
            "offset": offset,
            "members": [dict(r) for r in rows],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300], "members": []}


# ─── Outcome Ingest ───────────────────────────────────────────────────────────

def ingest_campaign_outcome(
    campaign_id: str,
    campaign_member_id: str = None,
    driver_id: str = None,
    crm_status="CONTACTED",
    outcome_note="",
    outcome_at=None,
) -> dict:
    _ensure_schema()
    if not campaign_member_id and not driver_id:
        return {"status": "error", "error": "campaign_member_id or driver_id required"}

    if crm_status not in MEMBER_CRM_STATUSES:
        return {"status": "error", "error": f"Invalid crm_status. Use: {MEMBER_CRM_STATUSES}"}

    outcome_ts = outcome_at or datetime.now(timezone.utc).isoformat()

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Find member
            if campaign_member_id:
                cur.execute("""
                    SELECT campaign_member_id, driver_id, crm_status
                    FROM ops.driver_campaign_members
                    WHERE campaign_id = %(cid)s AND campaign_member_id = %(mid)s
                """, {"cid": campaign_id, "mid": campaign_member_id})
            else:
                cur.execute("""
                    SELECT campaign_member_id, driver_id, crm_status
                    FROM ops.driver_campaign_members
                    WHERE campaign_id = %(cid)s AND driver_id = %(did)s
                """, {"cid": campaign_id, "did": driver_id})

            member = cur.fetchone()
            if not member:
                return {"status": "error", "error": "Campaign member not found"}

            cur.execute("""
                UPDATE ops.driver_campaign_members
                SET crm_status = %(status)s,
                    latest_outcome = %(outcome)s,
                    outcome_at = %(ts)s,
                    updated_at = NOW()
                WHERE campaign_id = %(cid)s AND campaign_member_id = %(mid)s
            """, {
                "status": crm_status,
                "outcome": outcome_note,
                "ts": outcome_ts,
                "cid": campaign_id,
                "mid": member["campaign_member_id"],
            })

            # Update campaign crm_sync_status
            cur.execute("""
                UPDATE ops.driver_campaigns
                SET crm_sync_status = CASE
                    WHEN crm_sync_status = 'NOT_SYNCED' THEN 'PARTIAL'
                    ELSE crm_sync_status
                END,
                updated_at = NOW()
                WHERE campaign_id = %(cid)s
            """, {"cid": campaign_id})

            conn.commit()

        return {
            "status": "ok",
            "campaign_id": campaign_id,
            "campaign_member_id": member["campaign_member_id"],
            "driver_id": member["driver_id"],
            "previous_crm_status": member["crm_status"],
            "new_crm_status": crm_status,
            "outcome_note": outcome_note,
            "outcome_at": outcome_ts,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


# ─── Campaign Summary ─────────────────────────────────────────────────────────

def get_campaign_summary(campaign_id: str = None) -> dict:
    """Aggregate summary for a campaign or all campaigns."""
    _ensure_schema()
    cid_filter = "WHERE campaign_id = %(cid)s" if campaign_id else ""
    params = {"cid": campaign_id} if campaign_id else {}

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(f"""
                SELECT crm_status, COUNT(*) as cnt
                FROM ops.driver_campaign_members
                {cid_filter}
                GROUP BY crm_status
            """, params)
            by_status = {r["crm_status"]: r["cnt"] for r in cur.fetchall()}
            total = sum(by_status.values())

        return {
            "status": "ok",
            "total_members": total,
            "by_crm_status": by_status,
            "contacted": by_status.get("CONTACTED", 0),
            "no_response": by_status.get("NO_RESPONSE", 0),
            "bad_phone": by_status.get("BAD_PHONE", 0),
            "returned": by_status.get("RETURNED", 0),
            "pending": by_status.get("PENDING", 0),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _check_freshness_simple():
    try:
        freshness = get_raw_freshness_map()
        fresh = sum(1 for s in freshness.get("sources", []) if s.get("freshness_status") == "fresh")
        blocked = sum(1 for s in freshness.get("sources", []) if s.get("freshness_status") == "blocked")
        return {"status": "ok" if blocked == 0 else "warning", "fresh": fresh, "blocked": blocked}
    except Exception:
        return {"status": "warning", "message": "Freshness unavailable"}
