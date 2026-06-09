"""
YEGO Lima Growth — Result Sync Service (LG-C2.0)

Receives LoopControl campaign results and links them to exported contacts.
Uses dedicated loopcontrol_result_sync table (migration 184).
Matches by campaign_id_external + phone. Idempotent.
No Impact. No Movement. No Attribution. No ROI.
"""
from __future__ import annotations
import logging, json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_RESULT = "growth.yego_lima_loopcontrol_result_sync"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"


def _normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    return phone.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")


def sync_results(payload: Dict[str, Any]) -> Dict[str, Any]:
    campaign_id = str(payload.get("campaign_id_external", ""))
    results = payload.get("results", [])

    if not campaign_id or not results:
        return {"success": False, "error": "campaign_id_external and results[] required"}

    matched = 0
    unmatched = 0
    inserted = 0
    updated = 0

    with get_db() as conn:
        cur = conn.cursor()

        for r in results:
            phone_raw = r.get("phone", "")
            phone = _normalize_phone(phone_raw)
            status = r.get("status", "")
            disposition = r.get("disposition", "")
            contact_id = r.get("contact_id", "")
            attempts = r.get("attempts", 0)
            last_call_at = r.get("last_call_at")
            notes = r.get("notes", "")
            agent = r.get("agent", "")

            # Match to queue by campaign + phone
            cur.execute(f"""
                SELECT id, driver_id, program_code, assigned_channel, export_batch_id
                FROM {TABLE_QUEUE}
                WHERE campaign_id_external = %(cid)s AND phone = %(ph)s
                LIMIT 1
            """, {"cid": campaign_id, "ph": phone_raw})
            queue_match = cur.fetchone()

            queue_id = None
            driver_id = None
            program_code = None
            channel = None
            batch_id = None
            match_status = "UNMATCHED"

            if queue_match:
                queue_id = queue_match[0]
                driver_id = queue_match[1]
                program_code = queue_match[2]
                channel = queue_match[3]
                batch_id = str(queue_match[4]) if queue_match[4] else None
                match_status = "MATCHED"
                matched += 1
            else:
                unmatched += 1

            # Upsert into dedicated result table (manual: no UNIQUE constraint on table)
            cur.execute(f"""
                SELECT id FROM {TABLE_RESULT}
                WHERE campaign_id_external = %(cid)s AND phone = %(ph)s
            """, {"cid": campaign_id, "ph": phone_raw})
            existing = cur.fetchone()

            if existing:
                cur.execute(f"""
                    UPDATE {TABLE_RESULT} SET
                        contact_id = %(ctid)s,
                        assignment_queue_id = COALESCE(%(qid)s::uuid, assignment_queue_id),
                        driver_id = COALESCE(%(did)s, driver_id),
                        attempts = %(att)s,
                        status = %(st)s,
                        disposition = %(disp)s,
                        last_call_at = %(lca)s::timestamptz,
                        notes = %(n)s,
                        agent = %(ag)s,
                        raw_payload = %(raw)s::jsonb,
                        synced_at = now(),
                        updated_at = now()
                    WHERE campaign_id_external = %(cid)s AND phone = %(ph)s
                """, {
                    "ctid": contact_id, "qid": queue_id, "did": driver_id,
                    "att": attempts, "st": status, "disp": disposition,
                    "lca": last_call_at, "n": notes, "ag": agent,
                    "raw": json.dumps(r, default=str), "cid": campaign_id, "ph": phone_raw,
                })
                updated += 1
            else:
                cur.execute(f"""
                    INSERT INTO {TABLE_RESULT}
                        (campaign_id_external, contact_id, phone, assignment_queue_id,
                         export_batch_id, driver_id, attempts, status, disposition,
                         last_call_at, notes, agent, raw_payload, synced_at)
                    VALUES (%(cid)s, %(ctid)s, %(ph)s, %(qid)s,
                            %(bid)s, %(did)s, %(att)s, %(st)s, %(disp)s,
                            %(lca)s::timestamptz, %(n)s, %(ag)s, %(raw)s::jsonb, now())
                """, {
                    "cid": campaign_id, "ctid": contact_id, "ph": phone_raw,
                    "qid": queue_id, "bid": batch_id, "did": driver_id,
                    "att": attempts, "st": status, "disp": disposition,
                    "lca": last_call_at, "n": notes, "ag": agent,
                    "raw": json.dumps(r, default=str),
                })
                inserted += 1

            if cur.rowcount > 0:
                if match_status == "MATCHED":
                    updated += 1
                else:
                    inserted += 1

        conn.commit()

    return {
        "success": True,
        "campaign_id_external": campaign_id,
        "received_count": len(results),
        "matched": matched,
        "unmatched": unmatched,
        "inserted": inserted,
        "updated": updated,
    }


