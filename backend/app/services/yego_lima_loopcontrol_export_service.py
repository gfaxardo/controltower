"""
YEGO Lima Growth — LoopControl Export Service (Fase LC-1).

Exports prioritized opportunities as DRAFT campaigns to LoopControl.
DRAFT only. No execution. No automation.
"""

from __future__ import annotations
import json
import logging
from datetime import date as date_type, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)


class _JsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (date_type, datetime)):
            return obj.isoformat()
        return super().default(obj)


def make_json_safe(obj):
    """Recursively convert all non-JSON-safe types to native types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date_type, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(v) for v in obj]
    return obj

TABLE_CONFIG = "growth.yango_lima_loopcontrol_config"
TABLE_EXPORT = "growth.yango_lima_loopcontrol_campaign_export"
TABLE_PRIORITIZED = "growth.yango_lima_prioritized_opportunity_daily"


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


def _mask_phone(phone: str) -> str:
    if not phone or len(phone) < 6:
        return "***"
    return phone[:3] + "****" + phone[-2:]


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


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
        cur.execute(f"""
            UPDATE {TABLE_CONFIG}
            SET is_enabled = %(en)s,
                base_url = %(url)s,
                integration_key_configured = %(has_key)s,
                updated_at = now()
            WHERE id = 1
        """, {"en": enabled, "url": base_url, "has_key": bool(key)})

    return {
        "enabled": enabled,
        "base_url_configured": bool(base_url),
        "integration_key_configured": bool(key),
        "mode": "DRY_RUN" if not enabled else "LIVE",
        "issues": issues,
    }


def build_contacts_payload(opportunity_date: str, program_code: str,
                           limit: int = 100) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT o.driver_profile_id, o.selected_program_code,
                   o.lifecycle_state, o.performance_state, o.retention_state,
                   o.completed_orders_week, o.best_week_12w,
                   o.distance_to_target, o.opportunity_score, o.final_rank,
                   o.productivity_bucket, o.value_tier, o.risk_tier,
                   o.completed_orders_30d,
                   d.phone, d.full_name AS driver_name, d.park_id,
                   COALESCE(dp.city, 'Lima') AS city
            FROM {TABLE_PRIORITIZED} o
            LEFT JOIN public.drivers d ON d.driver_id = o.driver_profile_id
            LEFT JOIN dim.dim_park dp ON dp.park_id = d.park_id
            WHERE o.opportunity_date = %(d)s
              AND o.is_actionable_today = true
              AND o.selected_program_code = %(p)s
            ORDER BY o.final_rank ASC
            LIMIT %(lim)s
        """, {"d": opportunity_date, "p": program_code, "lim": min(limit, 500)})
        drivers = [dict(r) for r in cur.fetchall()]

    if not drivers:
        return {"error": "No actionable drivers found", "count": 0}

    contacts = []
    for d in drivers:
        did = d["driver_profile_id"]
        sid = _short_external_id(did)
        phone_raw = (d.get("phone") or "").strip()
        name_raw = (d.get("driver_name") or "").strip()
        contacts.append({
            "external_id": sid,
            "contractor_id": sid,
            "phone": phone_raw,
            "name": name_raw if name_raw else f"Driver {did[:8]}",
            "city": d.get("city", "Lima"),
            "park_id": d.get("park_id", ""),
            "metadata": {
                "driver_profile_id": sid,
                "program": d["selected_program_code"],
                "lifecycle": d.get("lifecycle_state", ""),
                "performance": d.get("performance_state", ""),
                "orders_week": _safe_int(d.get("completed_orders_week")),
                "best_week": _safe_int(d.get("best_week_12w")),
                "orders_30d": _safe_int(d.get("completed_orders_30d")),
                "score": float(d.get("opportunity_score") or 0),
                "rank": _safe_int(d.get("final_rank")),
                "bucket": d.get("productivity_bucket", ""),
            }
        })

    return {
        "program_code": program_code,
        "opportunity_date": opportunity_date,
        "contacts_count": len(contacts),
        "contacts": contacts,
    }


