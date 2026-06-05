"""
YEGO Lima Growth — LoopControl Export Job Service (Fase LC-1.1).

Automated daily DRAFT campaign export with:
- Freshness gate
- Duplicate protection
- Per-program limits
- Job run logging
"""

from __future__ import annotations
import logging
from datetime import date as date_type, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

TABLE_JOB_RUN = "growth.yango_lima_loopcontrol_export_job_run"
TABLE_JOB_PROG = "growth.yango_lima_loopcontrol_export_job_program"
TABLE_EXPORT = "growth.yango_lima_loopcontrol_campaign_export"


def _safe_int(val, default=0):
    if val is None: return default
    try: return int(val)
    except: return int(default)


def get_job_config() -> Dict[str, Any]:
    programs = [p.strip() for p in (settings.LOOPCONTROL_EXPORT_PROGRAMS or "").split(",") if p.strip()]
    limits = {
        "PROGRAM_CHURN_PREVENTION": settings.LOOPCONTROL_LIMIT_CHURN_PREVENTION,
        "PROGRAM_HIGH_VALUE_RECOVERY": settings.LOOPCONTROL_LIMIT_HIGH_VALUE_RECOVERY,
        "PROGRAM_ACTIVE_GROWTH": settings.LOOPCONTROL_LIMIT_ACTIVE_GROWTH,
        "PROGRAM_14_90": settings.LOOPCONTROL_LIMIT_14_90,
    }
    return {
        "auto_export_enabled": settings.LOOPCONTROL_AUTO_EXPORT_ENABLED,
        "export_hour": settings.LOOPCONTROL_EXPORT_HOUR,
        "export_minute": settings.LOOPCONTROL_EXPORT_MINUTE,
        "programs": programs,
        "limits": limits,
        "campaign_prefix": settings.LOOPCONTROL_CAMPAIGN_PREFIX,
        "require_freshness_green": settings.LOOPCONTROL_REQUIRE_FRESHNESS_GREEN,
        "prevent_duplicate_export": settings.LOOPCONTROL_PREVENT_DUPLICATE_EXPORT,
        "export_dry_run": settings.LOOPCONTROL_EXPORT_DRY_RUN,
        "loopcontrol_enabled": settings.LOOPCONTROL_ENABLED,
    }


def validate_job_preconditions(run_date: str) -> Dict[str, Any]:
    issues = []
    warnings = []
    freshness = "unknown"

    if not settings.LOOPCONTROL_ENABLED:
        issues.append("LOOPCONTROL_ENABLED=false — exports will be DRY_RUN only")
    if not (settings.LOOPCONTROL_BASE_URL or "").strip():
        issues.append("LOOPCONTROL_BASE_URL not configured")
    if not (settings.LOOPCONTROL_INTEGRATION_KEY or "").strip():
        issues.append("LOOPCONTROL_INTEGRATION_KEY not configured")

    if settings.LOOPCONTROL_REQUIRE_FRESHNESS_GREEN:
        try:
            from app.services.yego_lima_freshness_service import get_health
            health = get_health()
            freshness = health.get("overall", "unknown")
            if freshness == "RED":
                issues.append(f"Freshness is RED — export blocked (require_freshness_green=true)")
            elif freshness == "YELLOW":
                warnings.append(f"Freshness is YELLOW — proceed with caution")
        except Exception as e:
            warnings.append(f"Freshness check failed: {e}")

    # Check prioritized opportunities exist
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM growth.yango_lima_prioritized_opportunity_daily WHERE opportunity_date = %(d)s AND is_actionable_today = true", {"d": run_date})
        n = cur.fetchone()[0]
        if n == 0:
            warnings.append(f"No actionable prioritized opportunities for {run_date}")

    return {
        "can_proceed": len(issues) == 0,
        "freshness_status": freshness,
        "issues": issues,
        "warnings": warnings,
    }


