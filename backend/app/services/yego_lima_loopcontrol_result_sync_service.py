"""
YEGO Lima Growth — LoopControl Result Sync Service (Fase LC-2A).

Minimal implementation. Reads campaign results from existing
growth.yango_lima_loopcontrol_campaign_export table.
Result payload stored as JSON in error_message field
(no schema changes per governance rules).

LC-2 plan (pending Miguel's endpoint):
  - Pull campaign results from LoopControl
  - Write to dedicated result table
  - Expose via result sync endpoints
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_EXPORT = "growth.yango_lima_loopcontrol_campaign_export"


def sync_campaign_results(
    campaign_id_external: int,
    calls_made: int = 0,
    calls_answered: int = 0,
    outcomes: Optional[Dict[str, int]] = None,
    synced_by: Optional[str] = None,
) -> Dict[str, Any]:
    result_payload = {
        "calls_made": calls_made,
        "calls_answered": calls_answered,
        "outcomes": outcomes or {},
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "synced_by": synced_by or "manual",
    }
    result_json = json.dumps(result_payload, ensure_ascii=False)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"SELECT export_id, campaign_id_external, campaign_name, contacts_inserted "
            f"FROM {TABLE_EXPORT} WHERE campaign_id_external = %(cid)s",
            {"cid": str(campaign_id_external)},
        )
        rows = cur.fetchall()

        if not rows:
            return {
                "synced": False,
                "campaign_id_external": campaign_id_external,
                "error": f"Campaign {campaign_id_external} not found in export history",
            }

        updated = 0
        for r in rows:
            cur.execute(
                f"UPDATE {TABLE_EXPORT} SET error_message = %(res)s "
                f"WHERE export_id = %(eid)s",
                {"res": result_json, "eid": r["export_id"]},
            )
            updated += 1

    logger.info(
        "LC result sync: campaign=%s, exports_updated=%s, calls_made=%s, calls_answered=%s",
        campaign_id_external, updated, calls_made, calls_answered,
    )

    return {
        "synced": True,
        "campaign_id_external": campaign_id_external,
        "exports_updated": updated,
        "calls_made": calls_made,
        "calls_answered": calls_answered,
        "outcomes": outcomes or {},
    }


def get_results_summary(campaign_id_external: Optional[int] = None) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        params = {}
        where = ""
        if campaign_id_external:
            where = "WHERE campaign_id_external = %(cid)s"
            params["cid"] = str(campaign_id_external)

        cur.execute(
            f"SELECT COUNT(*) as total_exports, "
            f"SUM(contacts_sent) as total_contacts_sent, "
            f"SUM(contacts_inserted) as total_contacts_inserted, "
            f"SUM(contacts_skipped) as total_contacts_skipped, "
            f"COUNT(CASE WHEN export_status = 'exported' THEN 1 END) as successful_exports, "
            f"COUNT(CASE WHEN export_status = 'failed' THEN 1 END) as failed_exports "
            f"FROM {TABLE_EXPORT} {where}",
            params,
        )
        r = cur.fetchone()

        cur.execute(
            f"SELECT COUNT(DISTINCT opportunity_date) as days_with_exports "
            f"FROM {TABLE_EXPORT} {where}",
            params,
        )
        days = cur.fetchone()

        cur.execute(
            f"SELECT program_code, COUNT(*) as count, "
            f"SUM(contacts_inserted) as contacts "
            f"FROM {TABLE_EXPORT} {where} "
            f"GROUP BY program_code ORDER BY count DESC",
            params,
        )
        by_program = [dict(row) for row in cur.fetchall()]

    synced_campaigns = 0
    if campaign_id_external:
        cur.execute(
            f"SELECT COUNT(*) as cnt FROM {TABLE_EXPORT} "
            f"WHERE campaign_id_external = %(cid)s AND error_message IS NOT NULL "
            f"AND error_message LIKE %(p)s",
            {"cid": str(campaign_id_external), "p": '%%"synced_at"%%'},
        )
        synced_campaigns = cur.fetchone()["cnt"]

    return {
        "total_exports": r["total_exports"] or 0,
        "successful_exports": r["successful_exports"] or 0,
        "failed_exports": r["failed_exports"] or 0,
        "total_contacts_sent": r["total_contacts_sent"] or 0,
        "total_contacts_inserted": r["total_contacts_inserted"] or 0,
        "total_contacts_skipped": r["total_contacts_skipped"] or 0,
        "days_with_exports": days["days_with_exports"] or 0,
        "synced_campaigns": synced_campaigns,
        "by_program": by_program,
    }


def get_results(
    campaign_id_external: Optional[int] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        params = {"lim": min(limit, 100)}
        where = ""
        if campaign_id_external:
            where = "WHERE campaign_id_external = %(cid)s"
            params["cid"] = str(campaign_id_external)

        cur.execute(
            f"SELECT export_id, opportunity_date, campaign_id_external, campaign_name, "
            f"program_code, contacts_sent, contacts_inserted, contacts_skipped, "
            f"export_status, error_message, exported_at, created_by "
            f"FROM {TABLE_EXPORT} {where} "
            f"ORDER BY exported_at DESC LIMIT %(lim)s",
            params,
        )
        rows = cur.fetchall()

    results = []
    for r in rows:
        result_data = None
        err_msg = r.get("error_message")
        if err_msg:
            try:
                parsed = json.loads(err_msg)
                if "synced_at" in parsed:
                    result_data = parsed
            except (json.JSONDecodeError, TypeError):
                pass

        results.append({
            "export_id": str(r["export_id"]),
            "opportunity_date": str(r["opportunity_date"]),
            "campaign_id_external": r["campaign_id_external"],
            "campaign_name": r["campaign_name"],
            "program_code": r["program_code"],
            "contacts_sent": int(r["contacts_sent"] or 0),
            "contacts_inserted": int(r["contacts_inserted"] or 0),
            "contacts_skipped": int(r["contacts_skipped"] or 0),
            "export_status": r["export_status"],
            "result_data": result_data,
            "exported_at": str(r["exported_at"]) if r.get("exported_at") else None,
            "created_by": r.get("created_by"),
        })

    return results
