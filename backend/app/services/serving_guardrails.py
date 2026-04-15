"""
Serving guardrails — hard enforcement for fact-first discipline.

Provides:
- ServingPolicy: per-feature policy declaration
- FORBIDDEN_SERVING_SOURCES: central blocklist
- check_source_allowed / assert_serving_source: runtime enforcement
- trace_source_usage / get_usage_log: runtime traceability
- execute_serving_query: query interception wrapper (hard gate)
- register_policy / get_declared_policy / is_policy_declared: policy registry
- QueryExecutionContext: explicit context for DB-level gating (FASE 2.7)
- DbGuardMode / execute_db_gated_query: DB-layer enforcement gate (FASE 2.7)
"""
from __future__ import annotations

import contextvars
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QueryMode(str, Enum):
    SERVING = "serving"
    DRILL = "drill"
    AUDIT = "audit"
    REBUILD = "rebuild"


class SourceType(str, Enum):
    FACT = "fact"
    MV = "mv"
    CACHE = "cache"
    VIEW = "view"
    RESOLVED = "resolved"
    RAW = "raw"


class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    WARNING = "WARNING"
    NON_COMPLIANT = "NON_COMPLIANT"
    UNKNOWN = "UNKNOWN"


class ServingSourceViolation(Exception):
    """Raised when a serving endpoint attempts to use a forbidden source in strict mode."""


FORBIDDEN_SERVING_SOURCES: List[str] = [
    "public.trips_all",
    "public.trips_unified",
    "ops.v_real_trips_business_slice_resolved",
    "ops.v_real_trips_enriched_base",
    "ops.v_real_trip_fact_v2",
]


@dataclass
class ServingPolicy:
    feature_name: str
    query_mode: QueryMode
    preferred_source: str
    preferred_source_type: SourceType
    forbidden_sources: List[str] = field(default_factory=lambda: list(FORBIDDEN_SERVING_SOURCES))
    fallback_allowed: bool = False
    allowed_fallbacks: List[str] = field(default_factory=list)
    strict_mode: bool = True
    require_preferred_source_match: bool = False


@dataclass
class SourceCheckResult:
    allowed: bool
    source: str
    reason: str
    compliance: ComplianceStatus


@dataclass
class SourceUsageRecord:
    feature_name: str
    query_mode: str
    source_used: str
    source_type: str
    forbidden_source_used: bool
    fallback_used: bool
    fallback_reason: Optional[str]
    timestamp: str


_usage_lock = threading.Lock()
_USAGE_LOG: List[SourceUsageRecord] = []
_MAX_LOG_SIZE = 500


def check_source_allowed(policy: ServingPolicy, actual_source: str) -> SourceCheckResult:
    """Check whether actual_source is allowed under the given policy."""
    src_lower = actual_source.strip().lower()

    if policy.query_mode in (QueryMode.DRILL, QueryMode.AUDIT, QueryMode.REBUILD):
        return SourceCheckResult(
            allowed=True,
            source=actual_source,
            reason=f"query_mode={policy.query_mode.value} allows broad sources",
            compliance=ComplianceStatus.COMPLIANT,
        )

    for forbidden in policy.forbidden_sources:
        if forbidden.strip().lower() == src_lower:
            return SourceCheckResult(
                allowed=False,
                source=actual_source,
                reason=f"Source '{actual_source}' is in forbidden_sources for serving",
                compliance=ComplianceStatus.NON_COMPLIANT,
            )

    for forbidden in FORBIDDEN_SERVING_SOURCES:
        if forbidden.strip().lower() == src_lower:
            return SourceCheckResult(
                allowed=False,
                source=actual_source,
                reason=f"Source '{actual_source}' is in global FORBIDDEN_SERVING_SOURCES",
                compliance=ComplianceStatus.NON_COMPLIANT,
            )

    return SourceCheckResult(
        allowed=True,
        source=actual_source,
        reason="source is allowed",
        compliance=ComplianceStatus.COMPLIANT,
    )


def assert_serving_source(policy: ServingPolicy, actual_source: str) -> None:
    """Raise ServingSourceViolation if source is forbidden under strict_mode."""
    result = check_source_allowed(policy, actual_source)
    if not result.allowed:
        logger.error(
            "SERVING_GUARDRAIL_VIOLATION: feature=%s source=%s reason=%s",
            policy.feature_name, actual_source, result.reason,
        )
        if policy.strict_mode:
            raise ServingSourceViolation(
                f"[{policy.feature_name}] {result.reason}. "
                f"Use the appropriate fact/MV or change query_mode to drill/audit."
            )