def _is_duplicate(run_date: str, program_code: str) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT COUNT(*) as n FROM {TABLE_JOB_PROG} jp
            JOIN {TABLE_JOB_RUN} jr ON jr.job_run_id = jp.job_run_id
            WHERE jr.run_date = %(d)s AND jp.program_code = %(p)s
              AND jp.status = 'exported'
        """, {"d": run_date, "p": program_code})
        return cur.fetchone()[0] > 0


def run_export_job(run_date: str, programs: Optional[List[str]] = None,
                   dry_run: Optional[bool] = None,
                   force: bool = False,
                   triggered_by: str = "manual") -> Dict[str, Any]:
    if dry_run is None:
        dry_run = settings.LOOPCONTROL_EXPORT_DRY_RUN
    if not settings.LOOPCONTROL_ENABLED:
        dry_run = True

    programs = programs or [p.strip() for p in (settings.LOOPCONTROL_EXPORT_PROGRAMS or "").split(",") if p.strip()]
    job_run_id = str(uuid4())

    limits = {
        "PROGRAM_CHURN_PREVENTION": settings.LOOPCONTROL_LIMIT_CHURN_PREVENTION,
        "PROGRAM_HIGH_VALUE_RECOVERY": settings.LOOPCONTROL_LIMIT_HIGH_VALUE_RECOVERY,
        "PROGRAM_ACTIVE_GROWTH": settings.LOOPCONTROL_LIMIT_ACTIVE_GROWTH,
        "PROGRAM_14_90": settings.LOOPCONTROL_LIMIT_14_90,
    }

    # Validate preconditions
    preconditions = validate_job_preconditions(run_date)
    if not preconditions["can_proceed"] and not force:
        return {
            "job_run_id": job_run_id,
            "run_date": run_date,
            "status": "blocked",
            "dry_run": dry_run,
            "preconditions": preconditions,
            "message": "Preconditions not met. Use force=true to override.",
        }

    # Create job run
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_JOB_RUN} (
                job_run_id, run_date, status, triggered_by, dry_run,
                freshness_status, programs_requested
            ) VALUES (
                %(jid)s, %(d)s, 'running', %(by)s, %(dr)s,
                %(fs)s, %(pr)s
            )
        """, {
            "jid": job_run_id, "d": run_date, "by": triggered_by, "dr": dry_run,
            "fs": preconditions["freshness_status"], "pr": programs,
        })

    warnings_list = []
    errors_list = []
    total_sent = 0
    total_inserted = 0
    total_skipped = 0
    exports_created = 0
    program_results = []

    for prog in programs:
        limit = limits.get(prog, 100)
        prefix = (settings.LOOPCONTROL_CAMPAIGN_PREFIX or "YEGO_LIMA").strip()
        campaign_name = f"{prefix}_{prog.replace('PROGRAM_','')}_{run_date}"

        # Duplicate check
        if settings.LOOPCONTROL_PREVENT_DUPLICATE_EXPORT and _is_duplicate(run_date, prog) and not force:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    INSERT INTO {TABLE_JOB_PROG} (
                        job_run_id, program_code, campaign_name, limit_requested,
                        contacts_sent, status, error_message
                    ) VALUES (%(jid)s, %(pc)s, %(cn)s, %(lim)s, 0, 'skipped_duplicate', 'Already exported')
                """, {"jid": job_run_id, "pc": prog, "cn": campaign_name, "lim": limit})
            program_results.append({"program": prog, "status": "skipped_duplicate", "contacts": 0})
            total_skipped += 1
            continue

        # Export
        try:
            from app.services.yego_lima_loopcontrol_export_service import export_campaign_draft
            result = export_campaign_draft(run_date, prog, limit, campaign_name, triggered_by)

            status = result.get("export_status", "failed")
            contacts = result.get("contacts_count", 0)
            export_id = result.get("export_id")
            campaign_ext_id = result.get("campaign_id_external")
            err = result.get("error_message")

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    INSERT INTO {TABLE_JOB_PROG} (
                        job_run_id, program_code, campaign_name, export_id,
                        campaign_id_external, limit_requested,
                        contacts_sent, contacts_inserted, contacts_skipped,
                        status, error_message
                    ) VALUES (
                        %(jid)s, %(pc)s, %(cn)s, %(eid)s,
                        %(cid)s, %(lim)s,
                        %(cs)s, %(ci)s, %(csk)s,
                        %(st)s, %(err)s
                    )
                """, {
                    "jid": job_run_id, "pc": prog, "cn": campaign_name,
                    "eid": export_id, "cid": campaign_ext_id, "lim": limit,
                    "cs": contacts, "ci": contacts if status in ("exported", "draft_dry_run") else 0,
                    "csk": 0, "st": status, "err": err,
                })

            total_sent += contacts
            if status in ("exported", "draft_dry_run"):
                total_inserted += contacts
                exports_created += 1
            program_results.append({"program": prog, "status": status, "contacts": contacts, "export_id": export_id})

        except Exception as e:
            err_msg = str(e)[:500]
            errors_list.append({"program": prog, "error": err_msg})
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(f"""
                    INSERT INTO {TABLE_JOB_PROG} (
                        job_run_id, program_code, campaign_name, limit_requested,
                        contacts_sent, status, error_message
                    ) VALUES (%(jid)s, %(pc)s, %(cn)s, %(lim)s, 0, 'failed', %(err)s)
                """, {"jid": job_run_id, "pc": prog, "cn": campaign_name, "lim": limit, "err": err_msg})
            program_results.append({"program": prog, "status": "failed", "error": err_msg})

    # Close job run
    job_status = "completed" if not errors_list else "completed_with_errors"
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_JOB_RUN}
            SET status = %(st)s, finished_at = now(),
                total_contacts_sent = %(ts)s, total_contacts_inserted = %(ti)s,
                total_contacts_skipped = %(tks)s, exports_created = %(ec)s,
                warnings = %(w)s::jsonb, errors = %(e)s::jsonb,
                summary = %(sm)s::jsonb
            WHERE job_run_id = %(jid)s
        """, {
            "jid": job_run_id, "st": job_status,
            "ts": total_sent, "ti": total_inserted, "tks": total_skipped, "ec": exports_created,
            "w": __import__("json").dumps(warnings_list or []),
            "e": __import__("json").dumps(errors_list or []),
            "sm": __import__("json").dumps(program_results),
        })

    return {
        "job_run_id": job_run_id,
        "run_date": run_date,
        "status": job_status,
        "dry_run": dry_run,
        "programs_requested": programs,
        "total_contacts_sent": total_sent,
        "total_contacts_inserted": total_inserted,
        "exports_created": exports_created,
        "freshness_status": preconditions["freshness_status"],
        "programs": program_results,
        "warnings": preconditions["warnings"],
    }


def get_job_history(limit: int = 20) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"""
            SELECT * FROM {TABLE_JOB_RUN}
            ORDER BY started_at DESC LIMIT %(lim)s
        """, {"lim": min(limit, 100)})
        return [_job_to_dict(r) for r in cur.fetchall()]


def get_job_run_detail(job_run_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM {TABLE_JOB_RUN} WHERE job_run_id = %(jid)s", {"jid": job_run_id})
        jr = cur.fetchone()
        if not jr:
            return {"error": "Job run not found"}

        cur.execute(f"SELECT * FROM {TABLE_JOB_PROG} WHERE job_run_id = %(jid)s ORDER BY program_code", {"jid": job_run_id})
        programs = [_prog_to_dict(r) for r in cur.fetchall()]

        result = _job_to_dict(jr)
        result["programs"] = programs
        return result


def _job_to_dict(r) -> Dict[str, Any]:
    return {
        "job_run_id": str(r["job_run_id"]),
        "run_date": str(r["run_date"]),
        "started_at": str(r["started_at"]) if r.get("started_at") else None,
        "finished_at": str(r["finished_at"]) if r.get("finished_at") else None,
        "status": r["status"],
        "triggered_by": r.get("triggered_by", "manual"),
        "dry_run": r.get("dry_run", False),
        "freshness_status": r.get("freshness_status"),
        "programs_requested": r.get("programs_requested"),
        "total_contacts_sent": _safe_int(r.get("total_contacts_sent")),
        "total_contacts_inserted": _safe_int(r.get("total_contacts_inserted")),
        "total_contacts_skipped": _safe_int(r.get("total_contacts_skipped")),
        "exports_created": _safe_int(r.get("exports_created")),
        "warnings": r.get("warnings"),
        "errors": r.get("errors"),
    }


def _prog_to_dict(r) -> Dict[str, Any]:
    return {
        "program_code": r["program_code"],
        "campaign_name": r.get("campaign_name"),
        "export_id": str(r["export_id"]) if r.get("export_id") else None,
        "campaign_id_external": r.get("campaign_id_external"),
        "limit_requested": _safe_int(r.get("limit_requested")),
        "contacts_sent": _safe_int(r.get("contacts_sent")),
        "contacts_inserted": _safe_int(r.get("contacts_inserted")),
        "contacts_skipped": _safe_int(r.get("contacts_skipped")),
        "status": r["status"],
        "error_message": r.get("error_message"),
    }
