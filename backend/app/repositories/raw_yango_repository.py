"""
Raw Yango Repository — manages raw_yango schema tables.

Stores raw data ingested from Yango Fleet API before any transformation.
Uses psycopg2 directly — no SQLAlchemy ORM.
NEVER logs or prints credentials/secrets.
Masks all IDs in log output.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date as dt_date
from datetime import timedelta
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor, execute_values

from app.db.connection import get_db

logger = logging.getLogger(__name__)

_MASK_LEN = 8


def _mask_id(val: Optional[str]) -> str:
    if not val or not isinstance(val, str):
        return "***"
    return val[:_MASK_LEN] + "***" if len(val) > _MASK_LEN else val


def _sanitize_message(msg: Optional[str]) -> Optional[str]:
    if not msg or not isinstance(msg, str):
        return msg
    from app.settings import settings

    secrets = [
        (settings.YANGO_API_KEY or "").strip(),
        (settings.YANGO_CLIENT_ID or "").strip(),
        (settings.DB_PASSWORD or "").strip(),
    ]
    clean = msg[:500]
    for s in secrets:
        if s and len(s) > 4:
            clean = clean.replace(s, "***")
    return clean


def _compute_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sanitize_url(url: str) -> str:
    from app.settings import settings

    safe = url or ""
    for s in (
        (settings.YANGO_API_KEY or "").strip(),
        (settings.YANGO_CLIENT_ID or "").strip(),
    ):
        if s and len(s) > 4:
            safe = safe.replace(s, "***")
    return safe[:500]


# ---------------------------------------------------------------------------
# Ingestion Run Lifecycle
# ---------------------------------------------------------------------------


def create_ingestion_run(
    run_id: str,
    endpoint_group: str,
    park_id: str,
    date_from: str,
    date_to: str,
    max_concurrency: int = 3,
    script_version: Optional[str] = None,
    source: str = "yango_fleet_api",
    status: str = "running",
) -> int:
    """Returns the inserted id."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                INSERT INTO raw_yango.api_ingestion_run (
                    run_id, endpoint_group, park_id,
                    date_from, date_to, max_concurrency,
                    script_version, source, status
                ) VALUES (
                    %(run_id)s, %(endpoint_group)s, %(park_id)s,
                    %(date_from)s, %(date_to)s, %(max_concurrency)s,
                    %(script_version)s, %(source)s, %(status)s
                )
                RETURNING id
            """,
                {
                    "run_id": run_id,
                    "endpoint_group": endpoint_group,
                    "park_id": park_id,
                    "date_from": date_from,
                    "date_to": date_to,
                    "max_concurrency": max_concurrency,
                    "script_version": script_version,
                    "source": source,
                    "status": status,
                },
            )
            row = cur.fetchone()
            inserted_id = row["id"]
            logger.info(
                "Ingestion run created: id=%s run=%s park=%s endpoint=%s status=%s",
                inserted_id,
                _mask_id(run_id),
                _mask_id(park_id),
                endpoint_group,
                status,
            )
            return inserted_id
        finally:
            cur.close()


def finish_ingestion_run(
    run_id: str,
    records_fetched: int,
    records_inserted: int,
    records_updated: int,
    record_skips: int,
    error_count: int = 0,
    warning_count: int = 0,
    notes: Optional[str] = None,
) -> bool:
    """Updates run to status='completed'."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                UPDATE raw_yango.api_ingestion_run
                SET status = 'completed',
                    records_fetched = %(records_fetched)s,
                    records_inserted = %(records_inserted)s,
                    records_updated = %(records_updated)s,
                    record_skips = %(record_skips)s,
                    error_count = %(error_count)s,
                    warning_count = %(warning_count)s,
                    notes = %(notes)s,
                    finished_at = now()
                WHERE run_id = %(run_id)s
            """,
                {
                    "run_id": run_id,
                    "records_fetched": records_fetched,
                    "records_inserted": records_inserted,
                    "records_updated": records_updated,
                    "record_skips": record_skips,
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "notes": notes,
                },
            )
            updated = cur.rowcount > 0
            logger.info(
                "Ingestion run finished: run=%s status=completed inserted=%s skipped=%s errors=%s",
                _mask_id(run_id),
                records_inserted,
                record_skips,
                error_count,
            )
            return updated
        finally:
            cur.close()


def fail_ingestion_run(
    run_id: str,
    error_message: str,
    records_fetched: int = 0,
    records_inserted: int = 0,
    error_count: int = 0,
) -> bool:
    """Updates run to status='failed'."""
    clean_msg = _sanitize_message(error_message)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                UPDATE raw_yango.api_ingestion_run
                SET status = 'failed',
                    records_fetched = %(records_fetched)s,
                    records_inserted = %(records_inserted)s,
                    error_count = %(error_count)s,
                    notes = %(notes)s,
                    finished_at = now()
                WHERE run_id = %(run_id)s
            """,
                {
                    "run_id": run_id,
                    "records_fetched": records_fetched,
                    "records_inserted": records_inserted,
                    "error_count": error_count,
                    "notes": clean_msg[:1000] if clean_msg else None,
                },
            )
            updated = cur.rowcount > 0
            logger.warning(
                "Ingestion run failed: run=%s error=%s",
                _mask_id(run_id),
                clean_msg[:200] if clean_msg else "unknown",
            )
            return updated
        finally:
            cur.close()


