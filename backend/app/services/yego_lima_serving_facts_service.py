"""
YEGO Lima Growth — Serving Facts Service (LG-UX-R2.9H)

Generates and reads serving facts (pre-computed snapshots per date).
Eliminates heavy runtime calculations from UI-facing endpoints.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_FACT = "growth.yego_lima_serving_fact"
TABLE_FALLBACK_AUDIT = "growth.yego_lima_runtime_fallback_audit"


def _now():
    return datetime.now(timezone.utc)


def _ensure_fallback_audit_table():
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS growth.yego_lima_runtime_fallback_audit (
                    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    endpoint        text NOT NULL,
                    fact_type       text NOT NULL,
                    fact_date       date NOT NULL,
                    source          text NOT NULL,
                    triggered_by    text DEFAULT 'system',
                    duration_ms     integer,
                    created_at      timestamptz NOT NULL DEFAULT now()
                )
            """)
            conn.commit()
    except Exception:
        pass


# ── STRICT SERVING-FIRST HELPER (R2.9H.1) ──

def serving_or_missing(fact_date: str, fact_type: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Strict serving-first contract:
    - If fact exists: return with source=SERVING_FACT
    - If fact missing AND force_refresh=false: return MISSING_SERVING_FACT
    - If force_refresh=true: caller must handle runtime fallback
    """
    fact = __get_fact_raw(fact_date, fact_type)

    if fact:
        return {
            "status": "OK",
            "source": "SERVING_FACT",
            "generated_at": fact["generated_at"],
            "payload": fact["data"],
        }

    if force_refresh:
        return {
            "status": "OK",
            "source": "RUNTIME_FORCE_REFRESH",
            "generated_at": None,
            "payload": None,  # caller fills this
        }

    return {
        "status": "MISSING_SERVING_FACT",
        "source": "NONE",
        "payload": None,
        "generated_at": None,
        "remediation": "Run Lima Growth refresh pipeline to generate serving facts.",
        "retry_available": True,
        "force_refresh_available": True,
    }


def __get_fact_raw(fact_date: str, fact_type: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT payload, generated_at, freshness_status FROM {TABLE_FACT} "
            f"WHERE fact_date = %(d)s AND fact_type = %(t)s",
            {"d": fact_date, "t": fact_type}
        )
        row = cur.fetchone()
        if row:
            return {
                "data": row[0],
                "generated_at": row[1].isoformat() if row[1] else None,
                "freshness_status": row[2],
            }
    return None


def audit_force_refresh(endpoint: str, fact_type: str, fact_date: str,
                         source: str, duration_ms: int = None):
    _ensure_fallback_audit_table()
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE_FALLBACK_AUDIT} (endpoint, fact_type, fact_date, source, duration_ms, triggered_by) "
                f"VALUES (%(e)s, %(ft)s, %(fd)s, %(s)s, %(d)s, 'api')",
                {"e": endpoint, "ft": fact_type, "fd": fact_date, "s": source, "d": duration_ms}
            )
            conn.commit()
    except Exception:
        logger.warning("Failed to write force_refresh audit", exc_info=True)


def _now():
    return datetime.now(timezone.utc)


def save_serving_fact(fact_date: str, fact_type: str, payload: Dict[str, Any],
                      source_run_id: str = None, freshness_status: str = None):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE_FACT} (fact_date, fact_type, payload, source_run_id, freshness_status) "
            f"VALUES (%(d)s, %(t)s, %(p)s, %(rid)s, %(fs)s) "
            f"ON CONFLICT (fact_date, fact_type) DO UPDATE SET "
            f"payload = EXCLUDED.payload, generated_at = now(), "
            f"source_run_id = EXCLUDED.source_run_id, freshness_status = EXCLUDED.freshness_status",
            {"d": fact_date, "t": fact_type, "p": json.dumps(payload, default=str),
             "rid": source_run_id, "fs": freshness_status}
        )
        conn.commit()


def get_serving_fact(fact_date: str, fact_type: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT payload, generated_at, freshness_status FROM {TABLE_FACT} "
            f"WHERE fact_date = %(d)s AND fact_type = %(t)s",
            {"d": fact_date, "t": fact_type}
        )
        row = cur.fetchone()
        if row:
            return {
                "serving_fact": True,
                "data": row[0],
                "generated_at": row[1].isoformat() if row[1] else None,
                "freshness_status": row[2],
            }
    return None


# ── FACT GENERATORS ──

def generate_all_serving_facts(date: str, run_id: str = None,
                                freshness_status: str = None) -> Dict[str, Any]:
    results = {}
    generators = {
        "operational_summary": _generate_operational_summary_fact,
        "today_action_plan": _generate_today_action_plan_fact,
        "programs_summary": _generate_programs_summary_fact,
        "driver_state_summary": _generate_driver_state_fact,
        "queue_summary": _generate_queue_summary_fact,
        "allocation_trace": _generate_allocation_trace_fact,
        "program_capacity_policy": _generate_policy_fact,
        "refresh_status": _generate_refresh_status_fact,
    }

    for fact_type, generator in generators.items():
        try:
            payload = generator(date)
            save_serving_fact(date, fact_type, payload, run_id, freshness_status)
            results[fact_type] = "SAVED"
        except Exception as e:
            logger.warning(f"Serving fact {fact_type} failed: {e}")
            results[fact_type] = f"FAILED: {str(e)[:100]}"

    return results


def _generate_operational_summary_fact(date: str) -> Dict:
    from app.services.yego_lima_operational_summary_service import get_operational_summary
    return get_operational_summary(date)


def _generate_today_action_plan_fact(date: str) -> Dict:
    from app.services.yego_lima_today_action_plan_service import get_today_action_plan
    return get_today_action_plan(date)


def _generate_programs_summary_fact(date: str) -> Dict:
    from app.services.yego_lima_programs_summary_service import get_programs_summary
    return get_programs_summary(date)


def _generate_driver_state_fact(date: str) -> Dict:
    from app.services.yego_lima_driver_state_summary_service import get_driver_state_summary
    return get_driver_state_summary(date)


def _generate_queue_summary_fact(date: str) -> Dict:
    from app.services.yego_lima_queue_summary_service import get_queue_summary
    return get_queue_summary(date)


def _generate_allocation_trace_fact(date: str) -> Dict:
    from app.services.yego_lima_allocation_trace_service import get_allocation_trace
    return get_allocation_trace(date)


def _generate_policy_fact(date: str) -> Dict:
    from app.services.yego_lima_program_capacity_policy_service import get_active_policy
    return get_active_policy(date)


def _generate_refresh_status_fact(date: str) -> Dict:
    from app.services.yego_lima_daily_refresh_service import get_refresh_status
    return get_refresh_status()
