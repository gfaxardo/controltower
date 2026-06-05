"""
Yango Raw Ingestion Service — safe ingestion from Yango Fleet API into raw_yango.

Orchestrates credential loading, paginated API calls, batch upserts, and audit output.
Always runs dry_run=True by default. Only persistent mode when dry_run=False.
NEVER exposes credentials in logs, errors, or audit output.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.db.connection import get_db
from app.settings import settings
from app.repositories.raw_yango_repository import (
    check_existing_run,
    create_ingestion_run,
    fail_ingestion_run,
    finish_ingestion_run,
    get_credential_for_park,
    insert_ingestion_error,
    upsert_driver_profiles_raw,
    upsert_orders_raw,
    upsert_transactions_raw,
)

logger = logging.getLogger(__name__)

PET = timezone(timedelta(hours=-5))
_MASK_LEN = 8
_MIN_INTER_REQUEST_SEC = 0.5
_BACKOFF_429_SEC = 3.0
_MAX_ORDERS_PER_PAGE = 500
_MAX_TXN_PER_PAGE = 1000
_MAX_PROFILES_PER_PAGE = 1000
_RETRY_MAX = 1

_park_last: Dict[str, float] = {}
_park_locks: Dict[str, asyncio.Lock] = {}


def _mask_id(val: Optional[str]) -> str:
    if not val or not isinstance(val, str):
        return "***"
    return val[:_MASK_LEN] + "***" if len(val) > _MASK_LEN else val


def _mask_payload(obj: Any, depth: int = 0) -> Any:
    if depth > 5:
        return "***"
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return _mask_id(obj) if len(obj) > 20 else obj
    if isinstance(obj, list):
        return [_mask_payload(it, depth + 1) for it in obj[:5]]
    if isinstance(obj, dict):
        r: Dict[str, Any] = {}
        for k, v in obj.items():
            lower = k.lower()
            if lower in (
                "api_key",
                "apikey",
                "x-api-key",
                "x-client-id",
                "token",
                "secret",
                "password",
                "key",
            ):
                r[k] = "***"
            elif lower.endswith("_id") or lower == "id":
                r[k] = _mask_id(str(v)) if isinstance(v, str) else v
            else:
                r[k] = _mask_payload(v, depth + 1)
        return r
    return str(obj)[:100]


def _get_park_lock(park_id: str) -> asyncio.Lock:
    if park_id not in _park_locks:
        _park_locks[park_id] = asyncio.Lock()
    return _park_locks[park_id]


async def _rate_limit(park_id: str) -> None:
    lock = _get_park_lock(park_id)
    async with lock:
        now = time.perf_counter()
        wait = _park_last.get(park_id, 0) + _MIN_INTER_REQUEST_SEC - now
        if wait > 0:
            await asyncio.sleep(wait)
        _park_last[park_id] = time.perf_counter()


def _build_headers(client_id: str, api_key: str) -> Dict[str, str]:
    return {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "Accept-Language": "en",
        "Content-Type": "application/json",
    }


def _fmt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


# ---------------------------------------------------------------------------
# API request body builders
# ---------------------------------------------------------------------------


def _orders_body(
    park_id: str,
    date_from: str,
    date_to: str,
    limit: int,
    cursor: Optional[str] = None,
) -> dict:
    from_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(
        tzinfo=PET, hour=0, minute=0, second=0, microsecond=0
    )
    to_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
        tzinfo=PET, hour=23, minute=59, second=59, microsecond=0
    )
    body: Dict[str, Any] = {
        "limit": limit,
        "query": {
            "park": {
                "id": park_id,
                "order": {
                    "ended_at": {
                        "from": _fmt_iso(from_dt),
                        "to": _fmt_iso(to_dt),
                    },
                    "statuses": ["complete"],
                },
            }
        },
    }
    if cursor:
        body["cursor"] = cursor
    return body


def _transactions_body(
    park_id: str,
    date_from: str,
    date_to: str,
    limit: int,
    cursor: Optional[str] = None,
) -> dict:
    from_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(
        tzinfo=PET, hour=0, minute=0, second=0, microsecond=0
    )
    to_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
        tzinfo=PET, hour=23, minute=59, second=59, microsecond=0
    )
    body: Dict[str, Any] = {
        "limit": limit,
        "query": {
            "park": {
                "id": park_id,
                "transaction": {
                    "event_at": {
                        "from": _fmt_iso(from_dt),
                        "to": _fmt_iso(to_dt),
                    },
                },
            }
        },
    }
    if cursor:
        body["cursor"] = cursor
    return body


def _drivers_body(park_id: str, limit: int, offset: int) -> dict:
    return {
        "query": {
            "park": {
                "id": park_id,
                "driver_profile": {
                    "work_status": ["working", "not_working"],
                },
            },
        },
        "fields": {
            "driver_profile": [
                "id",
                "park_id",
                "created_date",
                "first_name",
                "last_name",
                "work_rule_id",
                "work_status",
                "employment_type",
                "has_contract_issue",
            ],
            "current_status": [
                "status",
                "status_updated_at",
            ],
            "car": [
                "id",
                "status",
                "category",
                "callsign",
                "brand",
                "model",
                "year",
                "number",
            ],
            "account": [
                "id",
                "balance",
                "balance_limit",
                "currency",
                "last_transaction_date",
            ],
            "park": [
                "id",
                "city",
                "name",
            ],
        },
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# API call with retry
# ---------------------------------------------------------------------------


async def _call_api(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    body: Dict[str, Any],
    park_id: str,
) -> Tuple[int, Optional[dict], Optional[str]]:
    last_status = 0
    last_error: Optional[str] = None
    for attempt in range(_RETRY_MAX + 1):
        start = time.perf_counter()
        try:
            resp = await client.post(url, headers=headers, json=body)
            elapsed = round((time.perf_counter() - start) * 1000, 1)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = None
                return 200, data, None

            if resp.status_code == 429:
                last_status = 429
                last_error = "rate_limited"
                logger.warning(
                    "Rate limited (429) park=%s attempt=%s",
                    _mask_id(park_id),
                    attempt + 1,
                )
                await asyncio.sleep(_BACKOFF_429_SEC)
                continue

            try:
                data = resp.json()
            except Exception:
                data = None

            last_status = resp.status_code
            last_error = f"http_{resp.status_code}"
            if resp.status_code >= 500 and attempt < _RETRY_MAX:
                await asyncio.sleep(min(1.0 * (2**attempt), 8.0))
                continue
            return resp.status_code, data, last_error

        except httpx.TimeoutException:
            elapsed = round((time.perf_counter() - start) * 1000, 1)
            last_error = "timeout"
            if attempt < _RETRY_MAX:
                await asyncio.sleep(min(1.0 * (2**attempt), 8.0))
                continue
            return 0, None, last_error

        except httpx.ConnectError:
            last_error = "network_error"
            if attempt < _RETRY_MAX:
                await asyncio.sleep(min(1.0 * (2**attempt), 8.0))
                continue
            return 0, None, last_error

        except Exception as exc:
            last_error = str(exc)[:200]
            if attempt < _RETRY_MAX:
                await asyncio.sleep(min(1.0 * (2**attempt), 8.0))
                continue
            return 0, None, last_error

    return last_status, None, last_error or "max_retries_exceeded"


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------


def _load_credentials(
    park_id: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Load client_id and api_key for a park. Returns (client_id, api_key, error_message)."""
    cred = get_credential_for_park(park_id)
    if not cred:
        return (
            None,
            None,
            f"No active credential found for park_id={_mask_id(park_id)}",
        )

    env_var = cred["env_var_name"]

    client_id = (
        os.environ.get(f"{env_var}_CLIENT_ID", "")
        or getattr(settings, f"{env_var}_CLIENT_ID", "")
        or settings.YANGO_CLIENT_ID
    )
    api_key = (
        os.environ.get(f"{env_var}_API_KEY", "")
        or getattr(settings, f"{env_var}_API_KEY", "")
        or settings.YANGO_API_KEY
    )

    if not client_id or not api_key:
        return (
            None,
            None,
            f"Credential env var {env_var}_CLIENT_ID / {env_var}_API_KEY not available",
        )

    return (client_id or "").strip(), (api_key or "").strip(), None


