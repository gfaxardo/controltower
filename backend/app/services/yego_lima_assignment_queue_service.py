"""
YEGO Lima Growth — Assignment Queue Service (LG-2.5B V1).

Persistent operational queue from worklist.
Reads worklist → inserts into assignment_queue with dedup.

Rules:
- phone empty → HELD
- assigned_channel = UNASSIGNED → HELD
- resto → READY
- Duplicados (misma fecha/driver/programa) → skipped
"""
from __future__ import annotations

import logging
from datetime import date as DateType
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.yego_lima_opportunity_worklist_service import get_opportunity_worklist

logger = logging.getLogger(__name__)

TABLE_QUEUE = "growth.yego_lima_assignment_queue"


def create_assignment_batch(
    date_str: str,
    program: Optional[str] = None,
    channel: Optional[str] = None,
    city: Optional[str] = None,
) -> Dict[str, Any]:
    worklist = get_opportunity_worklist(
        date_str=date_str,
        program=program,
        channel=channel,
        city=city,
    )
    records = worklist.get("records", [])
    batch_id = str(uuid4())

    created = 0
    ready = 0
    held = 0
    skipped = 0
    skipped_invalid = 0
    skipped_reasons: Dict[str, int] = {}

    with get_db() as conn:
        cur = conn.cursor()

        for r in records:
            did = r.get("driver_id") or ""
            pc = r.get("program_code") or ""
            phone_val = r.get("phone")
            chan = r.get("assigned_channel") or ""

            if not did:
                skipped_invalid += 1
                skipped_reasons["missing_driver_id"] = skipped_reasons.get("missing_driver_id", 0) + 1
                continue
            if not pc:
                skipped_invalid += 1
                skipped_reasons["missing_program_code"] = skipped_reasons.get("missing_program_code", 0) + 1
                continue

            status = "READY"
            if not phone_val or chan == "UNASSIGNED":
                status = "HELD"

            try:
                cur.execute(
                    f"INSERT INTO {TABLE_QUEUE} "
                    f"(assignment_batch_id, assignment_date, driver_id, driver_name, phone, "
                    f" program_code, program_name, priority_rank, assigned_channel, "
                    f" opportunity_reason, last_trip_date, recent_trips, "
                    f" country, city, park, queue_status) "
                    f"VALUES (%(bid)s, %(d)s, %(did)s, %(dn)s, %(ph)s, "
                    f" %(pc)s, %(pn)s, %(pr)s, %(ch)s, "
                    f" %(or)s, %(ltd)s, %(rt)s, "
                    f" %(co)s, %(ci)s, %(pa)s, %(st)s) "
                    f"ON CONFLICT (assignment_date, driver_id, program_code) DO NOTHING",
                    {
                        "bid": batch_id,
                        "d": date_str,
                        "did": did,
                        "dn": r.get("driver_name") or "Sin nombre",
                        "ph": phone_val,
                        "pc": pc,
                        "pn": r.get("program_name") or pc,
                        "pr": r.get("priority_rank"),
                        "ch": chan,
                        "or": r.get("opportunity_reason"),
                        "ltd": r.get("last_trip_date"),
                        "rt": r.get("recent_trips"),
                        "co": r.get("country") or "PE",
                        "ci": r.get("city") or "Lima",
                        "pa": r.get("park") or "Sin park",
                        "st": status,
                    },
                )
                if cur.rowcount > 0:
                    created += 1
                    if status == "READY":
                        ready += 1
                    else:
                        held += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"Insert skipped for driver {did}: {e}")
                skipped_invalid += 1
                err_key = str(e)[:50]
                skipped_reasons[err_key] = skipped_reasons.get(err_key, 0) + 1

        conn.commit()

    # ── Record build audit with active policy (R2.8G) ──
    policy_info = _get_active_policy_for_build(date_str)
    _write_build_audit(batch_id, date_str, policy_info, created, ready + held, ready, held)

    result = {
        "assignment_batch_id": batch_id,
        "assignment_date": date_str,
        "created_count": created,
        "ready_count": ready,
        "held_count": held,
        "skipped_duplicates": skipped,
        "skipped_invalid": skipped_invalid,
        "skipped_reasons": skipped_reasons,
        "policy_applied": policy_info.get("applied", False),
        "allocation_mode": policy_info.get("mode", "STRICT_PRIORITY"),
        "policy_version": policy_info.get("version"),
    }
    return result


