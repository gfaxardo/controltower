"""
Refresh Control Service — Advisory Locks + Refresh Ledger centralizado.

Fase 1B — Refresh Hardening. Provee:
  - start_refresh_run / finish_refresh_run / fail_refresh_run / skip_refresh_run / block_refresh_run
  - Context manager refresh_guard() para envolver pipelines con lock + ledger
  - Cálculo determinista de advisory lock key (hash SHA256 → int64 compatible PG)
  - Guardrail destructivo: bloquea DROP + CASCADE en producción sin flag explícito
  - Detección de SQL destructivo (DROP MATERIALIZED VIEW, DROP VIEW, DROP TABLE con CASCADE)

Uso desde scripts:
    with refresh_guard(
        refresh_name="supply_refresh_pipeline",
        pipeline_name="supply_refresh",
        grain="weekly",
        trigger_source="cron",
        scope={"country": "all"},
    ) as guard:
        if guard.skipped:
            return  # otro proceso tiene el lock
        refresh_supply_alerting_mvs()
        guard.set_rows_affected(12345)

Uso desde servicios/APScheduler:
    guard = start_refresh_run(refresh_name="omniview_real_refresh", ...)
    if not guard.lock_acquired:
        return {"skipped": True}
    try:
        ...
        finish_refresh_run(guard.run_id)
    except Exception as e:
        fail_refresh_run(guard.run_id, str(e))
"""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import socket
import struct
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, Generator, List, Optional

from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

_LOCK_KEY_MAGIC: int = 173648291

# Palabras clave SQL que indican operación destructiva
_DESTRUCTIVE_SQL_PATTERNS: List[str] = [
    "DROP MATERIALIZED VIEW",
    "DROP VIEW",
    "DROP TABLE",
    "CASCADE",
]


@dataclass
class RefreshGuardState:
    run_id: Optional[int] = None
    refresh_name: str = ""
    pipeline_name: Optional[str] = None
    step_name: Optional[str] = None
    lock_key: int = 0
    lock_acquired: bool = False
    skipped: bool = False
    blocked: bool = False
    blocked_reason: str = ""
    started_at: float = 0.0
    _conn: Any = None
    _db_ctx: Any = None


def _compute_lock_key(refresh_name: str, scope_key: Optional[str] = None) -> int:
    seed = refresh_name or "unknown_refresh"
    if scope_key:
        seed = f"{seed}:{scope_key}"
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    return (struct.unpack(">q", h[:8])[0] & 0x7FFFFFFFFFFFFFFF) % (2**63)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _env_name() -> str:
    return str(getattr(settings, "ENVIRONMENT", "") or os.environ.get("ENVIRONMENT", "") or "dev").lower()


def _host_name() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return platform.node() or "unknown"


def _code_version() -> Optional[str]:
    for var in ("GIT_COMMIT", "RELEASE_VERSION", "CODE_VERSION"):
        v = os.environ.get(var)
        if v:
            return str(v)[:64]
    return None


def _is_destructive_sql(sql_text: str) -> bool:
    upper = sql_text.upper()
    return any(p in upper for p in _DESTRUCTIVE_SQL_PATTERNS)


def _production_destructive_allowed() -> bool:
    env = _env_name()
    if env not in ("production", "prod"):
        return True
    allowed = os.environ.get("CT_ALLOW_DESTRUCTIVE_REFRESH", "").lower()
    return allowed in ("1", "true", "yes")


def _refresh_locks_enabled() -> bool:
    val = os.environ.get("CT_REFRESH_LOCKS_ENABLED", "true").lower()
    return val in ("1", "true", "yes")


def _refresh_ledger_enabled() -> bool:
    val = os.environ.get("CT_REFRESH_LEDGER_ENABLED", "true").lower()
    return val in ("1", "true", "yes")


def _scheduler_enabled() -> bool:
    val = os.environ.get("CT_SCHEDULER_ENABLED", "false").lower()
    return val in ("1", "true", "yes")


def check_destructive_sql(sql_text: str, context: str = "") -> None:
    if _is_destructive_sql(sql_text) and not _production_destructive_allowed():
        msg = (
            f"Blocked destructive SQL in production: {context or 'unknown context'}. "
            f"Set CT_ALLOW_DESTRUCTIVE_REFRESH=1 only for an authorized backfill window."
        )
        logger.warning(msg)
        raise RuntimeError(msg)