def trace_source_usage(
    policy: ServingPolicy,
    actual_source: str,
    source_type: str = "unknown",
    fallback_used: bool = False,
    fallback_reason: Optional[str] = None,
) -> SourceUsageRecord:
    """Record actual source usage for diagnostics."""
    is_forbidden = not check_source_allowed(policy, actual_source).allowed

    if is_forbidden:
        logger.warning(
            "SERVING_FORBIDDEN_SOURCE_USED: feature=%s source=%s mode=%s",
            policy.feature_name, actual_source, policy.query_mode.value,
        )

    record = SourceUsageRecord(
        feature_name=policy.feature_name,
        query_mode=policy.query_mode.value,
        source_used=actual_source,
        source_type=source_type,
        forbidden_source_used=is_forbidden,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    with _usage_lock:
        _USAGE_LOG.append(record)
        if len(_USAGE_LOG) > _MAX_LOG_SIZE:
            del _USAGE_LOG[: len(_USAGE_LOG) - _MAX_LOG_SIZE]

    return record


def get_usage_log() -> List[Dict[str, Any]]:
    """Return recent source usage records for diagnostics."""
    with _usage_lock:
        return [
            {
                "feature_name": r.feature_name,
                "query_mode": r.query_mode,
                "source_used": r.source_used,
                "source_type": r.source_type,
                "forbidden_source_used": r.forbidden_source_used,
                "fallback_used": r.fallback_used,
                "fallback_reason": r.fallback_reason,
                "timestamp": r.timestamp,
            }
            for r in list(_USAGE_LOG)
        ]


def clear_usage_log() -> None:
    with _usage_lock:
        _USAGE_LOG.clear()


def get_feature_usage_summary() -> Dict[str, Any]:
    """Aggregate usage log by feature for quick compliance overview."""
    with _usage_lock:
        log_copy = list(_USAGE_LOG)

    by_feature: Dict[str, Dict[str, Any]] = {}
    for r in log_copy:
        if r.feature_name not in by_feature:
            by_feature[r.feature_name] = {
                "total_queries": 0,
                "forbidden_uses": 0,
                "fallbacks": 0,
                "last_source": None,
                "last_timestamp": None,
            }
        entry = by_feature[r.feature_name]
        entry["total_queries"] += 1
        if r.forbidden_source_used:
            entry["forbidden_uses"] += 1
        if r.fallback_used:
            entry["fallbacks"] += 1
        entry["last_source"] = r.source_used
        entry["last_timestamp"] = r.timestamp

    return by_feature


# ---------------------------------------------------------------------------
# Policy registry — services register their policy at import time
# ---------------------------------------------------------------------------
_policy_lock = threading.Lock()
_DECLARED_POLICIES: Dict[str, ServingPolicy] = {}


def register_policy(policy: ServingPolicy) -> None:
    """Register a ServingPolicy so diagnostics can verify declaration."""
    with _policy_lock:
        _DECLARED_POLICIES[policy.feature_name] = policy


def get_declared_policy(feature_name: str) -> Optional[ServingPolicy]:
    with _policy_lock:
        return _DECLARED_POLICIES.get(feature_name)


def is_policy_declared(feature_name: str) -> bool:
    with _policy_lock:
        return feature_name in _DECLARED_POLICIES


def get_all_declared_policies() -> Dict[str, ServingPolicy]:
    with _policy_lock:
        return dict(_DECLARED_POLICIES)


# ---------------------------------------------------------------------------
# execute_serving_query — hard enforcement gate
# ---------------------------------------------------------------------------

def execute_serving_query(
    policy: ServingPolicy,
    conn_or_cursor,
    sql: str,
    params: Any = None,
    source_name: str = "",
    source_type: str = "unknown",
    cursor_factory: Any = None,
) -> List[Dict[str, Any]]:
    """Central wrapper for all serving-critical queries.

    Enforces:
    1. Feature must be in SERVING_REGISTRY
    2. Source must not be forbidden (strict mode)
    3. preferred_source_match warning if enabled
    4. Traces usage after execution
    5. DB gate ContextVar check: warns/blocks if called outside execute_db_gated_query
    """
    from app.utils.source_trace import assert_feature_registered

    assert_feature_registered(policy.feature_name)

    # DB gate bypass detection: if this is a SERVING query and _active_db_gate
    # is not set, someone is bypassing execute_db_gated_query()
    if policy.query_mode == QueryMode.SERVING:
        mode = get_db_guard_mode()
        if mode != DbGuardMode.OFF and _active_db_gate.get() is None:
            msg = (
                f"DB_GATE_BYPASS_DETECTED: execute_serving_query() called without "
                f"execute_db_gated_query() context. feature={policy.feature_name}"
            )
            if mode == DbGuardMode.STRICT:
                logger.error(msg)
                raise ServingSourceViolation(msg)
            logger.warning(msg)

    if source_name:
        assert_serving_source(policy, source_name)

    if policy.require_preferred_source_match and source_name:
        ps = policy.preferred_source.strip().lower()
        sn = source_name.strip().lower()
        if sn != ps:
            logger.warning(
                "SERVING_SOURCE_MISMATCH: feature=%s preferred=%s actual=%s",
                policy.feature_name, policy.preferred_source, source_name,
            )

    needs_close = False
    if hasattr(conn_or_cursor, "cursor"):
        cur = conn_or_cursor.cursor(cursor_factory=cursor_factory) if cursor_factory else conn_or_cursor.cursor()
        needs_close = True
    else:
        cur = conn_or_cursor

    try:
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        if needs_close:
            cur.close()

    trace_source_usage(
        policy,
        actual_source=source_name or policy.preferred_source,
        source_type=source_type,
    )

    return rows


# ---------------------------------------------------------------------------
# FASE 2.7 — QueryExecutionContext + DB-level gate
# ---------------------------------------------------------------------------


@dataclass
class QueryExecutionContext:
    """Explicit context carried by every DB-level gated query."""
    feature_name: str
    query_mode: QueryMode
    expected_source: str
    source_type: SourceType
    strict_mode: bool = True
    allow_fallback: bool = False
    request_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


def context_from_policy(
    policy: ServingPolicy,
    source_name: str = "",
    request_id: Optional[str] = None,
) -> QueryExecutionContext:
    """Build a QueryExecutionContext from a ServingPolicy."""
    return QueryExecutionContext(
        feature_name=policy.feature_name,
        query_mode=policy.query_mode,
        expected_source=source_name or policy.preferred_source,
        source_type=policy.preferred_source_type,
        strict_mode=policy.strict_mode,
        allow_fallback=policy.fallback_allowed,
        request_id=request_id,
    )


# ---------------------------------------------------------------------------
# DB_SERVING_GUARD_MODE — configurable enforcement level
# ---------------------------------------------------------------------------


class DbGuardMode(str, Enum):
    OFF = "off"
    WARN = "warn"
    STRICT = "strict"


_env_mode = os.environ.get("DB_SERVING_GUARD_MODE", "warn").strip().lower()
try:
    DB_SERVING_GUARD_MODE: DbGuardMode = DbGuardMode(_env_mode)
except ValueError:
    DB_SERVING_GUARD_MODE = DbGuardMode.WARN

_guard_mode_lock = threading.Lock()


def get_db_guard_mode() -> DbGuardMode:
    return DB_SERVING_GUARD_MODE


def set_db_guard_mode(mode: DbGuardMode) -> None:
    global DB_SERVING_GUARD_MODE
    with _guard_mode_lock:
        DB_SERVING_GUARD_MODE = mode


# ContextVar to track whether a DB gate is active in the current execution
_active_db_gate: contextvars.ContextVar[Optional[QueryExecutionContext]] = (
    contextvars.ContextVar("_active_db_gate", default=None)
)


# ---------------------------------------------------------------------------
# DB gate log (separate from usage_log)
# ---------------------------------------------------------------------------

_db_gate_lock = threading.Lock()
_DB_GATE_LOG: List[Dict[str, Any]] = []
_MAX_DB_GATE_LOG = 500


def _record_db_gate(
    ctx: QueryExecutionContext,
    guard_mode: str,
    outcome: str,
    source_name: str = "",
) -> None:
    entry = {
        "feature_name": ctx.feature_name,
        "query_mode": ctx.query_mode.value,
        "expected_source": ctx.expected_source,
        "source_used": source_name or ctx.expected_source,
        "guard_mode": guard_mode,
        "outcome": outcome,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with _db_gate_lock:
        _DB_GATE_LOG.append(entry)
        if len(_DB_GATE_LOG) > _MAX_DB_GATE_LOG:
            del _DB_GATE_LOG[: len(_DB_GATE_LOG) - _MAX_DB_GATE_LOG]


# ---------------------------------------------------------------------------
# execute_db_gated_query — DB-level enforcement gate
# ---------------------------------------------------------------------------


def execute_db_gated_query(
    ctx: QueryExecutionContext,
    policy: ServingPolicy,
    conn_or_cursor,
    sql: str,
    params: Any = None,
    source_name: str = "",
    source_type: str = "unknown",
    cursor_factory: Any = None,
) -> List[Dict[str, Any]]:
    """DB-level gate wrapping execute_serving_query with ContextVar tracking.

    Enforcement depends on DB_SERVING_GUARD_MODE:
    - strict: full validation; violations raise
    - warn: validation + log warnings only
    - off: pass through
    """
    mode = get_db_guard_mode()
    token = _active_db_gate.set(ctx)

    try:
        if mode == DbGuardMode.OFF:
            rows = execute_serving_query(
                policy, conn_or_cursor, sql, params,
                source_name=source_name, source_type=source_type,
                cursor_factory=cursor_factory,
            )
            _record_db_gate(ctx, mode.value, "pass", source_name)
            return rows

        # Validate context minimum
        if not ctx.feature_name or not ctx.query_mode:
            msg = f"DB_GATE: missing context fields feature_name={ctx.feature_name} query_mode={ctx.query_mode}"
            if mode == DbGuardMode.STRICT:
                raise ServingSourceViolation(msg)
            logger.warning(msg)

        # Query mode-aware enforcement (TAREA 7)
        if ctx.query_mode == QueryMode.SERVING and mode == DbGuardMode.STRICT:
            # Full enforcement: execute_serving_query already does assert_serving_source
            rows = execute_serving_query(
                policy, conn_or_cursor, sql, params,
                source_name=source_name, source_type=source_type,
                cursor_factory=cursor_factory,
            )
            _record_db_gate(ctx, mode.value, "enforced", source_name)
            return rows

        if ctx.query_mode in (QueryMode.DRILL, QueryMode.AUDIT, QueryMode.REBUILD):
            # Relaxed: trace only, no block
            rows = execute_serving_query(
                policy, conn_or_cursor, sql, params,
                source_name=source_name, source_type=source_type,
                cursor_factory=cursor_factory,
            )
            _record_db_gate(ctx, mode.value, "relaxed", source_name)
            return rows

        # Default (warn mode for SERVING, or unknown query_mode)
        rows = execute_serving_query(
            policy, conn_or_cursor, sql, params,
            source_name=source_name, source_type=source_type,
            cursor_factory=cursor_factory,
        )
        outcome = "warn" if mode == DbGuardMode.WARN else "pass"
        _record_db_gate(ctx, mode.value, outcome, source_name)
        return rows

    finally:
        _active_db_gate.reset(token)


# ---------------------------------------------------------------------------
# Detection of ungated direct execution (TAREA 5)
# ---------------------------------------------------------------------------


def is_db_gate_active() -> bool:
    """True if the current execution is inside a DB gate context."""
    return _active_db_gate.get() is not None


def get_active_db_context() -> Optional[QueryExecutionContext]:
    return _active_db_gate.get()


def assert_db_gate_active(feature_hint: str = "") -> None:
    """Assert that the current execution is inside a DB gate.

    Respects DB_SERVING_GUARD_MODE:
    - strict: raises ServingSourceViolation
    - warn: logs warning
    - off: no-op
    """
    if is_db_gate_active():
        return
    mode = get_db_guard_mode()
    if mode == DbGuardMode.OFF:
        return
    msg = f"DB_GATE_UNGATED_EXECUTION: query executed without DB gate context. hint={feature_hint}"
    if mode == DbGuardMode.STRICT:
        logger.error(msg)
        raise ServingSourceViolation(msg)
    logger.warning(msg)


def get_db_gate_log() -> List[Dict[str, Any]]:
    with _db_gate_lock:
        return list(_DB_GATE_LOG)


def get_db_gate_summary() -> Dict[str, Any]:
    """Aggregate DB gate log for diagnostics."""
    with _db_gate_lock:
        log_copy = list(_DB_GATE_LOG)

    by_feature: Dict[str, Dict[str, Any]] = {}
    for entry in log_copy:
        fname = entry["feature_name"]
        if fname not in by_feature:
            by_feature[fname] = {
                "total_gated": 0,
                "enforced": 0,
                "warned": 0,
                "relaxed": 0,
                "passed": 0,
                "last_guard_mode": None,
                "last_outcome": None,
                "last_timestamp": None,
            }
        feat = by_feature[fname]
        feat["total_gated"] += 1
        outcome = entry.get("outcome", "pass")
        if outcome == "enforced":
            feat["enforced"] += 1
        elif outcome == "warn":
            feat["warned"] += 1
        elif outcome == "relaxed":
            feat["relaxed"] += 1
        else:
            feat["passed"] += 1
        feat["last_guard_mode"] = entry.get("guard_mode")
        feat["last_outcome"] = outcome
        feat["last_timestamp"] = entry.get("timestamp")

    return {
        "total_entries": len(log_copy),
        "guard_mode": get_db_guard_mode().value,
        "by_feature": by_feature,
    }