# ---------------------------------------------------------------------------
# Credential Registry
# ---------------------------------------------------------------------------


def get_active_park_credentials() -> List[Dict[str, Any]]:
    """Returns list of active credential registries (no actual keys)."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT id, park_id, fleet_name, country, city,
                       env_var_name, api_base_url, is_active
                FROM raw_yango.api_park_credentials_registry
                WHERE is_active = true
                ORDER BY park_id
            """
            )
            rows = cur.fetchall()
            result = []
            for r in rows:
                result.append(
                    {
                        "id": r["id"],
                        "park_id": r["park_id"],
                        "park_id_masked": _mask_id(r["park_id"]),
                        "fleet_name": r["fleet_name"],
                        "country": r["country"],
                        "city": r["city"],
                        "env_var_name": r["env_var_name"],
                        "api_base_url": r["api_base_url"],
                        "is_active": r["is_active"],
                    }
                )
            return result
        finally:
            cur.close()


def get_credential_for_park(park_id: str) -> Optional[Dict[str, Any]]:
    """Look up credential registry entry for a park. Returns env_var_name only, never the key."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT id, park_id, fleet_name, country, city,
                       env_var_name, api_base_url, is_active
                FROM raw_yango.api_park_credentials_registry
                WHERE park_id = %(park_id)s AND is_active = true
                LIMIT 1
            """,
                {"park_id": park_id},
            )
            r = cur.fetchone()
            if r:
                return {
                    "id": r["id"],
                    "park_id": r["park_id"],
                    "fleet_name": r["fleet_name"],
                    "country": r["country"],
                    "city": r["city"],
                    "env_var_name": r["env_var_name"],
                    "api_base_url": r["api_base_url"],
                    "is_active": r["is_active"],
                }
            return None
        finally:
            cur.close()


def check_existing_run(
    park_id: str, endpoint_group: str, date_from: str, date_to: str
) -> Optional[Dict[str, Any]]:
    """Check for existing completed/running runs for same park/date/endpoint."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT run_id, status, records_fetched, records_inserted,
                       error_count, started_at, finished_at
                FROM raw_yango.api_ingestion_run
                WHERE park_id = %(park_id)s
                  AND endpoint_group = %(endpoint_group)s
                  AND date_from = %(date_from)s
                  AND date_to = %(date_to)s
                ORDER BY started_at DESC
                LIMIT 1
            """,
                {
                    "park_id": park_id,
                    "endpoint_group": endpoint_group,
                    "date_from": date_from,
                    "date_to": date_to,
                },
            )
            r = cur.fetchone()
            if r:
                return {
                    "run_id": r["run_id"],
                    "status": r["status"],
                    "records_fetched": r["records_fetched"] or 0,
                    "records_inserted": r["records_inserted"] or 0,
                    "error_count": r["error_count"] or 0,
                    "started_at": (
                        r["started_at"].isoformat() if r["started_at"] else None
                    ),
                    "finished_at": (
                        r["finished_at"].isoformat() if r["finished_at"] else None
                    ),
                }
            return None
        finally:
            cur.close()


# ---------------------------------------------------------------------------
# Upsert Orders
# ---------------------------------------------------------------------------


