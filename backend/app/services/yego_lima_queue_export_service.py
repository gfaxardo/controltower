"""
YEGO Lima Growth — Assignment Queue Export Service (LC-1.5 V1).

Exports READY records from growth.yego_lima_assignment_queue to LoopControl.
NO recalculo. NO worklist. NO HELD. NO medicion de resultados.
"""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

TABLE_QUEUE = "growth.yego_lima_assignment_queue"
TABLE_CONFIG = "growth.yango_lima_loopcontrol_config"
TABLE_EXPORT = "growth.yango_lima_loopcontrol_campaign_export"


def _short_external_id(driver_profile_id: str) -> str:
    alpha = "".join(c for c in (driver_profile_id or "") if c.isalnum())
    if not alpha:
        return "UNKNOWN"
    return alpha[:20]


def _sanitize_contact_fields(contact: Dict[str, Any]) -> Dict[str, Any]:
    LIMITS = {
        "external_id": 20,
        "contractor_id": 20,
        "document": 20,
        "phone": 20,
        "park_id": 50,
        "city": 50,
        "name": 120,
    }
    sanitized = dict(contact)
    for field, max_len in LIMITS.items():
        val = sanitized.get(field)
        if isinstance(val, str) and len(val) > max_len:
            sanitized[field] = val[:max_len]
    return sanitized


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except Exception:
        return int(default)


def make_json_safe(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date_type, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(v) for v in obj]
    return obj


