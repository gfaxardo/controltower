"""
Period Closure Service — Closed Period Protection.
Fase 1D — Protege periodos cerrados de refreshes normales.

Provee:
  - get_last_reliable_data_date()
  - classify_period()
  - run_closure_qa()
  - close_period() / reopen_for_backfill()
  - assert_period_refresh_allowed()
  - compute_fact_checksum()
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from app.settings import settings
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

def _ct_data_lag_days() -> int:
    return int(os.environ.get("CT_DATA_LAG_DAYS", "1"))

def _ct_allow_closed_refresh() -> bool:
    return os.environ.get("CT_ALLOW_CLOSED_PERIOD_REFRESH", "false").lower() in ("1", "true", "yes")

def _ct_dry_run() -> bool:
    return os.environ.get("CT_PERIOD_CLOSURE_DRY_RUN", "true").lower() in ("1", "true", "yes")

CT_MIN_COVERAGE = float(os.environ.get("CT_MIN_MAPPING_COVERAGE_PCT", "99.0"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_last_reliable_data_date() -> Dict[str, Any]:
    today = date.today()
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT MAX(fecha_inicio_viaje::date) FROM public.trips_2026")
            row = cur.fetchone()
            max_raw = row["max"] if row else None
            cur.execute("SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact")
            row2 = cur.fetchone()
            max_fact = row2["max"] if row2 else None
            cur.close()

        reliable = max_raw
        if max_fact and max_raw:
            reliable = min(max_raw, max_fact)
        elif max_fact:
            reliable = max_fact
        elif max_raw:
            reliable = max_raw

        if reliable is None:
            return {
                "last_reliable_data_date": None,
                "lag_days": None,
                "status": "unknown",
                "warning": "No se pudo determinar última fecha confiable. Verificar trips_2026 y day_fact.",
            }

        last_date = reliable if hasattr(reliable, "date") else (reliable.date() if hasattr(reliable, "date") else reliable)
        lag = (today - last_date).days
        status = "fresh" if lag <= _ct_data_lag_days() else "stale" if lag <= _ct_data_lag_days() + 2 else "critical"

        return {
            "last_reliable_data_date": last_date.isoformat() if hasattr(last_date, "isoformat") else str(last_date),
            "lag_days": lag,
            "status": status,
            "max_raw_date": max_raw.isoformat() if hasattr(max_raw, "isoformat") else str(max_raw) if max_raw else None,
            "max_fact_date": max_fact.isoformat() if hasattr(max_fact, "isoformat") else str(max_fact) if max_fact else None,
        }
    except Exception as e:
        logger.warning("get_last_reliable_data_date: %s", e)
        return {"last_reliable_data_date": None, "lag_days": None, "status": "unknown", "warning": str(e)}


def classify_period(
    grain: str,
    period_start: date,
    period_end: Optional[date] = None,
) -> Dict[str, Any]:
    reliable = get_last_reliable_data_date()
    reliable_date_str = reliable.get("last_reliable_data_date")
    reliable_date = date.fromisoformat(reliable_date_str) if reliable_date_str else None

    if period_end is None:
        if grain == "monthly":
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1, day=1) - timedelta(days=1)
        elif grain == "weekly":
            period_end = period_start + timedelta(days=6)
        else:
            period_end = period_start

    is_closed_candidate = False
    is_open = False

    if reliable_date is not None:
        is_closed_candidate = period_end < reliable_date - timedelta(days=_ct_data_lag_days())
        is_open = not is_closed_candidate
    else:
        is_open = True

    return {
        "grain": grain,
        "period_start": period_start.isoformat() if isinstance(period_start, date) else str(period_start),
        "period_end": period_end.isoformat() if isinstance(period_end, date) else str(period_end),
        "last_reliable_data_date": reliable_date_str,
        "lag_days": reliable.get("lag_days"),
        "is_closed_candidate": is_closed_candidate,
        "is_open": is_open,
        "suggested_status": "closed" if is_closed_candidate else "open",
    }


def run_closure_qa(
    grain: str,
    period_start: date,
    period_end: Optional[date] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> Dict[str, Any]:
    if period_end is None:
        if grain == "monthly":
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1, day=1) - timedelta(days=1)
        elif grain == "weekly":
            period_end = period_start + timedelta(days=6)
        else:
            period_end = period_start

    qa: Dict[str, Any] = {
        "grain": grain,
        "period_start": str(period_start)[:10],
        "period_end": str(period_end)[:10],
        "country": country,
        "city": city,
        "checks": [],
        "overall": "pending",
        "blockers": [],
        "warnings": [],
    }

    # Coverage check
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            country_filter = "AND LOWER(COALESCE(country,'')) = LOWER(COALESCE(%s,''))" if country else ""
            city_filter = "AND LOWER(COALESCE(city,'')) = LOWER(COALESCE(%s,''))" if city else ""

            params: List[Any] = [str(period_start), str(period_end)]
            if country:
                params.append(country)
            if city:
                params.append(city)

            cur.execute(f"""
                SELECT 
                    COALESCE(SUM(raw_completed), 0) as raw_total,
                    COALESCE(SUM(fact_mapped), 0) as fact_total,
                    COALESCE(SUM(unmatched_estimate), 0) as unmatched_total
                FROM ops.v_business_slice_mapping_coverage
                WHERE trip_month >= %s AND trip_month < %s
                {country_filter} {city_filter}
            """, params if country or city else params[:2])

            r = cur.fetchone()
            raw = int(r["raw_total"]) if r else 0
            fact = int(r["fact_total"]) if r else 0
            unmatched = int(r["unmatched_total"]) if r else 0
            coverage = 100.0 * fact / raw if raw > 0 else None

            qa["raw_completed_count"] = raw
            qa["fact_completed_count"] = fact
            qa["unmatched_count"] = unmatched
            qa["coverage_pct"] = round(coverage, 2) if coverage is not None else None

            if coverage is not None and coverage >= CT_MIN_COVERAGE:
                qa["checks"].append({"check": "coverage", "status": "pass", "detail": f"{coverage:.2f}% >= {CT_MIN_COVERAGE}%"})
            else:
                qa["checks"].append({"check": "coverage", "status": "fail" if coverage is not None else "warning",
                                     "detail": f"{coverage:.2f}%" if coverage else "N/A"})
                qa["blockers"].append("coverage_below_minimum")

            cur.close()
    except Exception as e:
        qa["checks"].append({"check": "coverage", "status": "error", "detail": str(e)})
        qa["blockers"].append("coverage_query_failed")

    # Freshness check
    fresh = get_last_reliable_data_date()
    if fresh.get("status") == "fresh":
        qa["checks"].append({"check": "freshness", "status": "pass", "detail": str(fresh.get("last_reliable_data_date"))})
    elif fresh.get("status") == "stale":
        qa["checks"].append({"check": "freshness", "status": "warning", "detail": str(fresh.get("last_reliable_data_date"))})
        qa["warnings"].append("data_stale")
    else:
        qa["checks"].append({"check": "freshness", "status": "fail", "detail": fresh.get("warning", "unknown")})
        qa["blockers"].append("freshness_failed")

    # Determine overall
    has_blockers = len(qa["blockers"]) > 0
    has_warnings = len(qa["warnings"]) > 0
    qa["overall"] = "fail" if has_blockers else ("warning" if has_warnings else "pass")

    return qa


def close_period(
    grain: str,
    period_start: date,
    period_end: Optional[date] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice_name: Optional[str] = None,
    closed_by: Optional[str] = None,
    scope: str = "global",
) -> Dict[str, Any]:
    if period_end is None:
        if grain == "monthly":
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1, day=1) - timedelta(days=1)
        elif grain == "weekly":
            period_end = period_start + timedelta(days=6)
        else:
            period_end = period_start

    qa = run_closure_qa(grain, period_start, period_end, country, city)

    if _ct_dry_run():
        return {
            "dry_run": True,
            "action": "would_close" if qa["overall"] == "pass" else "would_fail",
            "qa": qa,
            "message": "Dry run mode. Set CT_PERIOD_CLOSURE_DRY_RUN=false to execute closure.",
        }

    if qa["overall"] != "pass":
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ops.period_closure_registry
                (grain, period_start, period_end, country, city, business_slice_name, status, closure_scope,
                 qa_status, qa_summary, raw_completed_count, fact_completed_count, unmatched_count, coverage_pct,
                 notes, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,'failed_closure',%s,'fail',%s::jsonb,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (grain, period_start, period_end, COALESCE(country,''), COALESCE(city,''), COALESCE(business_slice_name,''))
                DO UPDATE SET status='failed_closure', qa_status='fail', qa_summary=%s::jsonb, updated_at=NOW()
            """, (
                grain, period_start, period_end, country, city, business_slice_name, scope,
                __import__("json").dumps(qa),
                qa.get("raw_completed_count"), qa.get("fact_completed_count"),
                qa.get("unmatched_count"), qa.get("coverage_pct"),
                f"Closure failed QA: {qa['blockers']}",
                __import__("json").dumps(qa),
            ))
            conn.commit()
            cur.close()
        return {"closed": False, "reason": "QA failed", "qa": qa}

    checksum = compute_fact_checksum(grain, period_start, period_end, country, city)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ops.period_closure_registry
            (grain, period_start, period_end, country, city, business_slice_name, status, closure_scope,
             qa_status, qa_summary, raw_completed_count, fact_completed_count, unmatched_count, coverage_pct,
             checksum, closed_at, closed_by, notes, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,'locked',%s,'pass',%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            ON CONFLICT (grain, period_start, period_end, COALESCE(country,''), COALESCE(city,''), COALESCE(business_slice_name,''))
            DO UPDATE SET status='locked', qa_status='pass', qa_summary=%s::jsonb,
                checksum=%s, closed_at=%s, closed_by=%s, updated_at=NOW()
        """, (
            grain, period_start, period_end, country, city, business_slice_name, scope,
            __import__("json").dumps(qa),
            qa.get("raw_completed_count"), qa.get("fact_completed_count"),
            qa.get("unmatched_count"), qa.get("coverage_pct"),
            checksum, _now(), closed_by or "system",
            f"Period closed. QA: pass. Coverage: {qa.get('coverage_pct')}%%",
            __import__("json").dumps(qa), checksum, _now(), closed_by or "system",
        ))
        conn.commit()
        cur.close()

    return {"closed": True, "status": "locked", "qa": qa, "checksum": checksum}


def reopen_for_backfill(
    grain: str,
    period_start: date,
    period_end: Optional[date] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice_name: Optional[str] = None,
    reason: str = "",
    reopened_by: Optional[str] = None,
) -> Dict[str, Any]:
    if period_end is None:
        period_end = period_start

    if not _ct_allow_closed_refresh():
        return {
            "reopened": False,
            "reason": "blocked",
            "message": "CT_ALLOW_CLOSED_PERIOD_REFRESH no activado. Setéelo en 1 solo para ventana de backfill autorizada.",
        }

    if not reason:
        return {"reopened": False, "reason": "missing_reason", "message": "reason es obligatorio para backfill."}

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ops.period_closure_registry
            (grain, period_start, period_end, country, city, business_slice_name, status, closure_scope,
             reopened_at, reopened_by, reopen_reason, notes, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,'backfill','global',%s,%s,%s,%s,NOW())
            ON CONFLICT (grain, period_start, period_end, COALESCE(country,''), COALESCE(city,''), COALESCE(business_slice_name,''))
            DO UPDATE SET status='backfill', reopened_at=%s, reopened_by=%s, reopen_reason=%s, updated_at=NOW()
        """, (
            grain, period_start, period_end, country, city, business_slice_name,
            _now(), reopened_by or "system", reason,
            f"Backfill: {reason}",
            _now(), reopened_by or "system", reason,
        ))
        conn.commit()
        cur.close()

    return {"reopened": True, "status": "backfill", "reason": reason}