def export_campaign_draft(opportunity_date: str, program_code: str,
                          limit: int = 100,
                          campaign_name: Optional[str] = None,
                          created_by: Optional[str] = None) -> Dict[str, Any]:
    config = validate_loopcontrol_config()
    is_dry_run = not config["enabled"]

    # Build contacts
    payload_result = build_contacts_payload(opportunity_date, program_code, limit)
    if "error" in payload_result:
        return payload_result

    contacts = payload_result["contacts"]
    n_contacts = len(contacts)

    campaign_name = campaign_name or f"{program_code.replace('PROGRAM_','')}_{opportunity_date}"
    description = f"Lima Growth {program_code} — {opportunity_date} — {n_contacts} drivers"

    schedule_days = str(getattr(settings, "LOOPCONTROL_DEFAULT_SCHEDULE_DAYS", None) or "12345").strip()
    campaign_payload = {
        "name": campaign_name,
        "description": description,
        "dialer_mode": "predictive",
        "max_concurrent": 10,
        "max_attempts": 3,
        "ring_timeout": 30,
        "schedule_start": "09:00",
        "schedule_end": "18:00",
        "schedule_days": schedule_days,
        "script": f"Lima Growth {program_code} \u2014 contacto diario de productividad",
        "contacts": [
            _sanitize_contact_fields({
                "external_id": c["external_id"],
                "contractor_id": c["contractor_id"],
                "phone": c["phone"],
                "name": c["name"],
                "metadata": c["metadata"],
            })
            for c in contacts
        ],
    }

    export_id = str(uuid4())
    campaign_id_external = None
    ci_real = 0
    csk_real = 0
    export_status = "draft"
    error_msg = None

    if is_dry_run:
        export_status = "draft_dry_run"
        logger.info("LC DRY_RUN: campaign=%s, contacts=%d, program=%s",
                    campaign_name, n_contacts, program_code)
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
                    logger.info("LC exported: campaign=%s, id=%s, contacts_inserted=%s, contacts_skipped=%s",
                                campaign_name, campaign_id_external, ci_real, csk_real)
                else:
                    export_status = "failed"
                    error_msg = f"LC responded {resp.status_code}: {resp.text[:500]}"
                    logger.error("LC export failed: %s", error_msg)
        except Exception as e:
            export_status = "failed"
            error_msg = str(e)[:500]
            logger.error("LC export error: %s", error_msg)

    # Record export
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_EXPORT} (
                export_id, opportunity_date, campaign_id_external, campaign_name,
                program_code, contacts_sent, contacts_inserted, contacts_skipped,
                export_status, error_message, exported_at, created_by
            ) VALUES (
                %(eid)s, %(od)s, %(cid)s, %(cn)s,
                %(pc)s, %(cs)s, %(ci)s, %(csk)s,
                %(st)s, %(err)s, now(), %(by)s
            )
        """, {
            "eid": export_id, "od": opportunity_date, "cid": campaign_id_external,
            "cn": campaign_name, "pc": program_code,
            "cs": n_contacts, "ci": ci_real,
            "csk": csk_real, "st": export_status, "err": error_msg, "by": created_by,
        })

    return {
        "export_id": export_id,
        "campaign_name": campaign_name,
        "campaign_id_external": campaign_id_external,
        "program_code": program_code,
        "opportunity_date": opportunity_date,
        "contacts_count": n_contacts,
        "contacts_inserted": ci_real,
        "contacts_skipped": csk_real,
        "export_status": export_status,
        "mode": "DRY_RUN" if is_dry_run else "LIVE",
        "error_message": error_msg,
    }


def get_export_history(limit: int = 20) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT export_id, opportunity_date, campaign_id_external, campaign_name,
                   program_code, contacts_sent, contacts_inserted, contacts_skipped,
                   export_status, error_message, exported_at, created_by
            FROM {TABLE_EXPORT}
            ORDER BY exported_at DESC
            LIMIT %(lim)s
        """, {"lim": min(limit, 100)})
        return [_export_to_dict(r) for r in cur.fetchall()]


def get_export_status(export_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM {TABLE_EXPORT} WHERE export_id = %(eid)s",
                    {"eid": export_id})
        r = cur.fetchone()
        if not r:
            return {"error": "Export not found", "export_id": export_id}
        return _export_to_dict(r)