def validate_loopcontrol_config() -> Dict[str, Any]:
    enabled = settings.LOOPCONTROL_ENABLED
    base_url = (settings.LOOPCONTROL_BASE_URL or "").strip()
    key = (settings.LOOPCONTROL_INTEGRATION_KEY or "").strip()

    issues = []
    if not enabled:
        issues.append("LOOPCONTROL_ENABLED=false — DRY_RUN mode, no external calls")
    if not base_url:
        issues.append("LOOPCONTROL_BASE_URL not configured")
    if not key:
        issues.append("LOOPCONTROL_INTEGRATION_KEY not configured")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE {TABLE_CONFIG}
            SET is_enabled = %(en)s,
                base_url = %(url)s,
                integration_key_configured = %(has_key)s,
                updated_at = now()
            WHERE id = 1
        """,
            {"en": enabled, "url": base_url, "has_key": bool(key)},
        )

    return {
        "enabled": enabled,
        "base_url_configured": bool(base_url),
        "integration_key_configured": bool(key),
        "mode": "DRY_RUN" if not enabled else "LIVE",
        "issues": issues,
    }


def export_ready_queue_to_loopcontrol(
    date_str: str,
    program: Optional[str] = None,
    channel: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    export_batch_id = str(uuid4())
    max_limit = min(limit, 500) if limit else 500

    conditions = [
        "assignment_date = %(d)s",
        "queue_status = 'READY'",
        "phone IS NOT NULL",
        "phone != ''",
        "assigned_channel IS NOT NULL",
        "assigned_channel != 'UNASSIGNED'",
    ]
    params: Dict[str, Any] = {"d": date_str}

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
            f"SELECT COUNT(*) as cnt FROM {TABLE_QUEUE} WHERE {where}",
            params,
        )
        candidate_cnt = cur.fetchone()["cnt"]

        cur.execute(
            f"SELECT * FROM {TABLE_QUEUE} WHERE {where} "
            f"ORDER BY priority_rank ASC NULLS LAST, recent_trips ASC NULLS LAST, driver_name ASC NULLS LAST "
            f"LIMIT %(lim)s",
            {**params, "lim": max_limit},
        )
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return {
            "export_batch_id": export_batch_id,
            "assignment_date": date_str,
            "campaign_id_external": None,
            "selected_count": 0,
            "exported_count": 0,
            "skipped_count": 0,
            "skipped_reasons": {
                "missing_phone": 0,
                "unassigned_channel": 0,
                "already_exported": 0,
            },
        }

    contacts = []
    for r in rows:
        did = r["driver_id"]
        sid = _short_external_id(did)
        phone_raw = (r.get("phone") or "").strip()
        name_raw = (r.get("driver_name") or "").strip()
        contacts.append(
            {
                "external_id": sid,
                "contractor_id": sid,
                "phone": phone_raw,
                "name": name_raw if name_raw else f"Driver {did[:8]}",
                "city": r.get("city", "Lima"),
                "park_id": r.get("park", ""),
                "metadata": {
                    "driver_profile_id": sid,
                    "program": r["program_code"],
                    "priority_rank": _safe_int(r.get("priority_rank")),
                    "queue_id": str(r["id"]),
                },
            }
        )

    n_contacts = len(contacts)
    program_label = (program or "MULTI").replace("PROGRAM_", "")
    campaign_name = f"YEGO_LIMA_{program_label}_{date_str}"

    config = validate_loopcontrol_config()
    is_dry_run = not config["enabled"]

    schedule_days = str(
        getattr(settings, "LOOPCONTROL_DEFAULT_SCHEDULE_DAYS", None) or "12345"
    ).strip()
    campaign_payload = {
        "name": campaign_name,
        "description": f"Lima Growth Queue Export — {date_str} — {n_contacts} drivers",
        "dialer_mode": "predictive",
        "max_concurrent": 10,
        "max_attempts": 3,
        "ring_timeout": 30,
        "schedule_start": "09:00",
        "schedule_end": "18:00",
        "schedule_days": schedule_days,
        "script": f"Lima Growth {program_label} \u2014 contacto diario de productividad",
        "contacts": [
            _sanitize_contact_fields(
                {
                    "external_id": c["external_id"],
                    "contractor_id": c["contractor_id"],
                    "phone": c["phone"],
                    "name": c["name"],
                    "metadata": c["metadata"],
                }
            )
            for c in contacts
        ],
    }

    campaign_id_external = None
    ci_real = 0
    csk_real = 0
    export_status = "draft"
    error_msg = None

    if is_dry_run:
        export_status = "draft_dry_run"
        logger.info(
            "LC QUEUE DRY_RUN: campaign=%s, contacts=%d, batch=%s",
            campaign_name,
            n_contacts,
            export_batch_id,
        )
    else:
        try:
            import httpx

            base_url = (settings.LOOPCONTROL_BASE_URL or "").strip().rstrip("/")
            key = (settings.LOOPCONTROL_INTEGRATION_KEY or "").strip()

            if not base_url or not key:
                export_status = "failed"
                error_msg = "Missing base_url or integration_key"
            else:
                safe_payload = make_json_safe(campaign_payload)
                resp = httpx.post(
                    f"{base_url}/callcenter/campaigns/external",
                    json=safe_payload,
                    headers={"X-Integration-Key": key},
                    timeout=30,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    campaign_id_external = (
                        data.get("id")
                        or data.get("campaign_id")
                        or data.get("data", {}).get("campaign", {}).get("id")
                    )
                    ci_real = (
                        data.get("contacts_inserted")
                        or data.get("data", {}).get("contacts_inserted")
                        or n_contacts
                    )
                    csk_real = (
                        data.get("contacts_skipped")
                        or data.get("data", {}).get("contacts_skipped")
                        or 0
                    )
                    export_status = "exported"
                    logger.info(
                        "LC QUEUE exported: campaign=%s, id=%s, inserted=%s, skipped=%s",
                        campaign_name,
                        campaign_id_external,
                        ci_real,
                        csk_real,
                    )
                else:
                    export_status = "failed"
                    error_msg = f"LC responded {resp.status_code}: {resp.text[:500]}"
                    logger.error("LC QUEUE export failed: %s", error_msg)
        except Exception as e:
            export_status = "failed"
            error_msg = str(e)[:500]
            logger.error("LC QUEUE export error: %s", error_msg)

    record_export_id = str(uuid4())

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            f"""
            INSERT INTO {TABLE_EXPORT} (
                export_id, opportunity_date, campaign_id_external, campaign_name,
                program_code, contacts_sent, contacts_inserted, contacts_skipped,
                export_status, error_message, exported_at, created_by
            ) VALUES (
                %(eid)s, %(od)s, %(cid)s, %(cn)s,
                %(pc)s, %(cs)s, %(ci)s, %(csk)s,
                %(st)s, %(err)s, now(), %(by)s
            )
        """,
            {
                "eid": record_export_id,
                "od": date_str,
                "cid": campaign_id_external,
                "cn": campaign_name,
                "pc": program or "MULTI",
                "cs": n_contacts,
                "ci": ci_real,
                "csk": csk_real,
                "st": export_status,
                "err": error_msg,
                "by": "queue_export",
            },
        )

        row_ids = [str(r["id"]) for r in rows]
        cur.execute(
            f"""
            UPDATE {TABLE_QUEUE}
            SET queue_status = 'EXPORTED',
                exported_at = now(),
                campaign_id_external = %(cid)s,
                export_batch_id = %(bid)s,
                updated_at = now()
            WHERE id::text = ANY(%(ids)s)
        """,
            {"cid": campaign_id_external, "bid": export_batch_id, "ids": row_ids},
        )

        conn.commit()

    return {
        "export_batch_id": export_batch_id,
        "assignment_date": date_str,
        "campaign_id_external": campaign_id_external,
        "selected_count": n_contacts,
        "exported_count": n_contacts,
        "skipped_count": 0,
        "skipped_reasons": {
            "missing_phone": 0,
            "unassigned_channel": 0,
            "already_exported": 0,
        },
    }