# ---------------------------------------------------------------------------
# Endpoint configuration
# ---------------------------------------------------------------------------


def _endpoint_config(
    endpoint_group: str, base_url: str, park_id: str, date_from: str, date_to: str
) -> Dict[str, Any]:
    if endpoint_group == "orders":
        return {
            "url": f"{base_url}/v1/parks/orders/list",
            "response_key": "orders",
            "pagination": "cursor",
            "page_size": _MAX_ORDERS_PER_PAGE,
            "body_fn": lambda cursor=None, offset=0: _orders_body(
                park_id, date_from, date_to, _MAX_ORDERS_PER_PAGE, cursor
            ),
        }
    elif endpoint_group == "transactions":
        return {
            "url": f"{base_url}/v2/parks/transactions/list",
            "response_key": "transactions",
            "pagination": "cursor",
            "page_size": _MAX_TXN_PER_PAGE,
            "body_fn": lambda cursor=None, offset=0: _transactions_body(
                park_id, date_from, date_to, _MAX_TXN_PER_PAGE, cursor
            ),
        }
    else:  # driver_profiles
        return {
            "url": f"{base_url}/v1/parks/driver-profiles/list",
            "response_key": "driver_profiles",
            "pagination": "offset",
            "page_size": _MAX_PROFILES_PER_PAGE,
            "body_fn": lambda cursor=None, offset=0: _drivers_body(
                park_id, _MAX_PROFILES_PER_PAGE, offset
            ),
        }


