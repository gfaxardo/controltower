"""
Omniview V2 Snapshot Repository — CRUD for serving snapshots.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

TABLE = "ops.omniview_v2_serving_snapshot"


def _query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
    except Exception as e:
        logger.error("Snapshot repo error: %s", str(e)[:200])
        return []


def _query_one(sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    rows = _query(sql, params)
    return rows[0] if rows else None


def _exec(sql: str, params: tuple = ()) -> bool:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            cur.close()
            return True
    except Exception as e:
        logger.error("Snapshot exec error: %s", str(e)[:200])
        return False


def _payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def get_snapshot(
    source_system: str,
    grain: str,
    operating_date: str,
    payload_type: str,
) -> Optional[Dict[str, Any]]:
    return _query_one(
        f"SELECT * FROM {TABLE} WHERE source_system=%s AND grain=%s AND operating_date=%s AND payload_type=%s AND status='READY' ORDER BY generated_at DESC LIMIT 1",
        (source_system, grain, operating_date, payload_type),
    )


def get_snapshot_payload_fast(
    source_system: str,
    grain: str,
    operating_date: str,
    payload_type: str,
) -> Optional[Dict[str, Any]]:
    """Fast path: raw cursor, only payload + metadata columns, no dict conversion."""
    try:
        with get_db() as conn:
            cur = conn.cursor()  # raw cursor — no RealDictCursor overhead
            cur.execute(
                f"SELECT payload, generated_at, coverage_pct, freshness_status, status "
                f"FROM {TABLE} "
                f"WHERE source_system=%s AND grain=%s AND operating_date=%s AND payload_type=%s AND status='READY' "
                f"ORDER BY generated_at DESC LIMIT 1",
                (source_system, grain, operating_date, payload_type),
            )
            row = cur.fetchone()
            cur.close()
            if row:
                payload = row[0]
                if isinstance(payload, str):
                    import json
                    payload = json.loads(payload)
                return {
                    "payload": payload,
                    "generated_at": row[1].isoformat() if hasattr(row[1], "isoformat") and row[1] else None,
                    "coverage_pct": float(row[2] or 0),
                    "freshness_status": row[3] or "FRESH",
                    "status": row[4] or "READY",
                }
    except Exception as e:
        logger.error("Snapshot fast path error: %s", str(e)[:200])
    return None


def upsert_snapshot(
    source_system: str,
    grain: str,
    operating_date: str,
    payload_type: str,
    payload: dict,
    status: str = "READY",
    coverage_pct: float = 0.0,
    freshness_status: str = "FRESH",
    build_ms: int = 0,
    source_tables: Optional[list] = None,
    warnings: Optional[list] = None,
    expires_at: Optional[str] = None,
) -> bool:
    ph = _payload_hash(payload)
    st = json.dumps(source_tables or [], default=str)
    wj = json.dumps(warnings or [], default=str)
    pj = json.dumps(payload, default=str, ensure_ascii=False)

    return _exec(
        f"""
        INSERT INTO {TABLE} (source_system, grain, operating_date, payload_type, payload,
            status, coverage_pct, freshness_status, build_ms, source_tables, warnings,
            payload_hash, expires_at, generated_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, now())
        ON CONFLICT (source_system, grain, operating_date, payload_type)
        DO UPDATE SET payload=%s::jsonb, status=%s, coverage_pct=%s, freshness_status=%s,
            build_ms=%s, source_tables=%s::jsonb, warnings=%s::jsonb, payload_hash=%s,
            expires_at=%s, generated_at=now(), updated_at=now()
        """,
        (source_system, grain, operating_date, payload_type, pj,
         status, coverage_pct, freshness_status, build_ms, st, wj, ph, expires_at,
         pj, status, coverage_pct, freshness_status, build_ms, st, wj, ph, expires_at),
    )


def mark_snapshot_failed(
    source_system: str,
    grain: str,
    operating_date: str,
    payload_type: str,
    error_message: str,
) -> bool:
    return _exec(
        f"INSERT INTO {TABLE} (source_system, grain, operating_date, payload_type, payload, status, warnings) "
        "VALUES (%s, %s, %s, %s, '{}', 'FAILED', %s::jsonb) "
        "ON CONFLICT (source_system, grain, operating_date, payload_type) "
        "DO UPDATE SET status='FAILED', warnings=%s::jsonb, updated_at=now()",
        (source_system, grain, operating_date, payload_type,
         json.dumps([{"code": "SNAPSHOT_FAILED", "message": error_message[:500]}]),
         json.dumps([{"code": "SNAPSHOT_FAILED", "message": error_message[:500]}])),
    )


def snapshot_exists(
    source_system: str,
    grain: str,
    operating_date: str,
    payload_type: str,
) -> bool:
    row = _query_one(
        f"SELECT 1 FROM {TABLE} WHERE source_system=%s AND grain=%s AND operating_date=%s AND payload_type=%s AND status='READY' LIMIT 1",
        (source_system, grain, operating_date, payload_type),
    )
    return row is not None


def get_snapshot_health() -> Dict[str, Any]:
    row = _query_one(f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status='READY') AS ready,
            COUNT(*) FILTER (WHERE status='STALE') AS stale,
            COUNT(*) FILTER (WHERE status='FAILED') AS failed,
            MAX(generated_at) AS last_generated
        FROM {TABLE}
    """)
    if not row:
        return {"total": 0, "ready": 0, "stale": 0, "failed": 0}
    return {
        "total": int(row.get("total", 0) or 0),
        "ready": int(row.get("ready", 0) or 0),
        "stale": int(row.get("stale", 0) or 0),
        "failed": int(row.get("failed", 0) or 0),
        "last_generated": row.get("last_generated").isoformat() if row.get("last_generated") and hasattr(row["last_generated"], "isoformat") else None,
    }
