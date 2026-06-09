"""
YEGO Lima Growth — Refresh Governance Status (LG-R2.9I / LG-CF-HOTFIX-1B)

Answers: Is this system operable right now?
Reads run logs + serving facts + freshness_registry. NO recalculation. NO pipeline trigger.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from app.db.connection import get_db
from app.services.freshness_service import compute_freshness


COMPONENTS = [
    ("raw_orders", "growth.yango_lima_orders_raw", "ended_at"),
    ("driver_state", "growth.yango_lima_driver_state_snapshot", "snapshot_date"),
    ("eligibility", "growth.yango_lima_program_eligibility_daily", "eligibility_date"),
    ("prioritized", "growth.yango_lima_prioritized_opportunity_daily", "opportunity_date"),
    ("queue", "growth.yego_lima_assignment_queue", "assignment_date"),
    ("daily_registry", "growth.yego_lima_refresh_run_log", "operational_data_date"),
    ("snapshot_registry", "growth.yego_lima_freshness_registry", "last_refresh_at"),
]


def _refresh_freshness_registry(op_date: str = None):
    now = datetime.now(timezone.utc)
    with get_db() as conn:
        cur = conn.cursor()
        for component, table, col in COMPONENTS:
            try:
                if component == "snapshot_registry":
                    cur.execute("SELECT MAX(last_refresh_at) FROM %s" % table)
                else:
                    cur.execute("SELECT MAX(%s) FROM %s" % (col, table))
                row = cur.fetchone()
                max_date = str(row[0]) if row and row[0] else None
            except Exception:
                max_date = None

            if max_date:
                freshness = compute_freshness(component, max_date, table)
                fstatus = freshness.get("status", "UNKNOWN")
                latency = freshness.get("age_minutes")
            else:
                fstatus = "EMPTY"
                latency = None

            cur.execute("""
                UPDATE growth.yego_lima_freshness_registry
                SET freshness_status = %(st)s,
                    last_refresh_at = %(now)s,
                    max_data_date = %(mdd)s::date,
                    latency_minutes = %(lat)s,
                    updated_at = %(now)s
                WHERE component = %(c)s
            """, {
                "st": fstatus,
                "now": now,
                "mdd": max_date,
                "lat": latency,
                "c": component,
            })
        conn.commit()


def get_governance_status() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    op_date = None
    max_snapshot = None

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
        row = cur.fetchone()
        if row and row[0]:
            max_snapshot = row[0]
            op_date = str(max_snapshot)

    if not op_date:
        return {
            "operational_data_date": None,
            "today_action_date": today,
            "max_data_date": None,
            "freshness_age_minutes": None,
            "freshness_status": "UNKNOWN",
            "is_operable_today": False,
            "operability": "NOT_OPERABLE_MISSING_FACTS",
            "blocking_reasons": ["No operational data found. Run bootstrap pipeline."],
            "required_action": "POST /yego-lima-growth/pipeline/run-daily",
            "stale_components": [],
            "broken_components": [],
            "facts": [],
            "pipeline": {"last_run_status": "NEVER_RUN"},
        }

    freshness = compute_freshness("driver_snapshot", max_snapshot, "driver_state_snapshot")
    age_minutes = freshness.get("age_minutes") or 0
    f_status = freshness.get("status", "UNKNOWN")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, status, started_at, finished_at, warnings "
            "FROM growth.yego_lima_refresh_run_log "
            "WHERE operational_data_date = %(d)s "
            "ORDER BY started_at DESC LIMIT 1",
            {"d": op_date}
        )
        last_run = cur.fetchone()

    pipeline = {}
    if last_run:
        pipeline = {
            "last_run_id": str(last_run[0]),
            "last_run_status": last_run[1],
            "last_run_started": last_run[2].isoformat() if last_run[2] else None,
            "last_run_finished": last_run[3].isoformat() if last_run[3] else None,
            "warnings": last_run[4],
        }
    else:
        pipeline = {"last_run_status": "NEVER_RUN"}

    fact_types = ["operational_summary", "today_action_plan", "programs_summary",
                  "driver_state_summary", "queue_summary", "allocation_trace",
                  "program_capacity_policy", "refresh_status"]

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT fact_type, generated_at, freshness_status "
            "FROM growth.yego_lima_serving_fact WHERE fact_date = %(d)s",
            {"d": op_date}
        )
        existing = {r[0]: {"generated_at": r[1], "freshness_status": r[2]} for r in cur.fetchall()}

    facts = []
    all_ok = True
    any_missing = False
    any_stale = False

    for ft in fact_types:
        entry = existing.get(ft)
        if not entry:
            facts.append({
                "fact_type": ft, "status": "MISSING",
                "generated_at": None, "age_minutes": None,
                "remediation": "Run refresh pipeline to generate this fact"
            })
            any_missing = True
            all_ok = False
        else:
            gen = entry["generated_at"]
            age = (now - gen).total_seconds() / 60 if gen else None
            gen_str = gen.isoformat() if gen else None

            if age and age > 1440:
                facts.append({"fact_type": ft, "status": "STALE", "generated_at": gen_str,
                              "age_minutes": round(age, 1),
                              "remediation": "Facts older than 24h. Run refresh pipeline."})
                any_stale = True
            else:
                facts.append({"fact_type": ft, "status": "OK", "generated_at": gen_str,
                              "age_minutes": round(age, 1) if age else None, "remediation": None})

    stale_components = []
    broken_components = []
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT component, freshness_status, max_data_date, latency_minutes "
            "FROM growth.yego_lima_freshness_registry ORDER BY component"
        )
        for r in cur.fetchall():
            comp = {
                "component": r[0],
                "status": r[1] or "UNKNOWN",
                "max_data_date": str(r[2]) if r[2] else None,
                "latency_minutes": r[3],
            }
            if comp["status"] in ("STALE", "WARNING"):
                stale_components.append(comp)
            elif comp["status"] in ("UNKNOWN", "EMPTY", "MISSING"):
                broken_components.append(comp)

    op_date_dt = datetime.strptime(op_date, "%Y-%m-%d").date()
    today_dt = datetime.strptime(today, "%Y-%m-%d").date()
    days_behind = (today_dt - op_date_dt).days

    blocking_reasons = []
    if any_missing:
        blocking_reasons.append("%d serving facts missing" % sum(1 for f in facts if f['status'] == 'MISSING'))

    if days_behind >= 2:
        blocking_reasons.append("Operational data is %d days behind (date: %s)" % (days_behind, op_date))

    if pipeline.get("last_run_status") == "FAILED":
        blocking_reasons.append("Last refresh run FAILED")

    if pipeline.get("last_run_status") == "NEVER_RUN":
        blocking_reasons.append("Refresh pipeline has never been executed")

    if broken_components:
        blocking_reasons.append("%d components with UNKNOWN/EMPTY freshness" % len(broken_components))

    if blocking_reasons:
        operability = "NOT_OPERABLE_STALE" if days_behind >= 2 else "NOT_OPERABLE_MISSING_FACTS"
        is_operable = False
    elif days_behind == 1:
        operability = "OPERABLE_STALE_WARNING"
        is_operable = True
    elif all_ok:
        operability = "OPERABLE"
        is_operable = True
    else:
        operability = "UNKNOWN"
        is_operable = True

    return {
        "operational_data_date": op_date,
        "today_action_date": today,
        "max_data_date": op_date,
        "last_successful_refresh_at": pipeline.get("last_run_finished"),
        "freshness_age_minutes": round(age_minutes, 1) if age_minutes else None,
        "freshness_status": f_status,
        "days_behind": days_behind,
        "is_operable_today": is_operable,
        "operability": operability,
        "stale_components": stale_components,
        "broken_components": broken_components,
        "blocking_reasons": blocking_reasons,
        "required_action": (
            "Ejecutar refresh pipeline: POST /yego-lima-growth/refresh/run"
            if any_missing or days_behind >= 1 or pipeline.get("last_run_status") in ("NEVER_RUN", "FAILED")
            else None
        ),
        "facts": facts,
        "pipeline": pipeline,
    }