# ---------------------------------------------------------------------------
# Audit output helpers
# ---------------------------------------------------------------------------


def _write_audit_files(
    output_dir: str,
    run_id: str,
    summary: Dict[str, Any],
    errors: List[Dict[str, Any]],
    payload_samples: List[Dict[str, Any]],
    planned_calls: Optional[List[Dict[str, Any]]] = None,
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now(PET).strftime("%Y%m%d_%H%M%S")

    summary_path = os.path.join(output_dir, f"ingestion_summary_{ts}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str, ensure_ascii=False)

    if planned_calls:
        plan_path = os.path.join(output_dir, f"ingestion_planned_{ts}.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(planned_calls, f, indent=2, default=str, ensure_ascii=False)

    if errors:
        errors_csv = os.path.join(output_dir, f"ingestion_errors_{ts}.csv")
        with open(errors_csv, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "page",
                    "status_code",
                    "error_type",
                    "error_message",
                ]
            )
            for e in errors:
                w.writerow(
                    [
                        e.get("page", ""),
                        e.get("status_code", ""),
                        e.get("error_type", ""),
                        e.get("error_message", ""),
                    ]
                )

    if payload_samples:
        samples_path = os.path.join(
            output_dir, f"ingestion_payload_samples_{ts}.json"
        )
        with open(samples_path, "w", encoding="utf-8") as f:
            json.dump(payload_samples, f, indent=2, default=str, ensure_ascii=False)

    return summary_path


# ---------------------------------------------------------------------------
# Main ingestion orchestrator
# ---------------------------------------------------------------------------


async def ingest_endpoint(
    park_id: str,
    endpoint_group: str,
    date_from: str,
    date_to: str,
    max_concurrency: int = 3,
    max_pages: int = 20,
    dry_run: bool = True,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingests data from one Yango API endpoint group into raw_yango tables.

    Returns summary dict with ok, run_id, counters, errors, and audit_path.
    """
    run_id = str(uuid.uuid4())
    start_time = time.perf_counter()
    errors_list: List[Dict[str, Any]] = []
    payload_samples: List[Dict[str, Any]] = []
    total_fetched = 0
    total_inserted = 0
    total_skipped = 0
    pages_fetched = 0

    if endpoint_group not in ("orders", "transactions", "driver_profiles"):
        return {
            "ok": False,
            "run_id": run_id,
            "endpoint_group": endpoint_group,
            "park_id_masked": _mask_id(park_id),
            "date_range": {"from": date_from, "to": date_to},
            "records_fetched": 0,
            "records_inserted": 0,
            "records_skipped": 0,
            "error_count": 1,
            "pages_fetched": 0,
            "dry_run": dry_run,
            "errors": [
                {
                    "error_type": "invalid_endpoint",
                    "error_message": f"Unknown endpoint_group: {endpoint_group}",
                }
            ],
            "audit_path": None,
        }

    if not settings.YANGO_API_ENABLED:
        return {
            "ok": False,
            "run_id": run_id,
            "endpoint_group": endpoint_group,
            "park_id_masked": _mask_id(park_id),
            "date_range": {"from": date_from, "to": date_to},
            "records_fetched": 0,
            "records_inserted": 0,
            "records_skipped": 0,
            "error_count": 1,
            "pages_fetched": 0,
            "dry_run": dry_run,
            "errors": [
                {
                    "error_type": "disabled",
                    "error_message": "YANGO_API_ENABLED is false",
                }
            ],
            "audit_path": None,
        }

    client_id, api_key, cred_error = _load_credentials(park_id)
    if cred_error:
        logger.error("Credential load failed: %s", cred_error)
        return {
            "ok": False,
            "run_id": run_id,
            "endpoint_group": endpoint_group,
            "park_id_masked": _mask_id(park_id),
            "date_range": {"from": date_from, "to": date_to},
            "records_fetched": 0,
            "records_inserted": 0,
            "records_skipped": 0,
            "error_count": 1,
            "pages_fetched": 0,
            "dry_run": dry_run,
            "errors": [
                {
                    "error_type": "missing_credential",
                    "error_message": cred_error,
                }
            ],
            "audit_path": None,
        }

    base_url = (settings.YANGO_API_BASE_URL or "").strip().rstrip("/")
    ep_cfg = _endpoint_config(
        endpoint_group, base_url, park_id, date_from, date_to
    )
    headers = _build_headers(client_id, api_key)  # type: ignore[arg-type]
    sem = asyncio.Semaphore(max(1, min(max_concurrency, 5)))

    # ── Resume check ────────────────────────────────────────────────
    existing = check_existing_run(park_id, endpoint_group, date_from, date_to)
    if existing:
        if existing["status"] == "completed":
            logger.info(
                "Already completed: park=%s endpoint=%s date=%s->%s run=%s",
                _mask_id(park_id),
                endpoint_group,
                date_from,
                date_to,
                _mask_id(existing["run_id"]),
            )
            return {
                "ok": True,
                "run_id": existing["run_id"],
                "endpoint_group": endpoint_group,
                "park_id_masked": _mask_id(park_id),
                "date_range": {"from": date_from, "to": date_to},
                "records_fetched": existing["records_fetched"],
                "records_inserted": existing["records_inserted"],
                "records_skipped": 0,
                "error_count": existing["error_count"],
                "pages_fetched": 0,
                "dry_run": dry_run,
                "errors": [],
                "audit_path": None,
                "resumed_from": existing["run_id"],
            }

    # ── Dry run ─────────────────────────────────────────────────────
    if dry_run:
        run_pk = create_ingestion_run(
            run_id,
            endpoint_group,
            park_id,
            date_from,
            date_to,
            max_concurrency,
            source="yango_fleet_api",
            status="dry_run",
        )
        logger.info(
            "Dry run recorded: id=%s run=%s park=%s endpoint=%s max_pages=%s",
            run_pk,
            _mask_id(run_id),
            _mask_id(park_id),
            endpoint_group,
            max_pages,
        )

        planned_calls = [
            {
                "page": i + 1,
                "url": ep_cfg["url"],
                "method": "POST",
                "body_masked": _mask_payload(
                    ep_cfg["body_fn"](
                        cursor="<cursor>" if ep_cfg["pagination"] == "cursor" else None,
                        offset=i * ep_cfg["page_size"]
                        if ep_cfg["pagination"] == "offset"
                        else 0,
                    )
                ),
            }
            for i in range(max_pages)
        ]

        audit_path = None
        if output_dir:
            audit_path = _write_audit_files(
                output_dir,
                run_id,
                {
                    "ok": True,
                    "run_id": run_id,
                    "park_id_masked": _mask_id(park_id),
                    "endpoint_group": endpoint_group,
                    "date_range": {"from": date_from, "to": date_to},
                    "dry_run": True,
                    "max_pages": max_pages,
                    "max_concurrency": max_concurrency,
                },
                [],
                [],
                planned_calls,
            )

        return {
            "ok": True,
            "run_id": run_id,
            "endpoint_group": endpoint_group,
            "park_id_masked": _mask_id(park_id),
            "date_range": {"from": date_from, "to": date_to},
            "records_fetched": 0,
            "records_inserted": 0,
            "records_skipped": 0,
            "error_count": 0,
            "pages_fetched": 0,
            "dry_run": True,
            "errors": [],
            "audit_path": audit_path,
        }

    # ── Real ingestion ──────────────────────────────────────────────
    run_pk = create_ingestion_run(
        run_id,
        endpoint_group,
        park_id,
        date_from,
        date_to,
        max_concurrency,
        source="yango_fleet_api",
        status="running",
    )
    logger.info(
        "Ingestion started: id=%s run=%s park=%s endpoint=%s date=%s->%s",
        run_pk,
        _mask_id(run_id),
        _mask_id(park_id),
        endpoint_group,
        date_from,
        date_to,
    )

    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)
    cursor: Optional[str] = None
    offset_val = 0
    fatal_error: Optional[str] = None

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            while pages_fetched < max_pages:
                await _rate_limit(park_id)

                body = ep_cfg["body_fn"](
                    cursor=cursor
                    if ep_cfg["pagination"] == "cursor"
                    else None,
                    offset=offset_val,
                )

                async with sem:
                    status_code, data, err = await _call_api(
                        client, ep_cfg["url"], headers, body, park_id
                    )

                if status_code != 200:
                    error_info = {
                        "page": pages_fetched + 1,
                        "status_code": status_code,
                        "error_type": err or f"http_{status_code}",
                        "error_message": (
                            str(data)[:300] if data else (err or "unknown")
                        ),
                    }
                    errors_list.append(error_info)

                    insert_ingestion_error(
                        run_id=run_id,
                        park_id=park_id,
                        endpoint_group=endpoint_group,
                        endpoint_url=ep_cfg["url"],
                        request_params=json.dumps(body, default=str)[:2000],
                        status_code=status_code,
                        error_type=err or f"http_{status_code}",
                        error_message=str(data)[:1000] if data else (err or ""),
                        retry_count=0,
                    )

                    if status_code == 429:
                        pages_fetched += 1
                        continue

                    fatal_error = err or f"http_{status_code}"
                    break

                if not data or not isinstance(data, dict):
                    fatal_error = "empty_or_invalid_response"
                    break

                items = data.get(ep_cfg["response_key"], [])
                if not isinstance(items, list):
                    items = []
                fetched_count = len(items)
                total_fetched += fetched_count
                pages_fetched += 1

                if fetched_count > 0:
                    if len(payload_samples) < 5:
                        payload_samples.append(
                            {
                                "page": pages_fetched,
                                "endpoint": endpoint_group,
                                "masked_sample": _mask_payload(items[0]),
                            }
                        )

                    api_fetched_at = datetime.now(PET).isoformat()
                    with get_db() as conn:
                        if endpoint_group == "orders":
                            result = upsert_orders_raw(
                                conn, items, park_id, run_id, api_fetched_at
                            )
                        elif endpoint_group == "transactions":
                            result = upsert_transactions_raw(
                                conn, items, park_id, run_id, api_fetched_at
                            )
                        else:
                            result = upsert_driver_profiles_raw(
                                conn, items, park_id, run_id, api_fetched_at
                            )
                        total_inserted += result["inserted"]
                        total_skipped += result["skipped"]

                if ep_cfg["pagination"] == "offset":
                    offset_val += fetched_count
                    if fetched_count < ep_cfg["page_size"]:
                        break
                else:
                    next_cursor = data.get("cursor") or data.get("next_cursor")
                    if not next_cursor or fetched_count == 0:
                        break
                    cursor = next_cursor

        if fatal_error:
            fail_ingestion_run(
                run_id,
                fatal_error,
                total_fetched,
                total_inserted,
                len(errors_list),
            )
        else:
            finish_ingestion_run(
                run_id,
                total_fetched,
                total_inserted,
                0,
                total_skipped,
                error_count=len(errors_list),
            )

    except Exception as exc:
        fatal_error = str(exc)[:500]
        logger.exception("Ingestion fatal error: run=%s", _mask_id(run_id))
        try:
            fail_ingestion_run(
                run_id,
                fatal_error,
                total_fetched,
                total_inserted,
                len(errors_list) + 1,
            )
        except Exception:
            logger.exception("Failed to mark run as failed")

    # ── Audit output ────────────────────────────────────────────────
    audit_path = None
    if output_dir:
        try:
            audit_path = _write_audit_files(
                output_dir,
                run_id,
                {
                    "ok": fatal_error is None,
                    "run_id": run_id,
                    "park_id_masked": _mask_id(park_id),
                    "endpoint_group": endpoint_group,
                    "date_range": {"from": date_from, "to": date_to},
                    "records_fetched": total_fetched,
                    "records_inserted": total_inserted,
                    "records_skipped": total_skipped,
                    "error_count": len(errors_list),
                    "pages_fetched": pages_fetched,
                    "dry_run": False,
                    "elapsed_seconds": round(
                        time.perf_counter() - start_time, 1
                    ),
                },
                errors_list,
                payload_samples,
            )
        except Exception:
            logger.exception("Failed to write audit files")

    elapsed = round(time.perf_counter() - start_time, 1)
    logger.info(
        "Ingestion complete: run=%s endpoint=%s park=%s pages=%s "
        "fetched=%s inserted=%s skipped=%s errors=%s elapsed=%ss",
        _mask_id(run_id),
        endpoint_group,
        _mask_id(park_id),
        pages_fetched,
        total_fetched,
        total_inserted,
        total_skipped,
        len(errors_list),
        elapsed,
    )

    return {
        "ok": fatal_error is None,
        "run_id": run_id,
        "endpoint_group": endpoint_group,
        "park_id_masked": _mask_id(park_id),
        "date_range": {"from": date_from, "to": date_to},
        "records_fetched": total_fetched,
        "records_inserted": total_inserted,
        "records_skipped": total_skipped,
        "error_count": len(errors_list),
        "pages_fetched": pages_fetched,
        "dry_run": False,
        "errors": errors_list[:20],
        "audit_path": audit_path,
    }