def upsert_orders_raw(
    conn,
    orders: List[Dict[str, Any]],
    park_id: str,
    api_run_id: str,
    api_fetched_at: str,
) -> Dict[str, int]:
    """Batch upsert orders. Returns {inserted, updated, skipped}."""
    if not orders:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    rows = []
    for o in orders:
        if not isinstance(o, dict):
            continue
        payload = o.get("raw_payload", o)
        payload_hash = _compute_hash(payload) if isinstance(payload, dict) else ""
        rows.append(
            (
                o.get("order_id") or o.get("id", ""),
                park_id,
                o.get("order_status") or o.get("status"),
                o.get("order_created_at") or o.get("created_at"),
                o.get("order_booked_at") or o.get("booked_at"),
                o.get("order_ended_at") or o.get("ended_at"),
                o.get("driver_profile_id"),
                o.get("car_id"),
                o.get("category"),
                o.get("payment_method"),
                o.get("provider"),
                o.get("price"),
                o.get("mileage"),
                json.dumps(payload, ensure_ascii=False, default=str)
                if isinstance(payload, dict)
                else json.dumps(o, ensure_ascii=False, default=str),
                payload_hash,
                api_run_id,
                api_fetched_at,
                o.get("source_endpoint", "orders/list"),
                o.get("schema_version", "1.0"),
            )
        )

    if not rows:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    cur = conn.cursor()
    try:
        execute_values(
            cur,
            """
            INSERT INTO raw_yango.orders_raw (
                order_id, park_id, order_status, order_created_at, order_booked_at,
                order_ended_at, driver_profile_id, car_id, category, payment_method,
                provider, price, mileage, raw_payload, raw_payload_hash,
                api_run_id, api_fetched_at, source_endpoint, schema_version
            ) VALUES %s
            ON CONFLICT (order_id, park_id) DO NOTHING
        """,
            rows,
            template=None,
            page_size=1000,
        )
        inserted = cur.rowcount
        total = len(rows)
        skipped = total - inserted
        logger.debug(
            "upsert_orders_raw: total=%s inserted=%s skipped=%s park=%s",
            total,
            inserted,
            skipped,
            _mask_id(park_id),
        )
        return {"inserted": inserted, "updated": 0, "skipped": skipped}
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Upsert Transactions
# ---------------------------------------------------------------------------


def upsert_transactions_raw(
    conn,
    transactions: List[Dict[str, Any]],
    park_id: str,
    api_run_id: str,
    api_fetched_at: str,
) -> Dict[str, int]:
    """Batch upsert transactions. Returns {inserted, updated, skipped}."""
    if not transactions:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    rows = []
    for t in transactions:
        if not isinstance(t, dict):
            continue
        payload = t.get("raw_payload", t)
        payload_hash = _compute_hash(payload) if isinstance(payload, dict) else ""
        tx_id = (
            t.get("transaction_id")
            or t.get("id")
            or t.get("transactionId", "")
        )
        rows.append(
            (
                tx_id,
                park_id,
                t.get("transaction_status") or t.get("status"),
                t.get("transaction_created_at")
                or t.get("created_at")
                or t.get("event_at"),
                t.get("transaction_updated_at") or t.get("updated_at"),
                t.get("driver_profile_id"),
                t.get("car_id"),
                t.get("category"),
                t.get("amount") or t.get("total"),
                json.dumps(payload, ensure_ascii=False, default=str)
                if isinstance(payload, dict)
                else json.dumps(t, ensure_ascii=False, default=str),
                payload_hash,
                api_run_id,
                api_fetched_at,
                t.get("source_endpoint", "transactions/list"),
                t.get("schema_version", "1.0"),
            )
        )

    if not rows:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    cur = conn.cursor()
    try:
        execute_values(
            cur,
            """
            INSERT INTO raw_yango.transactions_raw (
                transaction_id, park_id, transaction_status, transaction_created_at,
                transaction_updated_at, driver_profile_id, car_id, category,
                amount, raw_payload, raw_payload_hash,
                api_run_id, api_fetched_at, source_endpoint, schema_version
            ) VALUES %s
            ON CONFLICT (transaction_id, park_id) DO NOTHING
        """,
            rows,
            template=None,
            page_size=1000,
        )
        inserted = cur.rowcount
        total = len(rows)
        skipped = total - inserted
        logger.debug(
            "upsert_transactions_raw: total=%s inserted=%s skipped=%s park=%s",
            total,
            inserted,
            skipped,
            _mask_id(park_id),
        )
        return {"inserted": inserted, "updated": 0, "skipped": skipped}
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Upsert Driver Profiles
# ---------------------------------------------------------------------------