def check_destructive_sql_safe(sql_text: str, context: str = "") -> bool:
    if _is_destructive_sql(sql_text) and not _production_destructive_allowed():
        msg = (
            f"Blocked destructive SQL in production: {context or 'unknown context'}. "
            f"Set CT_ALLOW_DESTRUCTIVE_REFRESH=1 only for an authorized backfill window."
        )
        logger.warning(msg)
        return False
    return True


def start_refresh_run(
    refresh_name: str,
    pipeline_name: Optional[str] = None,
    step_name: Optional[str] = None,
    trigger_source: str = "unknown",
    grain: str = "unknown",
    scope: Optional[Dict[str, Any]] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    period_status: str = "unknown",
    scope_key: Optional[str] = None,
) -> RefreshGuardState:
    state = RefreshGuardState(
        refresh_name=refresh_name,
        pipeline_name=pipeline_name,
        step_name=step_name,
        lock_key=_compute_lock_key(refresh_name, scope_key),
        started_at=time.perf_counter(),
    )

    if not _refresh_locks_enabled():
        state.lock_acquired = True
        state.skipped = False
    else:
        db_ctx = None
        try:
            db_ctx = get_db()
            conn = db_ctx.__enter__()
            cur = conn.cursor()
            cur.execute("SELECT pg_try_advisory_lock(%s)", (state.lock_key,))
            acquired = cur.fetchone()[0]
            cur.close()

            if not acquired:
                if _refresh_ledger_enabled():
                    _write_log(
                        conn,
                        refresh_name=refresh_name,
                        pipeline_name=pipeline_name,
                        step_name=step_name,
                        trigger_source=trigger_source,
                        lock_key=state.lock_key,
                        lock_acquired=False,
                        grain=grain,
                        scope=scope,
                        period_start=period_start,
                        period_end=period_end,
                        period_status=period_status,
                        status="skipped",
                        warning_message="Lock already held by another process",
                    )
                    conn.commit()
                if db_ctx is not None:
                    try:
                        db_ctx.__exit__(None, None, None)
                    except Exception:
                        pass
                state.lock_acquired = False
                state.skipped = True
                state._conn = None
                logger.info(
                    "Refresh SKIPPED (lock held): refresh_name=%s lock_key=%s",
                    refresh_name,
                    state.lock_key,
                )
                return state

            state.lock_acquired = True
            state._conn = conn
            state._db_ctx = db_ctx
            logger.info(
                "Lock ACQUIRED: refresh_name=%s lock_key=%s",
                refresh_name,
                state.lock_key,
            )
        except Exception as e:
            logger.exception("Error acquiring lock for %s: %s", refresh_name, e)
            if db_ctx is not None:
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    db_ctx.__exit__(None, None, None)
                except Exception:
                    pass
            state.lock_acquired = False
            state.skipped = True
            state._conn = None
            return state

    if _refresh_ledger_enabled():
        try:
            run_id = _write_log(
                state._conn,
                refresh_name=refresh_name,
                pipeline_name=pipeline_name,
                step_name=step_name,
                trigger_source=trigger_source,
                lock_key=state.lock_key,
                lock_acquired=state.lock_acquired,
                grain=grain,
                scope=scope,
                period_start=period_start,
                period_end=period_end,
                period_status=period_status,
                status="running",
            )
            state._conn.commit()
            state.run_id = run_id
        except Exception as e:
            logger.warning("Failed to insert refresh_run_log (running): %s", e)

    return state


def finish_refresh_run(
    state_or_run_id: Any,
    rows_affected: Optional[int] = None,
    source_min_date: Optional[date] = None,
    source_max_date: Optional[date] = None,
    warning_message: Optional[str] = None,
) -> None:
    _end_refresh(state_or_run_id, "success", None, rows_affected, source_min_date, source_max_date, warning_message)
    _release(state_or_run_id)


