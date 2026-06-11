"""
YEGO Lima Growth — Yango Raw Tick Ingestion Service (LG-CF-HOTFIX-1H)

Lightweight synchronous wrapper for Yango orders ingestion.
Called by autonomous_tick before rollover detection.
Max 3-day backfill. Cursor pagination. Idempotent (ON CONFLICT).
LG-CF-HOTFIX-1H: Batch insert, skip-duplicate, real timeout, page limit.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import requests
from psycopg2.extras import execute_values

from app.db.connection import get_db
from app.repositories.raw_yango_repository import get_credential_for_park
from app.settings import settings

logger = logging.getLogger(__name__)

PET = timezone(timedelta(hours=-5))
API_BASE_URL_DEFAULT = "https://fleet-api.yango.tech"
ORDERS_PATH = "/v1/parks/orders/list"
PAGE_SIZE = 500
MAX_DAYS_BACKFILL = 3
MAX_PAGES_PER_DATE = 500
REQUEST_TIMEOUT = 30
MAX_TOTAL_SECONDS = 600
MIN_INTER_REQUEST = 0.5
DEDUP_WINDOW_HOURS = 3


def _get_active_park_id() -> Optional[str]:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT park_id FROM raw_yango.api_park_credentials_registry "
                "WHERE is_active = true ORDER BY park_id LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
    except Exception as e:
        logger.warning("Failed to resolve active park_id: %s", e)
    return None


def _now_iso():
    return datetime.now(PET).isoformat()


def _today():
    return datetime.now(PET).date()


def _get_yango_credentials(cred: dict) -> tuple:
    prefix = cred.get("env_var_name", "")
    sources = [
        (f"{prefix}_CLIENT_ID", f"{prefix}_API_KEY", "env_prefix"),
        ("YANGO_CLIENT_ID", "YANGO_API_KEY", "env_legacy"),
    ]
    for client_key, api_key_name, source in sources:
        client_id = os.environ.get(client_key) or getattr(settings, client_key, None)
        api_key = os.environ.get(api_key_name) or getattr(settings, api_key_name, None)
        if client_id and api_key:
            return client_id, api_key, source

    return None, None, "missing"


def _mask(val: str) -> str:
    if not val:
        return "***"
    return val[:4] + "***" + val[-2:] if len(val) > 6 else "***"


def ingest_recent_orders(
    max_days: int = MAX_DAYS_BACKFILL,
    park_id: str = None,
) -> Dict[str, Any]:
    start_ts = time.time()
    result = {
        "attempted": True,
        "park_id_used": None,
        "env_prefix_used": None,
        "credential_source": None,
        "dates_attempted": [],
        "dates_skipped": [],
        "dates_inserted": [],
        "total_inserted": 0,
        "total_skipped": 0,
        "api_empty_dates": [],
        "api_errors": [],
    }

    if not park_id:
        park_id = _get_active_park_id()
    result["park_id_used"] = park_id

    if not park_id:
        result["error"] = "No active park found in api_park_credentials_registry"
        return result

    cred = get_credential_for_park(park_id)
    if not cred:
        result["error"] = f"No credentials found for park {park_id}"
        return result

    result["env_prefix_used"] = cred.get("env_var_name", "")

    client_id, api_key, cred_source = _get_yango_credentials(cred)
    result["credential_source"] = cred_source
    if not api_key or not client_id:
        result["error"] = f"Missing Yango API credentials (tried prefix={cred.get('env_var_name')}, legacy YANGO_CLIENT_ID/API_KEY, settings)"
        return result

    base_url = cred.get("api_base_url") or settings.YANGO_API_BASE_URL or API_BASE_URL_DEFAULT
    headers = {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    today = _today()
    dates_to_fetch = []
    for i in range(max_days):
        d = today - timedelta(days=i)
        dates_to_fetch.append(d.strftime("%Y-%m-%d"))

    logger.info("Yango tick ingestion: attempting %d dates (latest first)", len(dates_to_fetch))

    for date_str in dates_to_fetch:
        if time.time() - start_ts > MAX_TOTAL_SECONDS:
            result["timeout_after"] = date_str
            logger.warning("Yango tick ingestion: timeout after %d seconds", MAX_TOTAL_SECONDS)
            break

        result["dates_attempted"].append(date_str)

        try:
            page_result = _fetch_orders_for_date(date_str, park_id, base_url, headers, start_ts)
            if page_result.get("status") == "skipped_already_ingested":
                result["total_skipped"] += page_result.get("existing_fetched", 0)
                result["dates_skipped"].append(date_str)
                continue
            result["total_inserted"] += page_result.get("inserted", 0)
            result["total_skipped"] += page_result.get("skipped", 0)
            if page_result.get("inserted", 0) > 0:
                result["dates_inserted"].append(date_str)
            elif page_result.get("api_empty", False):
                result["api_empty_dates"].append(date_str)
            if page_result.get("error"):
                result["api_errors"].append({"date": date_str, "error": page_result["error"]})
            if page_result.get("status") in ("partial_timeout", "partial_page_limit", "failed"):
                result["api_errors"].append({"date": date_str,
                    "error": f"{page_result['status']}: {page_result.get('error', '')}"})
        except Exception as e:
            result["api_errors"].append({"date": date_str, "error": str(e)[:200]})
            logger.warning("Yango tick ingestion: error fetching %s: %s", date_str, e)

    result["duration_seconds"] = round(time.time() - start_ts, 1)
    logger.info("Yango tick ingestion: inserted=%d skipped=%d dates=%d duration=%.1fs",
                result["total_inserted"], result["total_skipped"],
                len(result["dates_attempted"]), result["duration_seconds"])
    return result


def _is_date_already_ingested(park_id: str, date_str: str) -> Optional[dict]:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT run_id, status, records_fetched, records_inserted, record_skips "
                "FROM raw_yango.api_ingestion_run "
                "WHERE park_id = %(p)s AND endpoint_group = 'orders' "
                "  AND date_from = %(d)s AND date_to = %(d)s "
                "  AND status = 'completed' AND records_fetched > 0 "
                "ORDER BY finished_at DESC LIMIT 1",
                {"p": park_id, "d": date_str}
            )
            row = cur.fetchone()
            if row:
                return {"run_id": row[0], "status": row[1],
                        "fetched": row[2], "inserted": row[3], "skipped": row[4]}
    except Exception:
        pass
    return None


def _fetch_orders_for_date(
    date_str: str,
    park_id: str,
    base_url: str,
    headers: dict,
    tick_start_ts: float = None,
) -> Dict[str, Any]:
    result = {"inserted": 0, "skipped": 0, "api_empty": False, "status": "completed"}

    existing = _is_date_already_ingested(park_id, date_str)
    if existing:
        result["status"] = "skipped_already_ingested"
        result["existing_run_id"] = existing["run_id"]
        result["existing_fetched"] = existing["fetched"]
        result["existing_inserted"] = existing["inserted"]
        result["existing_skipped"] = existing["skipped"]
        return result

    url = f"{base_url.rstrip('/')}{ORDERS_PATH}"
    from_dt = f"{date_str}T00:00:00-0500"
    to_dt = f"{date_str}T23:59:59-0500"
    base_body = {
        "limit": PAGE_SIZE,
        "query": {
            "park": {
                "id": park_id,
                "order": {
                    "ended_at": {"from": from_dt, "to": to_dt},
                    "statuses": ["complete"],
                }
            }
        }
    }

    run_uuid = str(uuid4())
    _record_ingestion_run_start(run_uuid, park_id, "orders", date_str, date_str)

    cursor = None
    page_count = 0
    total_fetched = 0
    page_start_ts = time.time()

    try:
        while True:
            if tick_start_ts and time.time() - tick_start_ts > MAX_TOTAL_SECONDS:
                result["status"] = "partial_timeout"
                result["error"] = f"Timeout after {MAX_TOTAL_SECONDS}s"
                _record_ingestion_run_partial(run_uuid, "partial_timeout",
                                              total_fetched, result["inserted"], result["skipped"],
                                              f"Timeout after {MAX_TOTAL_SECONDS}s")
                return result

            if page_count >= MAX_PAGES_PER_DATE:
                result["status"] = "partial_page_limit"
                result["page_limit_reached"] = True
                _record_ingestion_run_partial(run_uuid, "partial_page_limit",
                                              total_fetched, result["inserted"], result["skipped"],
                                              f"Reached max {MAX_PAGES_PER_DATE} pages")
                return result

            body = dict(base_body)
            if cursor:
                body["cursor"] = cursor

            resp = requests.post(url, json=body, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:
                time.sleep(3)
                continue
            if resp.status_code != 200:
                result["status"] = "failed"
                result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
                _record_ingestion_run_fail(run_uuid, result["error"])
                return result

            data = resp.json()
            orders = data.get("orders", [])
            page_count += 1
            total_fetched += len(orders)

            if orders:
                inserted, skipped = _upsert_orders_batch(orders, park_id, run_uuid)
                result["inserted"] += inserted
                result["skipped"] += skipped

            cursor = data.get("cursor") or data.get("next_cursor")
            if not cursor or len(orders) == 0:
                break

            time.sleep(MIN_INTER_REQUEST)

        if total_fetched == 0:
            result["api_empty"] = True

        _record_ingestion_run_done(run_uuid, total_fetched, result["inserted"], result["skipped"])

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)[:200]
        _record_ingestion_run_fail(run_uuid, str(e)[:200])
        return result

    return result


def _upsert_orders_batch(orders: list, park_id: str, run_uuid: str) -> tuple:
    if not orders:
        return 0, 0
    inserted = 0
    skipped = 0
    try:
        with get_db() as conn:
            cur = conn.cursor()
            now_ts = datetime.now(timezone.utc)
            rows = []
            for o in orders:
                order_id = o.get("order_id") or o.get("id") or ""
                if not order_id:
                    continue
                raw_json = json.dumps(o, default=str)
                payload_hash = hashlib.sha256(raw_json.encode()).hexdigest()
                rows.append((
                    order_id, park_id,
                    o.get("status") or o.get("order_status"),
                    _parse_ts(o.get("created_at") or o.get("order_created_at")),
                    _parse_ts(o.get("booked_at") or o.get("order_booked_at")),
                    _parse_ts(o.get("ended_at") or o.get("order_ended_at")),
                    o.get("driver_profile_id"),
                    o.get("car_id"),
                    o.get("category"),
                    o.get("payment_method"),
                    o.get("provider"),
                    o.get("price"),
                    o.get("mileage"),
                    raw_json, payload_hash,
                    run_uuid, now_ts,
                ))
            if not rows:
                return 0, 0

            execute_values(cur, """
                INSERT INTO raw_yango.orders_raw
                (order_id, park_id, order_status, order_created_at, order_booked_at,
                 order_ended_at, driver_profile_id, car_id, category, payment_method,
                 provider, price, mileage, raw_payload, raw_payload_hash,
                 api_run_id, api_fetched_at, source_endpoint, schema_version)
                VALUES %s
                ON CONFLICT (park_id, order_id, raw_payload_hash) DO NOTHING
            """, rows, template="""
                (%s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s,
                 %s, %s, %s, %s::jsonb, %s,
                 %s, %s, 'orders/list', '1.0')
            """, page_size=len(rows))
            conn.commit()
            inserted = cur.rowcount
            skipped = len(rows) - inserted
    except Exception as e:
        logger.warning("upsert_orders_batch DB error: %s", e)
    return inserted, skipped


def _parse_ts(val):
    if not val:
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None


def _record_ingestion_run_start(run_uuid, park_id, endpoint_group, date_from, date_to):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO raw_yango.api_ingestion_run "
                "(run_id, park_id, endpoint_group, date_from, date_to, status, started_at) "
                "VALUES (%(r)s, %(p)s, %(e)s, %(df)s, %(dt)s, 'running', now())",
                {"r": run_uuid, "p": park_id, "e": endpoint_group,
                 "df": date_from, "dt": date_to}
            )
            conn.commit()
    except Exception:
        pass


def _record_ingestion_run_done(run_uuid, fetched, inserted, skipped):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE raw_yango.api_ingestion_run SET status = 'completed', "
                "records_fetched = %(f)s, records_inserted = %(i)s, record_skips = %(s)s, "
                "finished_at = now() WHERE run_id = %(r)s",
                {"f": fetched, "i": inserted, "s": skipped, "r": run_uuid}
            )
            conn.commit()
    except Exception:
        pass


def _record_ingestion_run_fail(run_uuid, error):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE raw_yango.api_ingestion_run SET status = 'failed', "
                "finished_at = now() WHERE run_id = %(r)s",
                {"r": run_uuid}
            )
            conn.commit()
    except Exception:
        pass


def _record_ingestion_run_partial(run_uuid, status, fetched, inserted, skipped, error):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE raw_yango.api_ingestion_run SET status = %(st)s, "
                "records_fetched = %(f)s, records_inserted = %(i)s, record_skips = %(s)s, "
                "error_message = %(e)s, finished_at = now() WHERE run_id = %(r)s",
                {"st": status, "f": fetched, "i": inserted, "s": skipped,
                 "e": error[:500] if error else None, "r": run_uuid}
            )
            conn.commit()
    except Exception:
        pass