def upsert_driver_profiles_raw(
    conn,
    profiles: List[Dict[str, Any]],
    park_id: str,
    api_run_id: str,
    api_fetched_at: str,
) -> Dict[str, int]:
    """Batch upsert driver profiles. Returns {inserted, updated, skipped}."""
    if not profiles:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    rows = []
    for p in profiles:
        if not isinstance(p, dict):
            continue
        dp_id = (
            (p.get("driver_profile") or {}).get("id")
            or p.get("driver_profile_id")
            or p.get("id", "")
        )
        if not dp_id:
            continue
        payload_hash = _compute_hash(p)
        rows.append(
            (
                dp_id,
                park_id,
                json.dumps(p, ensure_ascii=False, default=str),
                payload_hash,
                api_run_id,
                api_fetched_at,
                p.get("source_endpoint", "driver-profiles/list"),
                p.get("schema_version", "1.0"),
            )
        )

    if not rows:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    cur = conn.cursor()
    try:
        execute_values(
            cur,
            """
            INSERT INTO raw_yango.driver_profiles_raw (
                driver_profile_id, park_id, profile_raw, raw_payload_hash,
                api_run_id, api_fetched_at, source_endpoint, schema_version
            ) VALUES %s
            ON CONFLICT (driver_profile_id, park_id) DO NOTHING
        """,
            rows,
            template=None,
            page_size=1000,
        )
        inserted = cur.rowcount
        total = len(rows)
        skipped = total - inserted
        logger.debug(
            "upsert_driver_profiles_raw: total=%s inserted=%s skipped=%s park=%s",
            total,
            inserted,
            skipped,
            _mask_id(park_id),
        )
        return {"inserted": inserted, "updated": 0, "skipped": skipped}
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Ingestion Errors
# ---------------------------------------------------------------------------