def assert_period_refresh_allowed(
    grain: str,
    period_start: date,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice_name: Optional[str] = None,
) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT status FROM ops.period_closure_registry
            WHERE grain = %s AND period_start = %s
              AND (country IS NOT DISTINCT FROM %s)
              AND (city IS NOT DISTINCT FROM %s)
              AND (business_slice_name IS NOT DISTINCT FROM %s)
            ORDER BY updated_at DESC LIMIT 1
        """, (grain, period_start, country, city, business_slice_name))
        row = cur.fetchone()
        cur.close()

    if row is None:
        return {"allowed": True, "status": "unregistered", "reason": "Periodo no registrado. Se permite refresh."}

    current_status = row["status"]

    if current_status in ("locked", "closed"):
        if _ct_allow_closed_refresh():
            return {"allowed": True, "status": current_status, "reason": "Backfill autorizado por CT_ALLOW_CLOSED_PERIOD_REFRESH."}
        else:
            return {"allowed": False, "status": current_status, "reason": f"Periodo {current_status}. Bloqueado por closed period protection."}

    if current_status == "backfill":
        return {"allowed": True, "status": "backfill", "reason": "Periodo en backfill. Refresh permitido."}

    return {"allowed": True, "status": current_status, "reason": f"Periodo {current_status}. Refresh permitido."}


def compute_fact_checksum(
    grain: str,
    period_start: date,
    period_end: Optional[date] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> str:
    if period_end is None:
        if grain == "monthly":
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1, day=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1, day=1)
        elif grain == "weekly":
            period_end = period_start + timedelta(days=7)
        else:
            period_end = period_start + timedelta(days=1)

    fact_table = "ops.real_business_slice_month_fact"

    with get_db() as conn:
        cur = conn.cursor()
        country_clause = "AND COALESCE(country,'') = COALESCE(%s,'')" if country else ""
        city_clause = "AND COALESCE(city,'') = COALESCE(%s,'')" if city else ""
        params = [str(period_start), str(period_end)]
        if country:
            params.append(country)
        if city:
            params.append(city)

        cur.execute(f"""
            SELECT MD5(STRING_AGG(
                COALESCE(business_slice_name,'') || '|' || 
                COALESCE(fleet_display_name,'') || '|' || 
                trips_completed::text || '|' ||
                active_drivers::text,
                '|' ORDER BY business_slice_name, fleet_display_name
            ))
            FROM {fact_table}
            WHERE month >= %s AND month < %s
            {country_clause} {city_clause}
        """, params)
        row = cur.fetchone()
        cur.close()

    return str(row[0]) if row and row[0] else "empty"


def get_period_closure_status(
    grain: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        q = "SELECT * FROM ops.v_period_closure_status"
        params = []
        if grain:
            q += " WHERE grain = %s"
            params.append(grain)
        q += " ORDER BY period_start DESC LIMIT %s"
        params.append(limit)
        cur.execute(q, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

    def _ser(v):
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v)

    return {
        "periods": [{k: _ser(v) for k, v in r.items()} for r in rows],
        "total": len(rows),
        "last_reliable_data": get_last_reliable_data_date(),
    }


def get_period_readiness(
    grain: str,
    period_start: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> Dict[str, Any]:
    ps = date.fromisoformat(str(period_start)[:10] if len(str(period_start)) >= 10 else str(period_start) + "-01")
    qa = run_closure_qa(grain, ps, None, country, city)
    classification = classify_period(grain, ps)

    return {
        "grain": grain,
        "period_start": str(ps),
        "can_close": qa["overall"] == "pass" and classification.get("is_closed_candidate") is True,
        "blockers": qa.get("blockers", []),
        "warnings": qa.get("warnings", []),
        "qa_summary": qa,
        "classification": classification,
    }


def check_period_refresh_guard(
    grain: str,
    period_start: date,
    refresh_name: str = "unknown",
    trigger_source: str = "unknown",
    reason: Optional[str] = None,
    allow_closed_flag: bool = False,
) -> Dict[str, Any]:
    """
    Guardrail reutilizable para scripts de refresh.

    Comportamiento:
      - Si periodo open/provisional/unregistered: allowed=True, ejecutar normalmente.
      - Si periodo closed/locked y CT_PERIOD_CLOSURE_DRY_RUN=true: allowed=True, warning "would_block".
      - Si periodo closed/locked y dry_run=false y allow_closed_flag+reason: allowed=True, backfill.
      - Si periodo closed/locked y dry_run=false sin flag: allowed=False, blocked.

    Returns:
      { allowed: bool, blocked: bool, would_block: bool, status: str, reason: str }
    """
    result = assert_period_refresh_allowed(grain, period_start)

    would_block = not result["allowed"] and result["status"] in ("locked", "closed")

    if _ct_dry_run():
        if would_block:
            _log_guard_event(
                refresh_name=refresh_name,
                trigger_source=trigger_source,
                grain=grain,
                period_start=period_start,
                action="would_block",
                status="skipped",
                warning=f"DRY-RUN: Would block refresh on {result['status']} period {period_start}.",
                reason_text="dry_run_mode",
            )
            return {
                "allowed": True,
                "blocked": False,
                "would_block": True,
                "status": "would_block",
                "reason": f"DRY-RUN: Would block. {result['reason']}",
            }

        return {
            "allowed": True,
            "blocked": False,
            "would_block": False,
            "status": "allowed",
            "reason": "Period open or dry-run mode.",
        }

    if not would_block:
        return {
            "allowed": True,
            "blocked": False,
            "would_block": False,
            "status": "allowed",
            "reason": "Period open or unregistered.",
        }

    if allow_closed_flag and _ct_allow_closed_refresh() and reason:
        _log_guard_event(
            refresh_name=refresh_name,
            trigger_source=trigger_source,
            grain=grain,
            period_start=period_start,
            action="backfill",
            status="running",
            warning=f"Backfill autorizado: {reason}",
            lock_acquired=True,
            reason_text=reason,
        )
        return {
            "allowed": True,
            "blocked": False,
            "would_block": False,
            "status": "backfill",
            "reason": f"Backfill autorizado: {reason}",
        }

    if not reason and would_block:
        _log_guard_event(
            refresh_name=refresh_name,
            trigger_source=trigger_source,
            grain=grain,
            period_start=period_start,
            action="blocked",
            status="blocked",
            error=f"Periodo {result['status']}. Bloqueado por closed period protection.",
            reason_text="no_reason_no_flag",
        )
        return {
            "allowed": False,
            "blocked": True,
            "would_block": False,
            "status": "blocked",
            "reason": f"Periodo {result['status']}. Bloqueado. Requiere --allow-closed-period --reason y CT_ALLOW_CLOSED_PERIOD_REFRESH=1.",
        }

    _log_guard_event(
        refresh_name=refresh_name,
        trigger_source=trigger_source,
        grain=grain,
        period_start=period_start,
        action="blocked",
        status="blocked",
        error=f"Periodo {result['status']}. Bloqueado. Reason missing or flag not set.",
        reason_text="reason_missing",
    )
    return {
        "allowed": False,
        "blocked": True,
        "would_block": False,
        "status": "blocked",
        "reason": f"Periodo {result['status']}. Bloqueado.",
    }


def _log_guard_event(
    refresh_name: str,
    trigger_source: str,
    grain: str,
    period_start: date,
    action: str,
    status: str,
    warning: Optional[str] = None,
    error: Optional[str] = None,
    lock_acquired: bool = False,
    reason_text: str = "",
) -> None:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            notes = f"Period guard: {action} on {grain} {period_start}"
            if reason_text:
                notes += f". Reason: {reason_text}"
            cur.execute("""
                INSERT INTO ops.refresh_run_log (
                    refresh_name, trigger_source, grain,
                    period_start, period_end, period_status,
                    status, warning_message, error_message,
                    lock_acquired, started_at
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, NOW()
                )
            """, (
                f"{refresh_name}_period_guard",
                trigger_source,
                grain,
                period_start,
                None,
                "closed" if action in ("blocked", "would_block") else "open",
                status,
                (warning or notes)[:1000],
                (error or "")[:2000],
                lock_acquired,
            ))
            conn.commit()
            cur.close()
    except Exception as e:
        logger.warning("_log_guard_event failed: %s", e)