def fail_refresh_run(
    state_or_run_id: Any,
    error_message: str,
    rows_affected: Optional[int] = None,
    warning_message: Optional[str] = None,
) -> None:
    _end_refresh(state_or_run_id, "failed", error_message, rows_affected, None, None, warning_message)
    _release(state_or_run_id)


def skip_refresh_run(
    state_or_run_id: Any,
    reason: str,
) -> None:
    _end_refresh(state_or_run_id, "skipped", None, None, None, None, reason)
    _release(state_or_run_id)


def block_refresh_run(
    state_or_run_id: Any,
    reason: str,
) -> None:
    _end_refresh(state_or_run_id, "blocked", reason, None, None, None, None)
    _release(state_or_run_id)


def _end_refresh(
    state_or_run_id: Any,
    status: str,
    error_message: Optional[str] = None,
    rows_affected: Optional[int] = None,
    source_min_date: Optional[date] = None,
    source_max_date: Optional[date] = None,
    warning_message: Optional[str] = None,
) -> None:
    if not _refresh_ledger_enabled():
        return

    if isinstance(state_or_run_id, RefreshGuardState):
        run_id = state_or_run_id.run_id
        conn = state_or_run_id._conn
        db_ctx = state_or_run_id._db_ctx
        started_at = state_or_run_id.started_at
    else:
        run_id = state_or_run_id
        conn = None
        db_ctx = None
        started_at = 0.0

    duration = round(time.perf_counter() - started_at, 2) if started_at > 0 else None

    try:
        own_ctx = None
        if conn is None:
            own_ctx = get_db()
            conn = own_ctx.__enter__()

        cur = conn.cursor()
        cur.execute(
            """
            UPDATE ops.refresh_run_log
            SET status = %s,
                finished_at = %s,
                duration_seconds = %s,
                rows_affected = %s,
                source_min_date = %s,
                source_max_date = %s,
                error_message = %s,
                warning_message = %s
            WHERE id = %s
            """,
            (
                status,
                _now_utc(),
                duration,
                rows_affected,
                source_min_date,
                source_max_date,
                (error_message or "")[:2000] if error_message else None,
                (warning_message or "")[:1000] if warning_message else None,
                run_id,
            ),
        )
        cur.close()
        conn.commit()

        if own_ctx is not None:
            try:
                own_ctx.__exit__(None, None, None)
            except Exception:
                pass
    except Exception as e:
        logger.warning("Failed to update refresh_run_log (id=%s): %s", run_id, e)
        if own_ctx is not None:
            try:
                own_ctx.__exit__(None, None, None)
            except Exception:
                pass


def _release(state_or_run_id: Any) -> None:
    if isinstance(state_or_run_id, RefreshGuardState):
        state = state_or_run_id
    else:
        return

    if state._conn is not None:
        try:
            state._conn.rollback()
        except Exception:
            pass

    if state.lock_acquired and state._conn is not None and state.lock_key:
        try:
            cur = state._conn.cursor()
            cur.execute("SELECT pg_advisory_unlock(%s)", (state.lock_key,))
            cur.close()
            state._conn.commit()
            logger.debug("Lock RELEASED: key=%s", state.lock_key)
        except Exception as e:
            logger.warning("Failed to release advisory lock (key=%s): %s", state.lock_key, e)

    if state._db_ctx is not None:
        try:
            state._db_ctx.__exit__(None, None, None)
        except Exception:
            pass
        state._db_ctx = None
        state._conn = None