def export_from_contacts(
    contacts: List[Dict[str, Any]],
    opportunity_date: str,
    program_code: str,
    campaign_name: Optional[str] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    config = validate_loopcontrol_config()
    is_dry_run = not config["enabled"]

    n_contacts = len(contacts)
    if n_contacts == 0:
        return {"error": "No contacts provided", "count": 0}

    campaign_name = campaign_name or f"{program_code.replace('PROGRAM_','')}_{opportunity_date}"
    description = f"Lima Growth {program_code} — {opportunity_date} — {n_contacts} drivers"

    schedule_days = str(getattr(settings, "LOOPCONTROL_DEFAULT_SCHEDULE_DAYS", None) or "12345").strip()
    campaign_payload = {
        "name": campaign_name,
        "description": description,
        "dialer_mode": "predictive",
        "max_concurrent": 10,
        "max_attempts": 3,
        "ring_timeout": 30,
        "schedule_start": "09:00",
        "schedule_end": "18:00",
        "schedule_days": schedule_days,
        "script": f"Lima Growth {program_code} \u2014 contacto diario de productividad",
        "contacts": [
            _sanitize_contact_fields({
                "external_id": _short_external_id(c.get("driver_id", c.get("external_id", ""))),
                "contractor_id": _short_external_id(c.get("driver_id", c.get("external_id", ""))),
                "phone": (c.get("phone") or "").strip(),
                "name": (c.get("driver_name") or c.get("name") or "").strip() or f"Driver {c.get('driver_id', '')[:8]}",
                "metadata": {
                    "driver_profile_id": _short_external_id(c.get("driver_id", c.get("external_id", ""))),
                    "program": program_code,
                    "channel": c.get("assigned_channel", c.get("channel", "")),
                    "priority_rank": _safe_int(c.get("priority_rank")),
                },
            })
            for c in contacts
        ],
    }

    export_id = str(uuid4())
    campaign_id_external = None
    ci_real = 0
    csk_real = 0
    export_status = "draft"
    error_msg = None

    if is_dry_run:
        export_status = "draft_dry_run"
        logger.info("LC DRY_RUN (from contacts): campaign=%s, contacts=%d, program=%s",
                    campaign_name, n_contacts, program_code)
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
                    logger.info("LC exported (from contacts): campaign=%s, id=%s, contacts_inserted=%s",
                                campaign_name, campaign_id_external, ci_real)
                else:
                    export_status = "failed"
                    error_msg = f"LC responded {resp.status_code}: {resp.text[:500]}"
                    logger.error("LC export failed: %s", error_msg)
        except Exception as e:
            export_status = "failed"
            error_msg = str(e)[:500]
            logger.error("LC export error: %s", error_msg)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_EXPORT} (
                export_id, opportunity_date, campaign_id_external, campaign_name,
                program_code, contacts_sent, contacts_inserted, contacts_skipped,
                export_status, error_message, exported_at, created_by
            ) VALUES (
                %(eid)s, %(od)s, %(cid)s, %(cn)s,
                %(pc)s, %(cs)s, %(ci)s, %(csk)s,
                %(st)s, %(err)s, now(), %(by)s
            )
        """, {
            "eid": export_id, "od": opportunity_date, "cid": campaign_id_external,
            "cn": campaign_name, "pc": program_code,
            "cs": n_contacts, "ci": ci_real,
            "csk": csk_real, "st": export_status, "err": error_msg, "by": created_by,
        })

    return {
        "export_id": export_id,
        "campaign_name": campaign_name,
        "campaign_id_external": campaign_id_external,
        "program_code": program_code,
        "opportunity_date": opportunity_date,
        "contacts_count": n_contacts,
        "contacts_inserted": ci_real,
        "contacts_skipped": csk_real,
        "export_status": export_status,
        "mode": "DRY_RUN" if is_dry_run else "LIVE",
        "error_message": error_msg,
    }


def _export_to_dict(r) -> Dict[str, Any]:
    return {
        "export_id": str(r["export_id"]),
        "opportunity_date": str(r["opportunity_date"]),
        "campaign_id_external": r.get("campaign_id_external"),
        "campaign_name": r["campaign_name"],
        "program_code": r["program_code"],
        "contacts_sent": _safe_int(r.get("contacts_sent")),
        "contacts_inserted": _safe_int(r.get("contacts_inserted")),
        "contacts_skipped": _safe_int(r.get("contacts_skipped")),
        "export_status": r["export_status"],
        "error_message": r.get("error_message"),
        "exported_at": str(r["exported_at"]) if r.get("exported_at") else None,
        "created_by": r.get("created_by"),
    }