def _get_active_policy_for_build(date_str: str) -> Dict[str, Any]:
    try:
        from app.services.yego_lima_program_capacity_policy_service import get_active_policy
        p = get_active_policy(date_str)
        if p.get("active") and p.get("programs"):
            return {
                "applied": True,
                "mode": p["programs"][0].get("allocation_mode", "STRICT_PRIORITY"),
                "version": p["programs"][0].get("version"),
                "programs": len(p.get("programs", [])),
            }
    except Exception:
        pass
    return {"applied": False, "mode": "STRICT_PRIORITY", "version": None}


def _write_build_audit(batch_id: str, date_str: str, policy_info: Dict, total_created: int,
                       total_assigned: int, ready: int, held: int):
    try:
        import json
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO growth.yego_lima_queue_build_audit "
                "(build_batch_id, assignment_date, policy_applied, allocation_mode, policy_version, "
                " total_actionable, total_assigned, total_unassigned, warnings, allocation_snapshot) "
                "VALUES (%(bid)s, %(d)s, %(pa)s, %(am)s, %(pv)s, %(ta)s, %(ts)s, %(tu)s, %(w)s, %(snap)s)",
                {
                    "bid": batch_id, "d": date_str,
                    "pa": policy_info.get("applied", False),
                    "am": policy_info.get("mode", "STRICT_PRIORITY"),
                    "pv": policy_info.get("version"),
                    "ta": total_created, "ts": total_assigned, "tu": 0,
                    "w": json.dumps(None),
                    "snap": json.dumps({"ready": ready, "held": held}),
                }
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Build audit write failed (non-blocking): {e}")


def get_assignment_queue(
    date_str: str,
    status: Optional[str] = None,
    program: Optional[str] = None,
    channel: Optional[str] = None,
) -> Dict[str, Any]:
    conditions = ["assignment_date = %(d)s"]
    params: Dict[str, Any] = {"d": date_str}

    if status:
        conditions.append("queue_status = %(st)s")
        params["st"] = status
    if program:
        conditions.append("program_code = %(p)s")
        params["p"] = program
    if channel:
        conditions.append("assigned_channel = %(ch)s")
        params["ch"] = channel

    where = " AND ".join(conditions)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            f"SELECT COUNT(*) as cnt, "
            f"SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) as ready_cnt, "
            f"SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END) as held_cnt "
            f"FROM {TABLE_QUEUE} WHERE {where}",
            params,
        )
        summary = cur.fetchone()

        cur.execute(
            f"SELECT * FROM {TABLE_QUEUE} WHERE {where} "
            f"ORDER BY priority_rank ASC NULLS LAST, recent_trips ASC NULLS LAST, driver_name ASC NULLS LAST",
            params,
        )
        rows = cur.fetchall()

    records = []
    for r in rows:
        records.append({
            "id": str(r["id"]),
            "assignment_batch_id": str(r["assignment_batch_id"]),
            "driver_id": r["driver_id"],
            "driver_name": r["driver_name"],
            "phone": r["phone"],
            "program_code": r["program_code"],
            "program_name": r["program_name"],
            "priority_rank": r["priority_rank"],
            "assigned_channel": r["assigned_channel"],
            "opportunity_reason": r["opportunity_reason"],
            "last_trip_date": r["last_trip_date"].isoformat()[:10] if r["last_trip_date"] else None,
            "recent_trips": r["recent_trips"],
            "country": r["country"],
            "city": r["city"],
            "park": r["park"],
            "queue_status": r["queue_status"],
        })

    return {
        "date": date_str,
        "total_records": int(summary["cnt"] or 0) if summary else 0,
        "ready_count": int(summary["ready_cnt"] or 0) if summary else 0,
        "held_count": int(summary["held_cnt"] or 0) if summary else 0,
        "records": records,
    }
