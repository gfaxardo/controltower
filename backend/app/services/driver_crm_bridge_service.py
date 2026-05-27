"""
Driver CRM Bridge Service — FASE H3.3
Execution & Campaign Layer: CRM Bridge & Sync Layer

Provides:
  - Sync tables (ops.driver_campaign_sync, ops.driver_campaign_sync_log)
  - Member execution_status tracking (adds columns to campaign_members)
  - CRM export payload generation
  - CRM outcomes import
  - Campaign progress computation
  - Sync health & auditability

Principles:
  - Drivers defines universe; CRM executes communication
  - All sync events auditable (actor, timestamp, payload metadata)
  - Graceful degradation: CRM failure does NOT block Drivers
  - Immutable cohorts after sync (no modification of frozen members)
  - No auto-send to CRM; no specific CRM integration
  - Agnostic bridge: any CRM can consume the payload
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 15000
SCHEMA_CREATED = False

SYNC_STATUSES = ["PENDING", "READY", "EXPORTING", "EXPORTED", "PARTIAL", "FAILED", "IMPORTING_OUTCOMES", "COMPLETED"]
SYNC_DIRECTIONS = ["DRIVERS_TO_CRM", "CRM_TO_DRIVERS"]
EXECUTION_STATUSES = [
    "NOT_CONTACTED", "ATTEMPTED", "CONTACTED",
    "FOLLOW_UP_REQUIRED", "RECOVERED", "NO_RESPONSE",
    "BAD_PHONE", "IRRECOVERABLE", "CLOSED",
]


def _ensure_schema():
    global SCHEMA_CREATED
    if SCHEMA_CREATED:
        return

    ddl = [
        "CREATE SCHEMA IF NOT EXISTS ops;",
        # Add execution tracking columns to campaign_members
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema='ops' AND table_name='driver_campaign_members'
                AND column_name='execution_status') THEN
                ALTER TABLE ops.driver_campaign_members
                    ADD COLUMN execution_status VARCHAR(30) DEFAULT 'NOT_CONTACTED';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema='ops' AND table_name='driver_campaign_members'
                AND column_name='attempts_count') THEN
                ALTER TABLE ops.driver_campaign_members
                    ADD COLUMN attempts_count INTEGER DEFAULT 0;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema='ops' AND table_name='driver_campaign_members'
                AND column_name='latest_contact_at') THEN
                ALTER TABLE ops.driver_campaign_members
                    ADD COLUMN latest_contact_at TIMESTAMPTZ;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                WHERE table_schema='ops' AND table_name='driver_campaign_members'
                AND column_name='executed_by') THEN
                ALTER TABLE ops.driver_campaign_members
                    ADD COLUMN executed_by VARCHAR(128);
            END IF;
        END $$;
        """,
        # Sync table
        """
        CREATE TABLE IF NOT EXISTS ops.driver_campaign_sync (
            sync_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            campaign_id UUID NOT NULL REFERENCES ops.driver_campaigns(campaign_id) ON DELETE CASCADE,
            crm_system_name VARCHAR(100),
            sync_direction VARCHAR(30) NOT NULL DEFAULT 'DRIVERS_TO_CRM',
            sync_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
            crm_campaign_reference VARCHAR(200),
            exported_members_count INTEGER DEFAULT 0,
            synced_members_count INTEGER DEFAULT 0,
            failed_members_count INTEGER DEFAULT 0,
            last_sync_at TIMESTAMPTZ,
            sync_started_at TIMESTAMPTZ,
            sync_finished_at TIMESTAMPTZ,
            sync_error_summary TEXT,
            sync_actor VARCHAR(128),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
        # Sync log
        """
        CREATE TABLE IF NOT EXISTS ops.driver_campaign_sync_log (
            sync_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sync_id UUID NOT NULL REFERENCES ops.driver_campaign_sync(sync_id) ON DELETE CASCADE,
            campaign_member_id UUID,
            driver_id TEXT,
            sync_event VARCHAR(50) NOT NULL,
            sync_status VARCHAR(30),
            sync_message TEXT,
            crm_reference TEXT,
            event_actor VARCHAR(128),
            created_at TIMESTAMPTZ DEFAULT NOW()
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
        logger.warning("CRM Bridge schema creation deferred: %s", e)


# ─── CRM Export Payload ───────────────────────────────────────────────────────

def generate_crm_export(campaign_id: str, crm_system_name="generic", actor="system") -> dict:
    _ensure_schema()

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Get campaign
            cur.execute("SELECT * FROM ops.driver_campaigns WHERE campaign_id = %(id)s", {"id": campaign_id})
            campaign = cur.fetchone()
            if not campaign:
                return {"status": "error", "error": "Campaign not found"}

            # Get members
            cur.execute("""
                SELECT campaign_member_id, driver_id, driver_name_snapshot, phone_snapshot,
                       country_snapshot, city_snapshot, park_id_snapshot,
                       queue_type_snapshot, lifecycle_stage_snapshot, priority_snapshot,
                       reason_snapshot, evidence_snapshot, crm_status, execution_status
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
                ORDER BY
                    CASE priority_snapshot
                        WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4
                    END
            """, {"id": campaign_id})
            members = cur.fetchall()

            # Create sync record
            sync_id = str(uuid.uuid4())
            total = len(members)
            with_phone = sum(1 for m in members if m.get("phone_snapshot"))

            cur.execute("""
                INSERT INTO ops.driver_campaign_sync
                    (sync_id, campaign_id, crm_system_name, sync_direction, sync_status,
                     exported_members_count, sync_started_at, sync_actor)
                VALUES (%(sid)s, %(cid)s, %(crm)s, 'DRIVERS_TO_CRM', 'EXPORTING',
                        %(cnt)s, NOW(), %(actor)s)
            """, {
                "sid": sync_id, "cid": campaign_id, "crm": crm_system_name,
                "cnt": total, "actor": actor,
            })

            # Log sync event
            cur.execute("""
                INSERT INTO ops.driver_campaign_sync_log
                    (sync_id, sync_event, sync_status, sync_message, event_actor)
                VALUES (%(sid)s, 'EXPORT_STARTED', 'EXPORTING', %(msg)s, %(actor)s)
            """, {
                "sid": sync_id, "msg": f"Exporting {total} members to {crm_system_name}",
                "actor": actor,
            })

            # Update campaign
            cur.execute("""
                UPDATE ops.driver_campaigns
                SET crm_sync_status = 'READY', campaign_status = 'READY_FOR_CRM', updated_at = NOW()
                WHERE campaign_id = %(id)s AND campaign_status = 'DRAFT'
            """, {"id": campaign_id})
            cur.execute("""
                UPDATE ops.driver_campaign_sync
                SET sync_status = 'EXPORTED', exported_members_count = %(cnt)s,
                    synced_members_count = %(cnt)s, sync_finished_at = NOW(), last_sync_at = NOW()
                WHERE sync_id = %(sid)s
            """, {"cnt": total, "sid": sync_id})

            # Log completion
            cur.execute("""
                INSERT INTO ops.driver_campaign_sync_log
                    (sync_id, sync_event, sync_status, sync_message, event_actor)
                VALUES (%(sid)s, 'EXPORT_COMPLETED', 'EXPORTED', %(msg)s, %(actor)s)
            """, {
                "sid": sync_id,
                "msg": f"Export completed: {total} members, {with_phone} with phone",
                "actor": actor,
            })

            conn.commit()

        members_payload = []
        actions = {
            "AT_RISK_DRIVERS": "Contactar antes de churn. Última actividad entre 8-21 días.",
            "CHURNED_RECENT": "Intentar reactivación. Evaluar incentivo.",
            "DECLINING_DRIVERS": "Revisar caída operativa reciente. Contactar para retención.",
            "REGISTERED_NO_FIRST_TRIP": "Contactar y asistir activación del primer viaje.",
            "HIGH_POTENTIAL_UNDERUTILIZED": "Explorar disponibilidad para más horas/viajes.",
        }

        for m in members:
            qt = m.get("queue_type_snapshot", "")
            members_payload.append({
                "campaign_member_id": str(m["campaign_member_id"]),
                "driver_id": m["driver_id"],
                "driver_name": m.get("driver_name_snapshot"),
                "phone": m.get("phone_snapshot"),
                "country": m.get("country_snapshot"),
                "city": m.get("city_snapshot"),
                "park_id": m.get("park_id_snapshot"),
                "queue_type": qt,
                "lifecycle_stage": m.get("lifecycle_stage_snapshot"),
                "priority": m.get("priority_snapshot"),
                "reason": m.get("reason_snapshot"),
                "recommended_action": actions.get(qt, "Contactar y evaluar situación."),
            })

        campaign_meta = {
            "campaign_id": str(campaign["campaign_id"]),
            "campaign_name": campaign.get("campaign_name"),
            "campaign_type": campaign.get("campaign_type"),
            "campaign_objective": campaign.get("campaign_objective"),
            "country": campaign.get("country"),
            "city": campaign.get("city"),
        }

        return {
            "status": "ok",
            "sync_id": sync_id,
            "campaign": campaign_meta,
            "members": members_payload,
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "sync_id": sync_id,
                "campaign_status": campaign.get("campaign_status"),
                "crm_sync_status": "READY",
                "total_members": total,
                "with_phone": with_phone,
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


# ─── CRM Import Outcomes ──────────────────────────────────────────────────────

def import_crm_outcomes(
    campaign_id: str,
    crm_system_name="generic",
    crm_campaign_reference=None,
    outcomes=None,
    actor="crm_system",
) -> dict:
    _ensure_schema()
    outcomes = outcomes or []

    if not outcomes:
        return {"status": "error", "error": "No outcomes provided"}

    sync_id = str(uuid.uuid4())
    processed = 0
    failed = 0
    updated = 0
    errors = []

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Create sync record for import
            cur.execute("""
                INSERT INTO ops.driver_campaign_sync
                    (sync_id, campaign_id, crm_system_name, sync_direction, sync_status,
                     crm_campaign_reference, sync_started_at, sync_actor)
                VALUES (%(sid)s, %(cid)s, %(crm)s, 'CRM_TO_DRIVERS', 'IMPORTING_OUTCOMES',
                        %(ref)s, NOW(), %(actor)s)
            """, {
                "sid": sync_id, "cid": campaign_id, "crm": crm_system_name,
                "ref": crm_campaign_reference, "actor": actor,
            })

            for outcome in outcomes:
                processed += 1
                member_id = outcome.get("campaign_member_id")
                driver_id_val = outcome.get("driver_id")
                execution_status = outcome.get("execution_status", "CONTACTED")
                outcome_text = outcome.get("outcome", "")
                contacted_at = outcome.get("contacted_at")
                executed_by = outcome.get("executed_by", crm_system_name)
                attempt = outcome.get("attempt_number", 1)

                # Validate execution_status
                valid_statuses = EXECUTION_STATUSES
                if execution_status not in valid_statuses:
                    errors.append(f"Invalid execution_status '{execution_status}' for member {member_id or driver_id_val}")
                    failed += 1
                    continue

                try:
                    # Find and update member
                    if member_id:
                        cur.execute("""
                            UPDATE ops.driver_campaign_members
                            SET execution_status = %(es)s,
                                latest_outcome = %(outcome)s,
                                latest_outcome_note = %(outcome)s,
                                outcome_at = COALESCE(%(cat)s, NOW()),
                                attempts_count = attempts_count + %(att)s,
                                latest_contact_at = COALESCE(%(cat)s, latest_contact_at),
                                executed_by = %(by)s,
                                crm_status = %(es)s,
                                updated_at = NOW()
                            WHERE campaign_id = %(cid)s AND campaign_member_id = %(mid)s
                        """, {
                            "es": execution_status, "outcome": outcome_text,
                            "cat": contacted_at, "att": 1 if attempt > 0 else 0,
                            "by": executed_by, "cid": campaign_id, "mid": member_id,
                        })
                    elif driver_id_val:
                        cur.execute("""
                            UPDATE ops.driver_campaign_members
                            SET execution_status = %(es)s,
                                latest_outcome = %(outcome)s,
                                latest_outcome_note = %(outcome)s,
                                outcome_at = COALESCE(%(cat)s, NOW()),
                                attempts_count = attempts_count + %(att)s,
                                latest_contact_at = COALESCE(%(cat)s, latest_contact_at),
                                executed_by = %(by)s,
                                crm_status = %(es)s,
                                updated_at = NOW()
                            WHERE campaign_id = %(cid)s AND driver_id = %(did)s
                        """, {
                            "es": execution_status, "outcome": outcome_text,
                            "cat": contacted_at, "att": 1 if attempt > 0 else 0,
                            "by": executed_by, "cid": campaign_id, "did": driver_id_val,
                        })
                    else:
                        failed += 1
                        errors.append("campaign_member_id or driver_id required")
                        continue

                    if cur.rowcount > 0:
                        updated += 1
                        # Log success
                        cur.execute("""
                            INSERT INTO ops.driver_campaign_sync_log
                                (sync_id, campaign_member_id, driver_id, sync_event,
                                 sync_status, sync_message, event_actor)
                            VALUES (%(sid)s, %(mid)s, %(did)s, 'OUTCOME_INGESTED',
                                    'ok', %(msg)s, %(actor)s)
                        """, {
                            "sid": sync_id, "mid": member_id, "did": driver_id_val,
                            "msg": f"Outcome ingested: {execution_status}",
                            "actor": actor,
                        })
                    else:
                        # Member not found - log warning, don't fail
                        cur.execute("""
                            INSERT INTO ops.driver_campaign_sync_log
                                (sync_id, campaign_member_id, driver_id, sync_event,
                                 sync_status, sync_message, event_actor)
                            VALUES (%(sid)s, %(mid)s, %(did)s, 'OUTCOME_SKIPPED',
                                    'warning', %(msg)s, %(actor)s)
                        """, {
                            "sid": sync_id, "mid": member_id, "did": driver_id_val,
                            "msg": "Member not found in campaign",
                            "actor": actor,
                        })

                except Exception as ie:
                    failed += 1
                    errors.append(str(ie)[:200])

            # Update sync record
            sync_status = "COMPLETED" if failed == 0 else "PARTIAL"
            cur.execute("""
                UPDATE ops.driver_campaign_sync
                SET sync_status = %(status)s,
                    exported_members_count = %(proc)s,
                    synced_members_count = %(upd)s,
                    failed_members_count = %(fail)s,
                    sync_error_summary = %(err)s,
                    sync_finished_at = NOW(),
                    last_sync_at = NOW()
                WHERE sync_id = %(sid)s
            """, {
                "status": sync_status, "proc": processed, "upd": updated,
                "fail": failed, "err": ("; ".join(errors[:5])) if errors else None,
                "sid": sync_id,
            })

            # Update campaign
            cur.execute("""
                UPDATE ops.driver_campaigns
                SET crm_sync_status = CASE
                    WHEN %(fail)s = 0 THEN 'SYNCED'
                    ELSE 'PARTIAL'
                END,
                campaign_status = CASE
                    WHEN campaign_status = 'READY_FOR_CRM' THEN 'IN_EXECUTION'
                    ELSE campaign_status
                END,
                updated_at = NOW()
                WHERE campaign_id = %(cid)s
            """, {"fail": failed, "cid": campaign_id})

            conn.commit()

        return {
            "status": "ok" if failed == 0 else "partial",
            "sync_id": sync_id,
            "processed": processed,
            "updated": updated,
            "failed": failed,
            "errors": errors[:10] if errors else [],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300], "processed": processed, "failed": failed}


# ─── Campaign Progress ────────────────────────────────────────────────────────

def compute_campaign_progress(campaign_id: str) -> dict:
    _ensure_schema()

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN execution_status IN ('CONTACTED', 'RECOVERED', 'FOLLOW_UP_REQUIRED') THEN 1 END) as contacted,
                    COUNT(CASE WHEN execution_status = 'RECOVERED' THEN 1 END) as recovered,
                    COUNT(CASE WHEN execution_status = 'NO_RESPONSE' THEN 1 END) as no_response,
                    COUNT(CASE WHEN execution_status = 'BAD_PHONE' THEN 1 END) as bad_phone,
                    COUNT(CASE WHEN execution_status = 'NOT_CONTACTED' THEN 1 END) as pending,
                    COUNT(CASE WHEN execution_status = 'FOLLOW_UP_REQUIRED' THEN 1 END) as follow_up,
                    COUNT(CASE WHEN execution_status = 'IRRECOVERABLE' THEN 1 END) as irrecoverable,
                    COUNT(CASE WHEN execution_status = 'CLOSED' THEN 1 END) as closed,
                    COUNT(CASE WHEN execution_status != 'NOT_CONTACTED' THEN 1 END) as executed,
                    AVG(attempts_count) FILTER (WHERE attempts_count > 0) as avg_attempts,
                    COUNT(CASE WHEN phone_snapshot IS NOT NULL AND phone_snapshot != '' THEN 1 END) as with_phone
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
            """, {"id": campaign_id})
            progress = cur.fetchone()
            if not progress or progress["total"] == 0:
                return {"status": "ok", "total": 0, "message": "No members"}

            total = progress["total"] or 0

            # Outcomes by execution_status
            cur.execute("""
                SELECT execution_status, COUNT(*) as cnt
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s
                GROUP BY execution_status
            """, {"id": campaign_id})
            by_execution = {r["execution_status"]: r["cnt"] for r in cur.fetchall()}

            # Outcomes by executed_by
            cur.execute("""
                SELECT executed_by, execution_status, COUNT(*) as cnt
                FROM ops.driver_campaign_members
                WHERE campaign_id = %(id)s AND executed_by IS NOT NULL
                GROUP BY executed_by, execution_status
                ORDER BY cnt DESC
            """, {"id": campaign_id})
            by_owner = {}
            for r in cur.fetchall():
                o = r["executed_by"] or "unknown"
                if o not in by_owner:
                    by_owner[o] = {}
                by_owner[o][r["execution_status"]] = r["cnt"]

            # Sync history
            cur.execute("""
                SELECT sync_id, sync_direction, sync_status, exported_members_count,
                       synced_members_count, failed_members_count, last_sync_at,
                       crm_system_name
                FROM ops.driver_campaign_sync
                WHERE campaign_id = %(id)s
                ORDER BY created_at DESC
                LIMIT 10
            """, {"id": campaign_id})
            sync_history = []
            for r in cur.fetchall():
                entry = dict(r)
                for ts in ("last_sync_at",):
                    if entry.get(ts):
                        entry[ts] = entry[ts].isoformat()
                sync_history.append(entry)

        return {
            "status": "ok",
            "total": total,
            "contacted": progress["contacted"] or 0,
            "recovered": progress["recovered"] or 0,
            "no_response": progress["no_response"] or 0,
            "bad_phone": progress["bad_phone"] or 0,
            "pending": progress["pending"] or 0,
            "follow_up": progress["follow_up"] or 0,
            "irrecoverable": progress["irrecoverable"] or 0,
            "closed": progress["closed"] or 0,
            "contact_rate": round(((progress["contacted"] or 0) / max(1, (progress["executed"] or 1))) * 100, 1),
            "recovery_rate": round(((progress["recovered"] or 0) / max(1, (progress["contacted"] or 1))) * 100, 1),
            "execution_coverage": round(((progress["executed"] or 0) / max(1, total)) * 100, 1),
            "avg_attempts": round(progress["avg_attempts"] or 0, 1),
            "by_execution_status": by_execution,
            "by_owner": by_owner,
            "sync_history": sync_history,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


# ─── Sync Health ──────────────────────────────────────────────────────────────

def get_sync_health(campaign_id: str = None) -> dict:
    _ensure_schema()

    cid_filter = "WHERE campaign_id = %(cid)s" if campaign_id else ""
    params = {"cid": campaign_id} if campaign_id else {}

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Overall sync stats
            cur.execute(f"""
                SELECT
                    COUNT(*) as total_syncs,
                    COUNT(CASE WHEN sync_status = 'FAILED' THEN 1 END) as failed,
                    COUNT(CASE WHEN sync_status = 'PARTIAL' THEN 1 END) as partial,
                    COUNT(CASE WHEN sync_status = 'COMPLETED' THEN 1 END) as completed,
                    COUNT(CASE WHEN sync_status = 'EXPORTED' THEN 1 END) as exported,
                    MAX(last_sync_at) as latest_sync
                FROM ops.driver_campaign_sync
                {cid_filter}
            """, params)
            stats = cur.fetchone()

            # Campaigns not yet synced
            cur.execute("""
                SELECT campaign_id, campaign_name, campaign_status, crm_sync_status, created_at
                FROM ops.driver_campaigns
                WHERE crm_sync_status IN ('NOT_SYNCED', 'READY') AND campaign_status != 'CANCELLED'
                ORDER BY created_at DESC
                LIMIT 10
            """)
            pending_sync = [dict(r) for r in cur.fetchall()]

            for r in pending_sync:
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].isoformat()

        return {
            "status": "ok",
            "total_syncs": stats["total_syncs"] if stats else 0,
            "failed": stats["failed"] if stats else 0,
            "partial": stats["partial"] if stats else 0,
            "completed": stats["completed"] if stats else 0,
            "exported": stats["exported"] if stats else 0,
            "latest_sync": (stats["latest_sync"].isoformat() if stats and stats.get("latest_sync") else None),
            "pending_sync_campaigns": pending_sync,
            "health": "blocked" if (stats and stats["failed"] and stats["failed"] > 3) else "warning" if (stats and stats["partial"] and stats["partial"] > 0) else "ok",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


# ─── Sync History ─────────────────────────────────────────────────────────────

def get_sync_history(campaign_id: str = None, limit=50, offset=0) -> dict:
    _ensure_schema()

    cid_filter = "WHERE campaign_id = %(cid)s" if campaign_id else ""
    params = {"cid": campaign_id} if campaign_id else {}
    params["limit"] = min(limit, 200)
    params["offset"] = offset

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(f"""
                SELECT sync_id, campaign_id, crm_system_name, sync_direction,
                       sync_status, exported_members_count, synced_members_count,
                       failed_members_count, sync_error_summary,
                       sync_started_at, sync_finished_at, last_sync_at, sync_actor
                FROM ops.driver_campaign_sync
                {cid_filter}
                ORDER BY created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, params)
            rows = cur.fetchall()

            for r in rows:
                for ts in ("sync_started_at", "sync_finished_at", "last_sync_at"):
                    if r.get(ts):
                        r[ts] = r[ts].isoformat()

            cur.execute(f"SELECT COUNT(*) as total FROM ops.driver_campaign_sync {cid_filter}", params)
            total = cur.fetchone()["total"] if cur.rowcount > 0 else 0

        return {"status": "ok", "total": total, "syncs": [dict(r) for r in rows]}
    except Exception as e:
        return {"status": "error", "error": str(e)[:300], "syncs": []}


# ─── Graceful Degradation Check ───────────────────────────────────────────────

def check_bridge_health() -> dict:
    """Check if the bridge is healthy, without blocking anything."""
    checks = []
    try:
        health = get_sync_health()
        checks.append({"name": "sync_health", "status": health.get("health", "warning"), "message": f"Total syncs: {health.get('total_syncs', 0)}, failed: {health.get('failed', 0)}"})
    except Exception as e:
        checks.append({"name": "sync_health", "status": "warning", "message": str(e)[:100]})

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM ops.driver_campaign_sync LIMIT 1")
            checks.append({"name": "sync_table", "status": "ok", "message": "Sync table exists"})
    except Exception:
        checks.append({"name": "sync_table", "status": "blocked", "message": "Sync table not found"})

    blocking = [c for c in checks if c["status"] == "blocked"]

    return {
        "status": "blocked" if blocking else "ok",
        "checks": checks,
        "message": "CRM Bridge is operational. CRM failure does NOT block Drivers." if not blocking else "CRM Bridge setup incomplete.",
    }
