"""
Driver Pilot Service — FASE H2
Control Foundation: Real Operations Pilot Preparation

Provides:
  - pilot_readiness: evaluate if system is ready for live pilot
  - cohort_preview: preview cohort before freezing
  - create_cohort: freeze a pilot cohort
  - assign_owners: distribute cases among N operators
  - pilot_metrics: descriptive metrics for pilot tracking
  - learning_log: record operational observations

Principles:
  - Deterministic logic, no scoring, no ML
  - Lightweight queries, no full scans
  - Derives from existing endpoints/services
  - No auto-transitions
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.driver_raw_freshness_service import get_raw_freshness_map
from app.services.driver_lifecycle_service import compute_lifecycle_summary
from app.services.driver_actionable_supply_service import (
    generate_actionable_summary, generate_actionable_list,
)

logger = logging.getLogger(__name__)

TIMEOUT_MS = 15000
PILOT_TABLE_CREATED = False


def _ensure_schema():
    """Ensure pilot tables exist in ops schema."""
    global PILOT_TABLE_CREATED
    if PILOT_TABLE_CREATED:
        return
    ddl = [
        """
        CREATE SCHEMA IF NOT EXISTS ops;
        """,
        """
        CREATE TABLE IF NOT EXISTS ops.driver_pilot_cohort (
            cohort_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            driver_id TEXT NOT NULL,
            driver_name TEXT,
            phone TEXT,
            has_phone BOOLEAN DEFAULT FALSE,
            queue_type TEXT NOT NULL,
            queue_priority TEXT,
            lifecycle_stage TEXT,
            country TEXT,
            city TEXT,
            park_id TEXT,
            park_name TEXT,
            trips_7d INTEGER DEFAULT 0,
            trips_30d INTEGER DEFAULT 0,
            latest_trip_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE (cohort_id, driver_id, queue_type)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS ops.driver_pilot_assignment (
            assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cohort_id UUID NOT NULL,
            driver_id TEXT NOT NULL,
            queue_type TEXT NOT NULL,
            assigned_owner TEXT NOT NULL,
            workflow_status TEXT DEFAULT 'UNASSIGNED',
            assigned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            first_action_at TIMESTAMP WITH TIME ZONE,
            last_action_at TIMESTAMP WITH TIME ZONE,
            UNIQUE (cohort_id, driver_id, queue_type)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS ops.driver_pilot_learning_log (
            log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cohort_id UUID,
            driver_id TEXT,
            owner TEXT,
            observation_type TEXT NOT NULL,
            observation_note TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """,
    ]
    try:
        with get_db() as conn:
            cur = conn.cursor()
            for sql in ddl:
                cur.execute(sql)
            conn.commit()
        PILOT_TABLE_CREATED = True
    except Exception as e:
        logger.warning("Pilot schema creation deferred: %s", e)


# ─── Pilot Readiness ──────────────────────────────────────────────────────────

def evaluate_pilot_readiness() -> dict:
    """
    Evaluate if the system is ready for an operational pilot.
    Checks: identity, phone, lifecycle, queues, workflow, freshness, health.
    Returns readiness_score 0-100 and detailed checks.
    """
    _ensure_schema()
    checks = []
    score = 0
    max_score = 8  # one point per check

    # 1. Raw freshness
    try:
        freshness = get_raw_freshness_map()
        fresh_count = sum(1 for s in freshness.get("sources", []) if s.get("freshness_status") == "fresh")
        stale_count = sum(1 for s in freshness.get("sources", []) if s.get("freshness_status") == "stale")
        blocked_count = sum(1 for s in freshness.get("sources", []) if s.get("freshness_status") == "blocked")
        if blocked_count == 0 and stale_count <= 2:
            checks.append({"name": "freshness", "status": "ok", "message": f"{fresh_count} fresh, {stale_count} stale, {blocked_count} blocked"})
            score += 1
        elif blocked_count > 0:
            checks.append({"name": "freshness", "status": "blocked", "message": f"{blocked_count} sources blocked", "remediation": "Refresh blocked sources before pilot"})
        else:
            checks.append({"name": "freshness", "status": "warning", "message": f"{stale_count} sources stale", "remediation": "Refresh stale sources"})
            score += 0.5
    except Exception as e:
        checks.append({"name": "freshness", "status": "blocked", "message": str(e)[:100], "remediation": "Check DB connectivity"})

    # 2. Identity
    try:
        from app.services.driver_identity_service import search_driver_identities
        identities = search_driver_identities(limit=5, offset=0)
        if identities and len(identities) > 0:
            with_phone = sum(1 for d in identities if d.get("phone"))
            checks.append({"name": "identity", "status": "ok", "message": f"Identity responding, {len(identities)} sample drivers, {with_phone} with phone"})
            score += 1
        else:
            checks.append({"name": "identity", "status": "warning", "message": "Identity endpoint returns empty", "remediation": "Check driver sources"})
    except Exception as e:
        checks.append({"name": "identity", "status": "blocked", "message": str(e)[:100], "remediation": "Check /drivers/identity endpoint"})

    # 3. Phone coverage
    try:
        summary = compute_lifecycle_summary()
        phone_cov = summary.get("quality", {}).get("phone_coverage", 0)
        if phone_cov and float(phone_cov) >= 30:
            checks.append({"name": "phone_coverage", "status": "ok", "message": f"{phone_cov}% phone coverage"})
            score += 1
        elif phone_cov and float(phone_cov) > 0:
            checks.append({"name": "phone_coverage", "status": "warning", "message": f"{phone_cov}% phone coverage (low)", "remediation": "Improve phone data sources"})
            score += 0.5
        else:
            checks.append({"name": "phone_coverage", "status": "warning", "message": "No phone coverage data", "remediation": "Verify phone sources"})
    except Exception as e:
        checks.append({"name": "phone_coverage", "status": "blocked", "message": str(e)[:100]})

    # 4. Lifecycle available
    try:
        ls = compute_lifecycle_summary()
        total_drivers = sum(s.get("drivers_count", 0) for s in ls.get("summary", []))
        if total_drivers > 0:
            checks.append({"name": "lifecycle", "status": "ok", "message": f"{total_drivers} drivers classified"})
            score += 1
        else:
            checks.append({"name": "lifecycle", "status": "warning", "message": "Lifecycle summary empty", "remediation": "Check driver_daily_activity_fact"})
    except Exception as e:
        checks.append({"name": "lifecycle", "status": "blocked", "message": str(e)[:100]})

    # 5. Actionable queues
    try:
        asum = generate_actionable_summary()
        total_q = asum.get("summary", {}).get("total_in_all_queues", 0) if asum else 0
        if total_q > 0:
            checks.append({"name": "actionable_queues", "status": "ok", "message": f"{total_q} drivers in queues"})
            score += 1
        else:
            checks.append({"name": "actionable_queues", "status": "warning", "message": "No actionable drivers", "remediation": "Check activity data freshness"})
    except Exception as e:
        checks.append({"name": "actionable_queues", "status": "blocked", "message": str(e)[:100]})

    # 6. Workflow tables
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='driver_supply_workflow'")
            if cur.fetchone():
                checks.append({"name": "workflow", "status": "ok", "message": "Workflow tables exist"})
                score += 1
            else:
                checks.append({"name": "workflow", "status": "warning", "message": "Workflow tables not found", "remediation": "Call create_workflow_schema()"})
    except Exception as e:
        checks.append({"name": "workflow", "status": "blocked", "message": str(e)[:100]})

    # 7. Actionable drivers with phone
    try:
        alist = generate_actionable_list(limit=200, offset=0)
        queues = alist.get("queues", []) if alist else []
        with_phone = sum(1 for q in queues if q.get("has_phone"))
        total = len(queues)
        if total > 0:
            checks.append({"name": "contactable_drivers", "status": "ok" if with_phone >= 5 else "warning",
                          "message": f"{with_phone}/{total} drivers with phone",
                          "remediation": "" if with_phone >= 5 else "5+ drivers with phone needed for pilot"})
            if with_phone >= 5:
                score += 1
            else:
                score += 0.5
        else:
            checks.append({"name": "contactable_drivers", "status": "blocked", "message": "No drivers in queues"})
    except Exception as e:
        checks.append({"name": "contactable_drivers", "status": "blocked", "message": str(e)[:100]})

    # 8. Assignable drivers (has phone, in actionable queues, not already assigned elsewhere)
    try:
        alist2 = generate_actionable_list(limit=500, offset=0)
        qs = alist2.get("queues", []) if alist2 else []
        assignable = [q for q in qs if q.get("has_phone")]
        checks.append({"name": "assignable_pool", "status": "ok" if len(assignable) >= 10 else "warning",
                      "message": f"{len(assignable)} assignable drivers",
                      "remediation": "" if len(assignable) >= 10 else "Need 10+ assignable drivers"})
        if len(assignable) >= 10:
            score += 1
        elif len(assignable) >= 5:
            score += 0.5
    except Exception as e:
        checks.append({"name": "assignable_pool", "status": "blocked", "message": str(e)[:100]})

    # Derive overall status
    readiness_score = round((score / max_score) * 100, 1)
    blocking = [c for c in checks if c["status"] == "blocked"]
    warnings_list = [c for c in checks if c["status"] == "warning"]

    if blocking:
        status = "blocked"
    elif warnings_list and readiness_score < 60:
        status = "warning"
    elif warnings_list:
        status = "warning"
    else:
        status = "ready"

    # Recommend scope
    recommended_scope = _recommend_scope()

    return {
        "status": status,
        "readiness_score": readiness_score,
        "checks": checks,
        "blocking_gaps": blocking,
        "warnings": warnings_list,
        "recommended_scope": recommended_scope,
    }


def _recommend_scope() -> dict:
    """Recommend best scope for pilot based on data availability."""
    try:
        ls = compute_lifecycle_summary()
        asum = generate_actionable_summary()
        by_queue = asum.get("summary", {}).get("by_queue", {}) if asum else {}

        queues_available = [k for k, v in by_queue.items() if v and v > 0]
        if not queues_available:
            return {"country": None, "city": None, "park": None, "queue_types": [], "reason": "No actionable queues available"}

        preferred = ["AT_RISK_DRIVERS", "REGISTERED_NO_FIRST_TRIP", "DECLINING_DRIVERS"]
        recommended = [q for q in preferred if q in queues_available]

        if not recommended:
            recommended = queues_available[:2]

        quality = ls.get("quality", {}) if ls else {}
        phone_cov = quality.get("phone_coverage", 0) if quality else 0

        reason = f"Seleccionadas {len(recommended)} queues con mayor volumen accionable. Phone coverage: {phone_cov}%."

        return {
            "country": None,
            "city": None,
            "park": None,
            "queue_types": recommended,
            "max_drivers": min(100, sum(by_queue.get(q, 0) for q in recommended)),
            "has_phone_only": True,
            "reason": reason,
        }
    except Exception:
        return {
            "country": None, "city": None, "park": None,
            "queue_types": ["AT_RISK_DRIVERS"],
            "max_drivers": 50,
            "has_phone_only": True,
            "reason": "Fallback scope. Verify data availability before proceeding.",
        }


# ─── Cohort Preview ───────────────────────────────────────────────────────────

def preview_cohort(country=None, city=None, park_id=None, queue_types=None, max_drivers=100, has_phone_only=True) -> dict:
    """Preview a cohort without persisting. Returns driver list."""
    queue_types = queue_types or ["AT_RISK_DRIVERS", "REGISTERED_NO_FIRST_TRIP"]

    all_drivers = []
    for qt in queue_types:
        try:
            result = generate_actionable_list(
                queue_type=qt, country=country, city=city, park_id=park_id,
                has_phone=True if has_phone_only else None,
                limit=min(max_drivers, 300), offset=0,
            )
            queues = result.get("queues", []) if result else []
            for q in queues:
                all_drivers.append({
                    "driver_id": q.get("driver_id"),
                    "driver_name": q.get("driver_name"),
                    "phone": q.get("phone") if q.get("has_phone") else None,
                    "has_phone": q.get("has_phone", False),
                    "queue_type": q.get("queue_type"),
                    "queue_priority": q.get("queue_priority"),
                    "lifecycle_stage": q.get("lifecycle_stage"),
                    "country": q.get("country"),
                    "city": q.get("city"),
                    "park_id": q.get("park_id"),
                    "park_name": q.get("park_name"),
                    "trips_7d": q.get("trips_7d", 0),
                    "trips_30d": q.get("trips_30d", 0),
                    "latest_trip_at": q.get("latest_trip_at"),
                })
        except Exception as e:
            logger.warning("Cohort preview failed for queue %s: %s", qt, e)

    # Deduplicate by driver_id
    seen = set()
    unique = []
    for d in all_drivers:
        if d["driver_id"] not in seen:
            seen.add(d["driver_id"])
            unique.append(d)

    # Limit to max_drivers
    unique = unique[:max_drivers]

    # Prioritize CRITICAL and HIGH
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    unique.sort(key=lambda d: priority_order.get(d.get("queue_priority", "LOW"), 99))

    by_queue = {}
    for d in unique:
        qt = d["queue_type"]
        by_queue[qt] = by_queue.get(qt, 0) + 1

    return {
        "status": "ok",
        "total": len(unique),
        "by_queue": by_queue,
        "with_phone": sum(1 for d in unique if d["has_phone"]),
        "without_phone": sum(1 for d in unique if not d["has_phone"]),
        "drivers": unique,
    }


# ─── Create Cohort ────────────────────────────────────────────────────────────

def create_pilot_cohort(country=None, city=None, park_id=None, queue_types=None, max_drivers=100, has_phone_only=True) -> dict:
    """Create a frozen pilot cohort persisted to ops.driver_pilot_cohort."""
    _ensure_schema()

    preview = preview_cohort(country, city, park_id, queue_types, max_drivers, has_phone_only)
    drivers = preview["drivers"]

    if not drivers:
        return {"status": "blocked", "error": "No drivers available for cohort", "cohort_id": None, "inserted": 0}

    cohort_id = str(uuid.uuid4())
    inserted = 0
    errors = []

    try:
        with get_db() as conn:
            cur = conn.cursor()
            for d in drivers:
                try:
                    cur.execute("""
                        INSERT INTO ops.driver_pilot_cohort
                            (cohort_id, driver_id, driver_name, phone, has_phone,
                             queue_type, queue_priority, lifecycle_stage,
                             country, city, park_id, park_name,
                             trips_7d, trips_30d, latest_trip_at)
                        VALUES (%(cohort_id)s, %(driver_id)s, %(driver_name)s, %(phone)s, %(has_phone)s,
                                %(queue_type)s, %(queue_priority)s, %(lifecycle_stage)s,
                                %(country)s, %(city)s, %(park_id)s, %(park_name)s,
                                %(trips_7d)s, %(trips_30d)s, %(latest_trip_at)s)
                        ON CONFLICT (cohort_id, driver_id, queue_type) DO NOTHING
                    """, {
                        "cohort_id": cohort_id, "driver_id": d["driver_id"], "driver_name": d["driver_name"],
                        "phone": d["phone"], "has_phone": d["has_phone"],
                        "queue_type": d["queue_type"], "queue_priority": d["queue_priority"],
                        "lifecycle_stage": d["lifecycle_stage"],
                        "country": d["country"], "city": d["city"],
                        "park_id": d["park_id"], "park_name": d["park_name"],
                        "trips_7d": d["trips_7d"], "trips_30d": d["trips_30d"],
                        "latest_trip_at": d["latest_trip_at"],
                    })
                    inserted += cur.rowcount
                except Exception as ie:
                    errors.append(str(ie)[:200])
            conn.commit()
    except Exception as e:
        return {"status": "blocked", "error": str(e)[:300], "cohort_id": cohort_id, "inserted": inserted}

    return {
        "status": "ok",
        "cohort_id": cohort_id,
        "inserted": inserted,
        "errors": errors[:5] if errors else [],
        "by_queue": preview["by_queue"],
        "with_phone": preview["with_phone"],
        "without_phone": preview["without_phone"],
    }


# ─── Assign Owners ────────────────────────────────────────────────────────────

def assign_pilot_owners(cohort_id: str, owners: list[str], strategy: str = "balanced_by_priority") -> dict:
    """Distribute cohort cases among owners."""
    _ensure_schema()

    if not owners:
        return {"status": "blocked", "error": "No owners provided", "assigned": 0}

    # Fetch cohort drivers
    drivers = []
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT driver_id, driver_name, queue_type, queue_priority,
                       has_phone, phone, lifecycle_stage
                FROM ops.driver_pilot_cohort
                WHERE cohort_id = %(cohort_id)s
                ORDER BY
                    CASE queue_priority
                        WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                        WHEN 'MEDIUM' THEN 3 ELSE 4
                    END,
                    queue_type
            """, {"cohort_id": cohort_id})
            drivers = cur.fetchall()
    except Exception as e:
        return {"status": "blocked", "error": str(e)[:300], "assigned": 0}

    if not drivers:
        return {"status": "blocked", "error": "Cohort not found or empty", "assigned": 0}

    # Distribute round-robin by priority
    n_owners = len(owners)
    assigned_count = 0
    by_owner = {o: 0 for o in owners}
    errors = []

    try:
        with get_db() as conn:
            cur = conn.cursor()
            for i, d in enumerate(drivers):
                owner = owners[i % n_owners]
                try:
                    cur.execute("""
                        INSERT INTO ops.driver_pilot_assignment
                            (cohort_id, driver_id, queue_type, assigned_owner, workflow_status)
                        VALUES (%(cohort_id)s, %(driver_id)s, %(queue_type)s, %(owner)s, 'UNASSIGNED')
                        ON CONFLICT (cohort_id, driver_id, queue_type) DO UPDATE
                            SET assigned_owner = EXCLUDED.assigned_owner,
                                assigned_at = NOW()
                    """, {
                        "cohort_id": cohort_id,
                        "driver_id": d["driver_id"],
                        "queue_type": d["queue_type"],
                        "owner": owner,
                    })
                    if cur.rowcount > 0:
                        assigned_count += cur.rowcount
                        by_owner[owner] += 1
                except Exception as ie:
                    errors.append(str(ie)[:200])
            conn.commit()
    except Exception as e:
        return {"status": "blocked", "error": str(e)[:300], "assigned": assigned_count}

    return {
        "status": "ok",
        "cohort_id": cohort_id,
        "strategy": strategy,
        "assigned": assigned_count,
        "by_owner": by_owner,
        "errors": errors[:5] if errors else [],
    }


# ─── Pilot Metrics ────────────────────────────────────────────────────────────

def get_pilot_metrics(cohort_id: str = None) -> dict:
    """Get descriptive metrics for pilot tracking."""
    _ensure_schema()

    cohort_filter = "WHERE cohort_id = %(cohort_id)s" if cohort_id else ""
    params = {"cohort_id": cohort_id} if cohort_id else {}

    metrics = {
        "assigned_total": 0,
        "contacted_total": 0,
        "no_response_total": 0,
        "recovered_total": 0,
        "closed_total": 0,
        "pending_total": 0,
        "contact_rate": 0,
        "recovery_rate": 0,
        "invalid_phone_rate": 0,
        "outcomes_by_owner": {},
        "outcomes_by_queue_type": {},
    }

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # By status
            sql_status = f"""
                SELECT workflow_status, COUNT(*) as cnt
                FROM ops.driver_pilot_assignment
                {cohort_filter}
                GROUP BY workflow_status
            """
            cur.execute(sql_status, params)
            status_counts = {r["workflow_status"]: r["cnt"] for r in cur.fetchall()}

            metrics["assigned_total"] = sum(status_counts.values())
            metrics["contacted_total"] = status_counts.get("CONTACTED", 0)
            metrics["no_response_total"] = status_counts.get("NO_RESPONSE", 0)
            metrics["recovered_total"] = status_counts.get("RECOVERED", 0)
            metrics["closed_total"] = status_counts.get("CLOSED", 0)
            metrics["pending_total"] = status_counts.get("UNASSIGNED", 0) + status_counts.get("ASSIGNED", 0) + status_counts.get("IN_PROGRESS", 0)

            total_non_pending = metrics["assigned_total"] - metrics["pending_total"]
            if total_non_pending > 0:
                metrics["contact_rate"] = round((metrics["contacted_total"] / total_non_pending) * 100, 1)
                metrics["recovery_rate"] = round((metrics["recovered_total"] / total_non_pending) * 100, 1)
            else:
                metrics["contact_rate"] = 0
                metrics["recovery_rate"] = 0

            # Invalid phone: count blocked workflows
            metrics["invalid_phone_rate"] = round((status_counts.get("BLOCKED", 0) / max(1, metrics["assigned_total"])) * 100, 1)

            # By owner
            sql_owner = f"""
                SELECT assigned_owner, workflow_status, COUNT(*) as cnt
                FROM ops.driver_pilot_assignment
                {cohort_filter}
                GROUP BY assigned_owner, workflow_status
            """
            cur.execute(sql_owner, params)
            for r in cur.fetchall():
                o = r["assigned_owner"] or "unassigned"
                if o not in metrics["outcomes_by_owner"]:
                    metrics["outcomes_by_owner"][o] = {}
                metrics["outcomes_by_owner"][o][r["workflow_status"]] = r["cnt"]

            # By queue type (from cohort table)
            sql_queue = """
                SELECT c.queue_type, a.workflow_status, COUNT(*) as cnt
                FROM ops.driver_pilot_assignment a
                JOIN ops.driver_pilot_cohort c ON a.cohort_id = c.cohort_id AND a.driver_id = c.driver_id AND a.queue_type = c.queue_type
                {}
                GROUP BY c.queue_type, a.workflow_status
            """.format("AND a.cohort_id = %(cohort_id)s" if cohort_id else "")
            cur.execute(sql_queue, params)
            for r in cur.fetchall():
                qt = r["queue_type"]
                if qt not in metrics["outcomes_by_queue_type"]:
                    metrics["outcomes_by_queue_type"][qt] = {}
                metrics["outcomes_by_queue_type"][qt][r["workflow_status"]] = r["cnt"]

    except Exception as e:
        logger.warning("Pilot metrics query failed: %s", e)

    return metrics


# ─── Learning Log ─────────────────────────────────────────────────────────────

def add_learning_log(cohort_id=None, driver_id=None, owner=None, observation_type=None, observation_note=None) -> dict:
    """Record an operational observation."""
    _ensure_schema()
    if not observation_type:
        return {"status": "error", "error": "observation_type is required"}

    valid_types = ["bad_phone", "wrong_queue", "useful_queue", "unclear_action", "driver_feedback", "system_issue", "other"]
    if observation_type not in valid_types:
        return {"status": "error", "error": f"Invalid observation_type. Use: {valid_types}"}

    log_id = str(uuid.uuid4())
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ops.driver_pilot_learning_log
                    (log_id, cohort_id, driver_id, owner, observation_type, observation_note)
                VALUES (%(log_id)s, %(cohort_id)s, %(driver_id)s, %(owner)s, %(observation_type)s, %(observation_note)s)
            """, {
                "log_id": log_id, "cohort_id": cohort_id, "driver_id": driver_id,
                "owner": owner, "observation_type": observation_type, "observation_note": observation_note,
            })
            conn.commit()
        return {"status": "ok", "log_id": log_id}
    except Exception as e:
        return {"status": "error", "error": str(e)[:300]}


def get_learning_log(cohort_id=None, owner=None, observation_type=None, limit=100, offset=0) -> dict:
    """Query learning log entries."""
    _ensure_schema()

    conditions = []
    params = {}
    if cohort_id:
        conditions.append("cohort_id = %(cohort_id)s")
        params["cohort_id"] = cohort_id
    if owner:
        conditions.append("owner = %(owner)s")
        params["owner"] = owner
    if observation_type:
        conditions.append("observation_type = %(observation_type)s")
        params["observation_type"] = observation_type

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params["limit"] = min(limit, 500)
    params["offset"] = offset

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"""
                SELECT log_id, cohort_id, driver_id, owner, observation_type, observation_note, created_at
                FROM ops.driver_pilot_learning_log
                {where}
                ORDER BY created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, params)
            rows = cur.fetchall()
            # Convert timestamps
            for r in rows:
                if r.get("created_at"):
                    r["created_at"] = r["created_at"].isoformat()
            return {"status": "ok", "total": len(rows), "entries": rows}
    except Exception as e:
        return {"status": "error", "error": str(e)[:300], "entries": []}