def insert_ingestion_error(
    run_id: str,
    park_id: str,
    endpoint_group: str,
    endpoint_url: str,
    request_params: Optional[str],
    status_code: int,
    error_type: str,
    error_message: str,
    retry_count: int = 0,
) -> int:
    """Returns inserted id. Sanitizes url and error message before storing."""
    from app.settings import settings

    safe_url = _sanitize_url(endpoint_url)

    safe_params = request_params
    if safe_params:
        for s in (
            (settings.YANGO_API_KEY or "").strip(),
            (settings.YANGO_CLIENT_ID or "").strip(),
        ):
            if s and len(s) > 4:
                safe_params = safe_params.replace(s, "***")

    safe_msg = (
        _sanitize_message(error_message)[:1000] if error_message else None
    )

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                INSERT INTO raw_yango.ingestion_errors (
                    run_id, park_id, endpoint_group, endpoint_url,
                    request_params, status_code, error_type,
                    error_message, retry_count
                ) VALUES (
                    %(run_id)s, %(park_id)s, %(endpoint_group)s, %(endpoint_url)s,
                    %(request_params)s, %(status_code)s, %(error_type)s,
                    %(error_message)s, %(retry_count)s
                )
                RETURNING id
            """,
                {
                    "run_id": run_id,
                    "park_id": park_id,
                    "endpoint_group": endpoint_group,
                    "endpoint_url": safe_url,
                    "request_params": safe_params[:2000] if safe_params else None,
                    "status_code": status_code,
                    "error_type": error_type,
                    "error_message": safe_msg,
                    "retry_count": retry_count,
                },
            )
            row = cur.fetchone()
            eid = row["id"]
            logger.warning(
                "Ingestion error logged: id=%s run=%s endpoint=%s status=%s type=%s",
                eid,
                _mask_id(run_id),
                endpoint_group,
                status_code,
                error_type,
            )
            return eid
        finally:
            cur.close()


# ---------------------------------------------------------------------------
# Coverage Summary
# ---------------------------------------------------------------------------


def get_raw_coverage_summary(
    park_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Returns coverage stats: distinct dates, counts, days with data, missing days."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            park_filter = "AND park_id = %(park_id)s" if park_id else ""
            params: Dict[str, Any] = {}
            if park_id:
                params["park_id"] = park_id

            df_parts: List[str] = []
            if date_from:
                params["date_from"] = date_from
                df_parts.append("api_fetched_at::date >= %(date_from)s")
            if date_to:
                params["date_to"] = date_to
                df_parts.append("api_fetched_at::date <= %(date_to)s")
            date_filter = "AND " + " AND ".join(df_parts) if df_parts else ""

            cur.execute(
                f"""
                SELECT COUNT(DISTINCT DATE(api_fetched_at)) AS distinct_dates,
                       COUNT(*) AS orders_count
                FROM raw_yango.orders_raw
                WHERE 1=1 {park_filter} {date_filter}
            """,
                params,
            )
            orders_row = cur.fetchone()

            cur.execute(
                f"""
                SELECT COUNT(*) AS txn_count
                FROM raw_yango.transactions_raw
                WHERE 1=1 {park_filter} {date_filter}
            """,
                params,
            )
            txn_row = cur.fetchone()

            cur.execute(
                f"""
                SELECT COUNT(*) AS profiles_count
                FROM raw_yango.driver_profiles_raw
                WHERE 1=1 {park_filter} {date_filter}
            """,
                params,
            )
            profiles_row = cur.fetchone()

            cur.execute(
                f"""
                SELECT COUNT(*) AS revenue_candidate_count
                FROM raw_yango.orders_raw
                WHERE 1=1 {park_filter} {date_filter}
                  AND price IS NOT NULL AND price > 0
            """,
                params,
            )
            rev_row = cur.fetchone()

            dates_set: set = set()
            if date_from and date_to:
                fd = dt_date.fromisoformat(date_from)
                td = dt_date.fromisoformat(date_to)
                cur_d = fd
                while cur_d <= td:
                    dates_set.add(cur_d.isoformat())
                    cur_d += timedelta(days=1)

            cur.execute(
                f"""
                SELECT DISTINCT DATE(api_fetched_at) AS d
                FROM raw_yango.orders_raw
                WHERE 1=1 {park_filter} {date_filter}
                UNION
                SELECT DISTINCT DATE(api_fetched_at) AS d
                FROM raw_yango.transactions_raw
                WHERE 1=1 {park_filter} {date_filter}
                UNION
                SELECT DISTINCT DATE(api_fetched_at) AS d
                FROM raw_yango.driver_profiles_raw
                WHERE 1=1 {park_filter} {date_filter}
            """,
                params,
            )
            existing_dates: set = set()
            for r in cur.fetchall():
                if r["d"]:
                    existing_dates.add(
                        r["d"].isoformat()
                        if hasattr(r["d"], "isoformat")
                        else str(r["d"])
                    )

            missing_days = (
                sorted(dates_set - existing_dates) if dates_set else []
            )

            return {
                "distinct_dates": orders_row["distinct_dates"] or 0
                if orders_row
                else 0,
                "orders_count": orders_row["orders_count"] or 0
                if orders_row
                else 0,
                "transactions_count": txn_row["txn_count"] or 0
                if txn_row
                else 0,
                "profiles_count": profiles_row["profiles_count"] or 0
                if profiles_row
                else 0,
                "revenue_candidate_count": rev_row["revenue_candidate_count"] or 0
                if rev_row
                else 0,
                "days_with_data": len(existing_dates),
                "missing_days": missing_days,
                "park_id_masked": _mask_id(park_id) if park_id else None,
            }
        finally:
            cur.close()


# ---------------------------------------------------------------------------
# Ingestion Reliability Hardening (OV2-B.6B)
# ---------------------------------------------------------------------------


def update_ingestion_heartbeat(run_id: str, current_page: int = 0,
                                last_cursor: Optional[str] = None,
                                next_cursor: Optional[str] = None) -> bool:
    """Update heartbeat timestamp and page progress."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE raw_yango.api_ingestion_run
                SET heartbeat_at = now(),
                    current_page = COALESCE(%(current_page)s, current_page),
                    last_cursor = COALESCE(%(last_cursor)s, last_cursor),
                    next_cursor = %(next_cursor)s
                WHERE run_id = %(run_id)s
                """,
                {
                    "run_id": run_id,
                    "current_page": current_page,
                    "last_cursor": last_cursor,
                    "next_cursor": next_cursor,
                },
            )
            return cur.rowcount > 0
        finally:
            cur.close()


def update_ingestion_counters(run_id: str, fetched: int = 0, inserted: int = 0,
                               updated: int = 0, skipped: int = 0,
                               errors: int = 0, pages_completed: int = 0) -> bool:
    """Increment counters during ingestion."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE raw_yango.api_ingestion_run
                SET records_fetched = COALESCE(records_fetched, 0) + %(fetched)s,
                    records_inserted = COALESCE(records_inserted, 0) + %(inserted)s,
                    records_updated = COALESCE(records_updated, 0) + %(updated)s,
                    record_skips = COALESCE(record_skips, 0) + %(skipped)s,
                    error_count = COALESCE(error_count, 0) + %(errors)s,
                    pages_completed = COALESCE(pages_completed, 0) + %(pages_completed)s,
                    heartbeat_at = now()
                WHERE run_id = %(run_id)s
                """,
                {
                    "run_id": run_id,
                    "fetched": fetched,
                    "inserted": inserted,
                    "updated": updated,
                    "skipped": skipped,
                    "errors": errors,
                    "pages_completed": pages_completed,
                },
            )
            return cur.rowcount > 0
        finally:
            cur.close()


def set_ingestion_expected_pages(run_id: str, expected: int) -> bool:
    """Set expected total pages for coverage tracking."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE raw_yango.api_ingestion_run SET expected_pages = %s WHERE run_id = %s",
                (expected, run_id),
            )
            return cur.rowcount > 0
        finally:
            cur.close()


