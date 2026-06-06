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

    with get_db() as conn:
        cur = conn.cursor()

        for r in records:
            phone_val = r.get("phone")
            chan = r.get("assigned_channel", "")

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
                    f"ON CONFLICT ON CONSTRAINT idx_aq_unique_driver_program_date DO NOTHING",
                    {
                        "bid": batch_id,
                        "d": date_str,
                        "did": r["driver_id"],
                        "dn": r.get("driver_name"),
                        "ph": phone_val,
                        "pc": r["program_code"],
                        "pn": r.get("program_name"),
                        "pr": r.get("priority_rank"),
                        "ch": chan,
                        "or": r.get("opportunity_reason"),
                        "ltd": r.get("last_trip_date"),
                        "rt": r.get("recent_trips"),
                        "co": r.get("country"),
                        "ci": r.get("city"),
                        "pa": r.get("park"),
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
                logger.warning(f"Insert skipped for driver {r.get('driver_id')}: {e}")
                skipped += 1

        conn.commit()

    return {
        "assignment_batch_id": batch_id,
        "assignment_date": date_str,
        "created_count": created,
        "ready_count": ready,
        "held_count": held,
        "skipped_duplicates": skipped,
    }


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