def get_result_summary(campaign_id_external: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_RESULT} WHERE campaign_id_external = %(cid)s", {"cid": campaign_id_external})
        total = cur.fetchone()[0] or 0

        cur.execute(f"""
            SELECT COUNT(*) FROM {TABLE_RESULT}
            WHERE campaign_id_external = %(cid)s AND assignment_queue_id IS NOT NULL
        """, {"cid": campaign_id_external})
        matched_q = cur.fetchone()[0] or 0

        cur.execute(f"""
            SELECT status, COUNT(*) FROM {TABLE_RESULT}
            WHERE campaign_id_external = %(cid)s GROUP BY status
        """, {"cid": campaign_id_external})
        by_status = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute(f"""
            SELECT disposition, COUNT(*) FROM {TABLE_RESULT}
            WHERE campaign_id_external = %(cid)s GROUP BY disposition
        """, {"cid": campaign_id_external})
        by_disposition = {r[0] or 'NULL': r[1] for r in cur.fetchall()}

        cur.execute(f"SELECT MAX(synced_at) FROM {TABLE_RESULT} WHERE campaign_id_external = %(cid)s", {"cid": campaign_id_external})
        last_sync = cur.fetchone()[0]

    return {
        "campaign_id_external": campaign_id_external,
        "total_results": total,
        "matched_queue_count": matched_q,
        "unmatched_count": total - matched_q,
        "by_status": by_status,
        "by_disposition": by_disposition,
        "contacted_count": by_status.get("CONTACTED", 0),
        "interested_count": by_disposition.get("INTERESTED", 0),
        "no_answer_count": by_status.get("NO_ANSWER", 0),
        "last_sync_at": last_sync.isoformat() if last_sync else None,
    }


def get_result_records(campaign_id_external: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_RESULT} WHERE campaign_id_external = %(cid)s", {"cid": campaign_id_external})
        total = cur.fetchone()[0] or 0

        cur.execute(f"""
            SELECT r.contact_id, r.phone, r.driver_id, r.status, r.disposition,
                   r.attempts, r.last_call_at, r.agent, r.notes, r.assignment_queue_id,
                   aq.program_code, aq.assigned_channel, aq.driver_name
            FROM {TABLE_RESULT} r
            LEFT JOIN {TABLE_QUEUE} aq ON r.assignment_queue_id = aq.id
            WHERE r.campaign_id_external = %(cid)s
            ORDER BY r.synced_at DESC
            LIMIT %(lim)s OFFSET %(off)s
        """, {"cid": campaign_id_external, "lim": min(limit, 500), "off": offset})
        records = []
        for r in cur.fetchall():
            records.append({
                "contact_id": r[0], "phone": r[1], "driver_id": r[2] or '',
                "status": r[3] or '', "disposition": r[4] or '',
                "attempts": r[5] or 0, "last_call_at": r[6].isoformat() if r[6] else None,
                "agent": r[7] or '', "notes": r[8] or '',
                "program_code": r[10] or '', "assigned_channel": r[11] or '',
                "driver_name": r[12] or '',
                "matched": r[9] is not None,
            })

    return {"campaign_id_external": campaign_id_external, "total": total, "limit": limit, "offset": offset, "records": records}