def set_ingestion_status(run_id: str, status: str) -> bool:
    """Explicitly set run status. Use for stalled/recovery transitions."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE raw_yango.api_ingestion_run SET status = %s, finished_at = CASE WHEN %s IN ('completed','failed','stalled','cancelled') THEN now() ELSE finished_at END WHERE run_id = %s",
                (status, status, run_id),
            )
            return cur.rowcount > 0
        finally:
            cur.close()


def mark_stalled_runs(park_id: str, stale_minutes: int = 30) -> int:
    """Mark runs with stale heartbeat as stalled. Returns count affected."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE raw_yango.api_ingestion_run
                SET status = 'stalled',
                    finished_at = now(),
                    notes = COALESCE(notes, '') || ' [auto-stalled: no heartbeat for ' || %s || ' min]'
                WHERE park_id = %s
                  AND status IN ('started', 'running')
                  AND (heartbeat_at IS NULL OR heartbeat_at < now() - make_interval(mins := %s))
                """,
                (str(stale_minutes), park_id, stale_minutes),
            )
            count = cur.rowcount
            logger.warning(
                "Marked %s stalled runs for park %s (stale > %s min)",
                count, _mask_id(park_id), stale_minutes,
            )
            return count
        finally:
            cur.close()


def get_stalled_runs(park_id: str, stale_minutes: int = 30) -> list:
    """Get list of runs that appear stalled."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT run_id, endpoint_group, status, current_page,
                       last_cursor, next_cursor, pages_completed, expected_pages,
                       records_fetched, records_inserted, error_count,
                       started_at, heartbeat_at,
                       EXTRACT(EPOCH FROM (now() - COALESCE(heartbeat_at, started_at)))/60 AS stale_min
                FROM raw_yango.api_ingestion_run
                WHERE park_id = %s
                  AND status IN ('started', 'running')
                  AND (heartbeat_at IS NULL OR heartbeat_at < now() - make_interval(mins := %s))
                ORDER BY started_at
                """,
                (park_id, stale_minutes),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()


def get_completed_runs(park_id: str, date_from: Optional[str] = None,
                       date_to: Optional[str] = None) -> list:
    """Get completed/succeeded runs for a park/date range."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            params = [park_id]
            extras = ""
            if date_from:
                params.append(date_from)
                extras += " AND date_from = %s"
            if date_to:
                params.append(date_to)
                extras += " AND date_to = %s"

            cur.execute(
                f"""
                SELECT run_id, endpoint_group, status,
                       records_fetched, records_inserted,
                       pages_completed, expected_pages,
                       started_at, finished_at
                FROM raw_yango.api_ingestion_run
                WHERE park_id = %s AND status = 'completed'{extras}
                ORDER BY started_at
                """,
                tuple(params),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()


# ── Page Checkpoint ──────────────────────────────────────────


def init_page_checkpoints(run_id: str, park_id: str, endpoint_group: str,
                          target_date: str, total_pages: int,
                          partition_key: Optional[str] = None) -> int:
    """Initialize checkpoint rows for all expected pages. Returns count created."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            from psycopg2.extras import execute_values

            rows = [
                (run_id, park_id, endpoint_group, target_date,
                 partition_key, page_num, None, "pending")
                for page_num in range(1, total_pages + 1)
            ]
            execute_values(
                cur,
                """
                INSERT INTO raw_yango.api_ingestion_page_checkpoint
                    (run_id, park_id, endpoint_group, target_date,
                     partition_key, page_number, cursor_value, status)
                VALUES %s
                ON CONFLICT (run_id, page_number) DO NOTHING
                """,
                rows,
                page_size=100,
            )
            count = cur.rowcount
            logger.info(
                "Initialized %s page checkpoints for run %s (%s pages)",
                count, _mask_id(run_id), total_pages,
            )
            return count
        finally:
            cur.close()


def record_page_completed(run_id: str, page_number: int,
                          records_count: int = 0,
                          records_inserted: int = 0,
                          cursor_value: Optional[str] = None) -> bool:
    """Mark a page as completed in the checkpoint registry."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO raw_yango.api_ingestion_page_checkpoint
                    (run_id, park_id, endpoint_group, target_date,
                     partition_key, page_number, cursor_value, status,
                     records_count, records_inserted, started_at, finished_at)
                VALUES (%(run_id)s, '', '', '1970-01-01',
                        '', %(page_number)s, %(cursor_value)s, 'inserted',
                        %(records_count)s, %(records_inserted)s, now(), now())
                ON CONFLICT (run_id, page_number)
                DO UPDATE SET
                    status = 'inserted',
                    records_count = EXCLUDED.records_count,
                    records_inserted = EXCLUDED.records_inserted,
                    cursor_value = COALESCE(EXCLUDED.cursor_value,
                                            api_ingestion_page_checkpoint.cursor_value),
                    finished_at = now(),
                    updated_at = now()
                """,
                {
                    "run_id": run_id,
                    "page_number": page_number,
                    "cursor_value": cursor_value,
                    "records_count": records_count,
                    "records_inserted": records_inserted,
                },
            )
            return cur.rowcount > 0
        finally:
            cur.close()


def record_page_failed(run_id: str, page_number: int,
                       error_message: Optional[str] = None) -> bool:
    """Mark a page as failed."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO raw_yango.api_ingestion_page_checkpoint
                    (run_id, park_id, endpoint_group, target_date,
                     partition_key, page_number, status, error_message_sanitized,
                     started_at, finished_at)
                VALUES (%(run_id)s, '', '', '1970-01-01',
                        '', %(page_number)s, 'failed', %(error)s, now(), now())
                ON CONFLICT (run_id, page_number)
                DO UPDATE SET
                    status = 'failed',
                    error_message_sanitized = %(error)s,
                    finished_at = now(),
                    updated_at = now()
                """,
                {
                    "run_id": run_id,
                    "page_number": page_number,
                    "error": _sanitize_message(error_message)[:500] if error_message else None,
                },
            )
            return cur.rowcount > 0
        finally:
            cur.close()


def get_missing_pages(run_id: str) -> list:
    """Get pages not yet inserted for a run."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT page_number, status, cursor_value, records_count,
                       error_message_sanitized
                FROM raw_yango.api_ingestion_page_checkpoint
                WHERE run_id = %s AND status != 'inserted'
                ORDER BY page_number
                """,
                (run_id,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()


def get_page_checkpoint_summary(run_id: str) -> Dict[str, Any]:
    """Get summary of page checkpoint progress."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_pages,
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending_pages,
                    COUNT(*) FILTER (WHERE status = 'inserted') AS completed_pages,
                    COUNT(*) FILTER (WHERE status = 'failed') AS failed_pages,
                    COUNT(*) FILTER (WHERE status = 'fetched') AS fetched_pages,
                    SUM(records_count) AS total_records,
                    SUM(records_inserted) AS total_inserted
                FROM raw_yango.api_ingestion_page_checkpoint
                WHERE run_id = %s
                """,
                (run_id,),
            )
            r = cur.fetchone()
            if not r:
                return {}
            return {
                "total_pages": int(r["total_pages"] or 0),
                "pending": int(r["pending_pages"] or 0),
                "completed": int(r["completed_pages"] or 0),
                "failed": int(r["failed_pages"] or 0),
                "fetched": int(r["fetched_pages"] or 0),
                "total_records": int(r["total_records"] or 0),
                "total_inserted": int(r["total_inserted"] or 0),
            }
        finally:
            cur.close()