def _write_log(
    conn,
    refresh_name: str,
    pipeline_name: Optional[str] = None,
    step_name: Optional[str] = None,
    trigger_source: str = "unknown",
    lock_key: Optional[int] = None,
    lock_acquired: bool = False,
    grain: str = "unknown",
    scope: Optional[Dict[str, Any]] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    period_status: str = "unknown",
    status: str = "running",
    warning_message: Optional[str] = None,
) -> int:
    import json as _json

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO ops.refresh_run_log (
            refresh_name, pipeline_name, step_name,
            trigger_source, environment, host_name, process_id,
            lock_key, lock_acquired,
            grain, scope, period_start, period_end, period_status,
            status, started_at,
            warning_message, code_version
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s::jsonb, %s, %s, %s,
            %s, %s,
            %s, %s
        )
        RETURNING id
        """,
        (
            refresh_name,
            pipeline_name,
            step_name,
            trigger_source,
            _env_name(),
            _host_name(),
            os.getpid(),
            lock_key or 0,
            lock_acquired,
            grain,
            _json.dumps(scope) if scope else None,
            period_start.isoformat() if isinstance(period_start, date) else str(period_start) if period_start else None,
            period_end.isoformat() if isinstance(period_end, date) else str(period_end) if period_end else None,
            period_status,
            status,
            _now_utc(),
            (warning_message or "")[:1000] if warning_message else None,
            _code_version(),
        ),
    )
    row = cur.fetchone()
    run_id = int(row[0]) if row else 0
    cur.close()
    return run_id


@contextmanager
def refresh_guard(
    refresh_name: str,
    pipeline_name: Optional[str] = None,
    step_name: Optional[str] = None,
    trigger_source: str = "unknown",
    grain: str = "unknown",
    scope: Optional[Dict[str, Any]] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    period_status: str = "unknown",
    scope_key: Optional[str] = None,
) -> Generator[RefreshGuardState, None, None]:
    state = start_refresh_run(
        refresh_name=refresh_name,
        pipeline_name=pipeline_name,
        step_name=step_name,
        trigger_source=trigger_source,
        grain=grain,
        scope=scope,
        period_start=period_start,
        period_end=period_end,
        period_status=period_status,
        scope_key=scope_key,
    )

    if state.skipped:
        try:
            yield state
        finally:
            pass
        return

    try:
        yield state
    except Exception as e:
        fail_refresh_run(state, str(e))
        raise
    else:
        if state.run_id and not state.skipped:
            finish_refresh_run(state)


def get_refresh_status(
    refresh_name: Optional[str] = None,
    pipeline_name: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            q = """
                SELECT
                    refresh_name, pipeline_name, step_name,
                    status, trigger_source, grain,
                    started_at, finished_at, duration_seconds,
                    lock_acquired,
                    source_max_date,
                    period_start, period_end, period_status,
                    warning_message, error_message,
                    rows_affected,
                    environment, host_name
                FROM ops.v_refresh_latest_status
            """
            params: List[Any] = []
            conditions: List[str] = []

            if refresh_name:
                conditions.append("refresh_name = %s")
                params.append(refresh_name)
            if pipeline_name:
                conditions.append("pipeline_name = %s")
                params.append(pipeline_name)

            if conditions:
                q += " WHERE " + " AND ".join(conditions)

            q += " ORDER BY started_at DESC LIMIT %s"
            params.append(limit)

            cur.execute(q, params)
            rows = cur.fetchall()
            cur.close()

            def _ser(v: Any) -> Any:
                if v is None:
                    return None
                if hasattr(v, "isoformat"):
                    return v.isoformat()
                return str(v)

            results = []
            for r in rows:
                results.append({
                    "refresh_name": r[0],
                    "pipeline_name": r[1],
                    "step_name": r[2],
                    "status": r[3],
                    "trigger_source": r[4],
                    "grain": r[5],
                    "started_at": _ser(r[6]),
                    "finished_at": _ser(r[7]),
                    "duration_seconds": float(r[8]) if r[8] is not None else None,
                    "lock_acquired": bool(r[9]),
                    "source_max_date": _ser(r[10]),
                    "period_start": _ser(r[11]),
                    "period_end": _ser(r[12]),
                    "period_status": r[13],
                    "warning_message": r[14],
                    "error_message": r[15],
                    "rows_affected": int(r[16]) if r[16] is not None else None,
                    "environment": r[17],
                    "host_name": r[18],
                })

            stale_warning = False
            if results:
                last = results[0]
                if last["status"] in ("failed", "skipped", "blocked"):
                    stale_warning = True
            elif refresh_name:
                stale_warning = True

            return {
                "statuses": results,
                "total": len(results),
                "stale_warning": stale_warning,
            }

    except Exception as e:
        logger.warning("get_refresh_status: %s", e)
        return {"statuses": [], "total": 0, "stale_warning": True, "error": str(e)}


def is_scheduler_enabled() -> bool:
    env = _env_name()
    if env in ("production", "prod"):
        return _scheduler_enabled()
    return True
