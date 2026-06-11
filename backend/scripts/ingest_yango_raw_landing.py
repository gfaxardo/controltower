#!/usr/bin/env python3
"""
Yango Raw Landing — Safe ingestion script.
Read-only by default (dry_run=True). Requires --confirm-live for real ingestion.

Usage:
  cd backend
  python -m scripts.ingest_yango_raw_landing --endpoint-group transactions --date-from 2026-06-01 --date-to 2026-06-03
  python -m scripts.ingest_yango_raw_landing --endpoint-group all --confirm-live --max-pages 5
  python -m scripts.ingest_yango_raw_landing --dry-run --output-audit-dir exports/audits/yango_raw_landing/
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.settings import settings
from app.db.connection import get_db
from app.repositories.raw_yango_repository import (
    create_ingestion_run,
    finish_ingestion_run,
    fail_ingestion_run,
    update_ingestion_heartbeat,
    update_ingestion_counters,
    set_ingestion_expected_pages,
    set_ingestion_status,
    init_page_checkpoints,
    record_page_completed,
    record_page_failed,
    get_missing_pages,
)
import httpx

PET = timezone(timedelta(hours=-5))
MASK_SUFFIX = "***"
MIN_INTER_REQUEST_SEC = 0.5
BACKOFF_429_SEC = 3.0
CHECKPOINT_FILE = "ingest_checkpoint.json"
SCHEMA_VERSION = "2026-06-05"

ENDPOINT_GROUP_MAP = {
    "orders": {
        "endpoints": ["orders"],
        "url_path": "/v1/parks/orders/list",
        "pagination": "cursor",
        "response_key": "orders",
        "table": "raw_yango.orders_raw",
        "page_size": 500,
    },
    "transactions": {
        "endpoints": ["transactions"],
        "url_path": "/v2/parks/transactions/list",
        "pagination": "cursor",
        "response_key": "transactions",
        "response_keys_alt": ["items"],
        "table": "raw_yango.transactions_raw",
        "page_size": 1000,
    },
    "driver_profiles": {
        "endpoints": ["driver_profiles"],
        "url_path": "/v1/parks/driver-profiles/list",
        "pagination": "offset",
        "response_key": "driver_profiles",
        "table": "raw_yango.driver_profiles_raw",
        "page_size": 1000,
    },
    "all": {
        "endpoints": ["orders", "transactions", "driver_profiles"],
    },
}


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mask(val: Optional[str], keep: int = 8) -> str:
    if not val or not isinstance(val, str):
        return MASK_SUFFIX
    return (val[:keep] + MASK_SUFFIX) if len(val) > keep else val[:2] + MASK_SUFFIX


def _build_headers(client_id: str, api_key: str) -> Dict[str, str]:
    return {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "Accept-Language": "en",
        "Content-Type": "application/json",
    }


def _fmt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def _dt_tuple(day_str: str):
    t = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=PET)
    return t, t.replace(hour=23, minute=59, second=59)


def _load_checkpoint(d: str) -> dict:
    p = os.path.join(d, CHECKPOINT_FILE)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_checkpoint(d: str, data: dict):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, CHECKPOINT_FILE), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)


def _orders_body(park_id: str, day: str, cursor: Optional[str] = None) -> dict:
    f, t = _dt_tuple(day)
    b = {
        "limit": 500,
        "query": {
            "park": {
                "id": park_id,
                "order": {
                    "ended_at": {"from": _fmt_iso(f), "to": _fmt_iso(t)},
                    "statuses": ["complete"],
                },
            }
        },
    }
    if cursor:
        b["cursor"] = cursor
    return b


def _transactions_body(park_id: str, day: str, cursor: Optional[str] = None) -> dict:
    f, t = _dt_tuple(day)
    b = {
        "limit": 100,
        "query": {
            "park": {
                "id": park_id,
                "transaction": {
                    "event_at": {"from": _fmt_iso(f), "to": _fmt_iso(t)}
                },
            }
        },
    }
    if cursor:
        b["cursor"] = cursor
    return b


def _transactions_body_hour(park_id: str, day: str, hour_from: int, hour_to: int, cursor: Optional[str] = None) -> dict:
    """Transaction body for an hour-window partition."""
    base = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=PET)
    f = base.replace(hour=hour_from, minute=0, second=0, microsecond=0)
    t = base.replace(hour=hour_to - 1, minute=59, second=59, microsecond=0) if hour_to > hour_from else base.replace(hour=23, minute=59, second=59)
    b = {
        "limit": 100,
        "query": {
            "park": {
                "id": park_id,
                "transaction": {
                    "event_at": {"from": _fmt_iso(f), "to": _fmt_iso(t)}
                },
            }
        },
    }
    if cursor:
        b["cursor"] = cursor
    return b


def _orders_body_hour(park_id: str, day: str, hour_from: int, hour_to: int, cursor: Optional[str] = None) -> dict:
    """Order body for an hour-window partition."""
    base = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=PET)
    f = base.replace(hour=hour_from, minute=0, second=0, microsecond=0)
    t = base.replace(hour=hour_to - 1, minute=59, second=59, microsecond=0) if hour_to > hour_from else base.replace(hour=23, minute=59, second=59)
    b = {
        "limit": 500,
        "query": {
            "park": {
                "id": park_id,
                "order": {
                    "ended_at": {"from": _fmt_iso(f), "to": _fmt_iso(t)},
                    "statuses": ["complete"],
                },
            }
        },
    }
    if cursor:
        b["cursor"] = cursor
    return b


def _build_hour_partitions(date_from: str, date_to: str, hour_window: int) -> List[Tuple[str, int, int]]:
    """Generate (day, hour_from, hour_to) partitions for a date range."""
    fd = datetime.strptime(date_from, "%Y-%m-%d").date()
    td = datetime.strptime(date_to, "%Y-%m-%d").date()
    parts = []
    current = fd
    while current <= td:
        day_str = current.strftime("%Y-%m-%d")
        for h in range(0, 24, hour_window):
            parts.append((day_str, h, min(h + hour_window, 24)))
        current += timedelta(days=1)
    return parts


def _load_partitioned_checkpoint(output_dir: str) -> dict:
    p = os.path.join(output_dir, "partitioned_checkpoint.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_partitioned_checkpoint(output_dir: str, data: dict):
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, "partitioned_checkpoint.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)


def _drivers_body(park_id: str, limit: int, offset: int) -> dict:
    return {
        "query": {
            "park": {
                "id": park_id,
                "driver_profile": {
                    "work_status": ["working", "not_working"]
                },
            }
        },
        "fields": {
            "driver_profile": [
                "id", "park_id", "created_date", "first_name",
                "last_name", "work_rule_id", "work_status", "employment_type",
                "has_contract_issue",
            ],
            "current_status": ["status", "status_updated_at"],
            "car": ["id", "status", "category", "callsign", "brand", "model", "year", "number"],
            "account": ["id", "balance", "balance_limit", "currency", "last_transaction_date"],
            "park": ["id", "city", "name"],
        },
        "limit": limit,
        "offset": offset,
    }


_park_last: Dict[str, float] = {}


async def _rate_limit(park_id: str, lock: asyncio.Lock):
    async with lock:
        now = time.perf_counter()
        wait = _park_last.get(park_id, 0) + MIN_INTER_REQUEST_SEC - now
        if wait > 0:
            await asyncio.sleep(wait)
        _park_last[park_id] = time.perf_counter()


async def _backoff(attempt: int):
    await asyncio.sleep(min(1.0 * (2 ** attempt), 16.0))


async def _retry_fetch(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    body: dict,
    sem: asyncio.Semaphore,
    park_id: str,
    park_lock: asyncio.Lock,
    max_retries: int,
) -> Tuple[Optional[dict], float, Optional[int], Optional[str]]:
    last_elapsed, last_status, last_err = 0.0, None, None
    for attempt in range(max_retries + 1):
        await _rate_limit(park_id, park_lock)
        async with sem:
            start = time.perf_counter()
            try:
                resp = await client.post(url, headers=headers, json=body)
            except httpx.TimeoutException:
                last_elapsed = round((time.perf_counter() - start) * 1000, 1)
                if attempt < max_retries:
                    await _backoff(attempt)
                    continue
                return None, last_elapsed, 0, "timeout"
            except Exception as exc:
                last_elapsed = round((time.perf_counter() - start) * 1000, 1)
                if attempt < max_retries:
                    await _backoff(attempt)
                    continue
                msg = str(exc)[:200]
                for s in (
                    (settings.YANGO_API_KEY or "").strip(),
                    (settings.YANGO_CLIENT_ID or "").strip(),
                ):
                    if s and len(s) > 4:
                        msg = msg.replace(s, MASK_SUFFIX)
                return None, last_elapsed, 0, msg

        elapsed = round((time.perf_counter() - start) * 1000, 1)
        if resp.status_code == 429:
            last_elapsed, last_status, last_err = elapsed, 429, "rate_limited"
            if attempt < max_retries:
                await asyncio.sleep(BACKOFF_429_SEC)
                continue
            try:
                return resp.json(), elapsed, 429, "rate_limited"
            except Exception:
                return None, elapsed, 429, "rate_limited"
        if resp.status_code == 200:
            try:
                return resp.json(), elapsed, 200, None
            except Exception:
                return None, elapsed, 200, "json_parse_error"
        last_elapsed, last_status = elapsed, resp.status_code
        last_err = f"http_{resp.status_code}"
        if attempt < max_retries and resp.status_code >= 500:
            await _backoff(attempt)
            continue
        try:
            return resp.json(), elapsed, resp.status_code, last_err
        except Exception:
            return None, elapsed, resp.status_code, last_err
    return None, last_elapsed, last_status or 0, last_err or "max_retries_exceeded"


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _insert_orders(rows: List[Dict], park_id: str, run_id: str) -> int:
    if not rows:
        return 0
    try:
        with get_db() as conn:
            cur = conn.cursor()
            inserted = 0
            for row in rows:
                rd = row if isinstance(row, dict) else {}
                payload_hash = _hash_payload(rd)
                try:
                    cur.execute(
                        """
                        INSERT INTO raw_yango.orders_raw (
                            order_id, park_id, order_status,
                            price, payment_method, category,
                            driver_profile_id, car_id,
                            order_booked_at, order_ended_at, order_created_at,
                            mileage, provider,
                            raw_payload_hash, raw_payload,
                            api_fetched_at, operational_date,
                            source_endpoint, schema_version, api_run_id
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s, %s
                        ) ON CONFLICT (park_id, order_id, raw_payload_hash) DO NOTHING
                        """,
                        (
                            str(rd.get("id") or ""),
                            park_id,
                            str(rd.get("status") or ""),
                            float(rd["price"]) if rd.get("price") else None,
                            str(rd.get("payment_method") or ""),
                            str(rd.get("category") or ""),
                            str((rd.get("driver_profile") or {}).get("id") or ""),
                            str((rd.get("car") or {}).get("id") or ""),
                            rd.get("booked_at"),
                            rd.get("ended_at"),
                            rd.get("created_at"),
                            float(rd["mileage"]) if rd.get("mileage") else None,
                            str(rd.get("provider") or ""),
                            payload_hash,
                            json.dumps(rd, default=str, ensure_ascii=False),
                            datetime.now(PET),
                            (rd.get("ended_at") or rd.get("created_at")),
                            "/v1/parks/orders/list",
                            SCHEMA_VERSION,
                            run_id,
                        ),
                    )
                    inserted += cur.rowcount
                except Exception:
                    conn.rollback()
            conn.commit()
            cur.close()
            return inserted
    except Exception:
        return 0


def _insert_transactions(rows: List[Dict], park_id: str, run_id: str) -> int:
    if not rows:
        return 0
    try:
        with get_db() as conn:
            cur = conn.cursor()
            inserted = 0
            for row in rows:
                rd = row if isinstance(row, dict) else {}
                payload_hash = _hash_payload(rd)
                try:
                    cur.execute(
                        """
                        INSERT INTO raw_yango.transactions_raw (
                            transaction_id, park_id,
                            category_id, category_name, group_id,
                            amount, currency_code, description,
                            driver_profile_id, order_id,
                            event_at, created_by_identity,
                            raw_payload_hash, raw_payload,
                            api_fetched_at, operational_date,
                            source_endpoint, schema_version, api_run_id
                        ) VALUES (
                            %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s, %s
                        ) ON CONFLICT (park_id, transaction_id, raw_payload_hash) DO NOTHING
                        """,
                        (
                            str(rd.get("id") or ""),
                            park_id,
                            str(rd.get("category_id") or ""),
                            str(rd.get("category_name") or ""),
                            str(rd.get("category_group_id") or ""),
                            float(rd["amount"]) if rd.get("amount") else None,
                            str(rd.get("currency_code") or ""),
                            str(rd.get("description") or ""),
                            str(rd.get("driver_profile_id") or ""),
                            str(rd.get("order_id") or ""),
                            rd.get("event_at"),
                            str((rd.get("created_by") or {}).get("identity") or ""),
                            payload_hash,
                            json.dumps(rd, default=str, ensure_ascii=False),
                            datetime.now(PET),
                            rd.get("event_at"),
                            "/v2/parks/transactions/list",
                            SCHEMA_VERSION,
                            run_id,
                        ),
                    )
                    inserted += cur.rowcount
                except Exception:
                    conn.rollback()
            conn.commit()
            cur.close()
            return inserted
    except Exception:
        return 0


def _insert_driver_profiles(rows: List[Dict], park_id: str, run_id: str) -> int:
    if not rows:
        return 0
    try:
        with get_db() as conn:
            cur = conn.cursor()
            inserted = 0
            for row in rows:
                rd = row if isinstance(row, dict) else {}
                dp = rd.get("driver_profile") or {}
                car_info = (rd.get("car") or [{}, {}])
                if isinstance(car_info, list):
                    car_info = car_info[0] if car_info else {}
                payload_hash = _hash_payload(rd)
                try:
                    cur.execute(
                        """
                        INSERT INTO raw_yango.driver_profiles_raw (
                            driver_profile_id, park_id,
                            work_status, car_id, car_category,
                            has_contract_issue,
                            raw_payload_hash, raw_payload,
                            api_fetched_at, operational_date,
                            source_endpoint, schema_version, api_run_id
                        ) VALUES (
                            %s, %s,
                            %s, %s, %s,
                            %s,
                            %s, %s,
                            %s, %s,
                            %s, %s, %s
                        ) ON CONFLICT (park_id, driver_profile_id, raw_payload_hash) DO NOTHING
                        """,
                        (
                            str(dp.get("id") or ""),
                            park_id,
                            str(dp.get("work_status") or ""),
                            str(car_info.get("id") or ""),
                            str(car_info.get("category") or ""),
                            bool(dp.get("has_contract_issue")),
                            payload_hash,
                            json.dumps(rd, default=str, ensure_ascii=False),
                            datetime.now(PET),
                            datetime.now(PET).date(),
                            "/v1/parks/driver-profiles/list",
                            SCHEMA_VERSION,
                            run_id,
                        ),
                    )
                    inserted += cur.rowcount
                except Exception:
                    conn.rollback()
            conn.commit()
            cur.close()
            return inserted
    except Exception:
        return 0


async def _ingest_endpoint(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    body_fn,
    pagination: str,
    response_key: str,
    response_keys_alt: List[str],
    park_id: str,
    days: List[str],
    sem: asyncio.Semaphore,
    park_lock: asyncio.Lock,
    max_pages: int,
    max_retries: int,
    page_size: int,
    metrics: list,
    errors: list,
    checkpoint: dict,
    output_dir: str,
    dry_run: bool,
    name: str,
    run_id: str,
    insert_fn,
) -> dict:
    total_records, pages_fetched = 0, 0
    if dry_run:
        return {
            "endpoint": name,
            "dry_run": True,
            "days": len(days),
            "estimated_calls": len(days) * max_pages,
        }

    if pagination == "offset":
        days_iter = ["N/A"]
    else:
        days_iter = days

    offset = 0
    for day_str in days_iter:
        cursor = None
        day_pages = 0
        while day_pages < max_pages:
            ck = (
                f"{name}_{day_str}_{day_pages}"
                if pagination == "cursor"
                else f"{name}_{pages_fetched}"
            )
            if checkpoint.get("completed_pages", {}).get(ck):
                day_pages += 1
                if pagination == "offset":
                    pages_fetched += 1
                    offset += page_size
                continue

            if pagination == "offset":
                body = body_fn(park_id, page_size, offset)
            else:
                body = body_fn(park_id, day_str, cursor)

            data, elapsed, status, err = await _retry_fetch(
                client, url, headers, body, sem, park_id, park_lock, max_retries
            )
            metrics.append(
                {
                    "endpoint": name,
                    "day": day_str,
                    "page": day_pages + 1,
                    "elapsed_ms": elapsed,
                    "status_code": status,
                    "error": err,
                }
            )
            if err or status != 200:
                errors.append(
                    {
                        "endpoint": name,
                        "day": day_str,
                        "page": day_pages + 1,
                        "status_code": status,
                        "error": err,
                        "elapsed_ms": elapsed,
                    }
                )
                if status == 429:
                    continue
                break

            items = None
            if data and isinstance(data, dict):
                for k in [response_key] + response_keys_alt:
                    items = data.get(k)
                    if items is not None:
                        break
            items = items or []

            if items:
                inserted = insert_fn(items, park_id, run_id)
                total_records += inserted

                # ── Heartbeat + counters (OV2-B.6B) ──────────────────
                try:
                    update_ingestion_counters(
                        run_id,
                        fetched=len(items),
                        inserted=inserted,
                        pages_completed=1,
                    )
                    update_ingestion_heartbeat(
                        run_id, current_page=pages_fetched + 1, next_cursor=next_cursor
                    )
                    try:
                        record_page_completed(run_id, pages_fetched + 1, len(items), inserted, next_cursor)
                    except Exception:
                        pass
                except Exception:
                    pass

            next_cursor = data.get("cursor") or data.get("next_cursor") if data and isinstance(data, dict) else None
            cursor = next_cursor if (next_cursor and items) else None
            pages_fetched += 1
            day_pages += 1
            if pagination == "offset":
                offset += page_size
            checkpoint.setdefault("completed_pages", {})[ck] = True
            _save_checkpoint(output_dir, checkpoint)
            if not cursor and pagination == "cursor":
                break
    return {"endpoint": name, "total_records": total_records, "pages_fetched": pages_fetched}


def _build_summary_md(
    config: dict,
    results: dict,
    metrics: list,
    errors: list,
    start_time: float,
    output_dir: str,
) -> str:
    elapsed = time.perf_counter() - start_time
    ok = [m for m in metrics if m.get("status_code") == 200 and m.get("error") is None]
    err_n = len(errors)
    r429 = len([e for e in errors if e.get("status_code") == 429])
    pages = sum(r.get("pages_fetched", 0) for r in results.values())
    recs = sum(r.get("total_records", 0) for r in results.values())
    h, m = int(elapsed // 3600), int((elapsed % 3600) // 60)

    lines = [
        "# Yango Raw Landing — Ingestion Summary",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Range:** {config.get('date_from')} -> {config.get('date_to')} ({config.get('days_count')}d)",
        f"**Park:** {config.get('park_id_masked')}",
        f"**Endpoint Group:** {config.get('endpoint_group')}",
        f"**Dry Run:** {config.get('dry_run')}",
        f"**Run ID:** {config.get('run_id')}",
        f"**Output Dir:** {output_dir}",
        "",
        "## Results",
        f"- Requests: {len(metrics)} | Success: {len(ok)} | Errors: {err_n} | 429s: {r429}",
        f"- Pages: {pages} | Records Inserted: {recs}",
        f"- Elapsed: {h}h {m}m {elapsed%60:.1f}s",
        "",
        "## Per-Endpoint",
    ]
    for ep_name in ["orders", "transactions", "driver_profiles"]:
        r = results.get(ep_name, {})
        lines.append(
            f"- **{ep_name}**: pages={r.get('pages_fetched', 0)} records={r.get('total_records', 0)}"
        )
    lines.append("")
    if errors:
        lines.append("## Errors")
        cnt: Dict[str, int] = {}
        for e in errors:
            k = f"{e.get('endpoint')} {e.get('status_code')} {e.get('error')}"
            cnt[k] = cnt.get(k, 0) + 1
        for k, v in sorted(cnt.items()):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("## Errors")
        lines.append("- None")
    return "\n".join(lines)


def _build_metrics_json(
    config: dict, results: dict, metrics: list, errors: list, start_time: float
) -> dict:
    elapsed = time.perf_counter() - start_time
    return {
        "run_id": config.get("run_id"),
        "generated_at": datetime.now(PET).isoformat(),
        "config": config,
        "counts": {
            "requests": len(metrics),
            "success": len([m for m in metrics if m.get("status_code") == 200 and m.get("error") is None]),
            "errors": len(errors),
            "rate_limits_429": len([e for e in errors if e.get("status_code") == 429]),
            "total_pages": sum(r.get("pages_fetched", 0) for r in results.values()),
            "total_records": sum(r.get("total_records", 0) for r in results.values()),
        },
        "elapsed_total_seconds": round(elapsed, 1),
    }


def _write_csv(
    output_dir: str, filename: str, headers_row: list, rows: list
) -> str:
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers_row)
        for row in rows:
            w.writerow(row)
    return path


def _write_dry_run_plan(
    output_dir: str,
    config: dict,
    endpoint_groups: list,
    days: list,
    max_pages: int,
) -> str:
    path = os.path.join(output_dir, "dry_run_plan.json")
    plan = {
        "run_id": config["run_id"],
        "dry_run": True,
        "endpoint_groups": endpoint_groups,
        "days": days,
        "max_pages_per_endpoint": max_pages,
        "estimated_api_calls": len(days) * max_pages * len(endpoint_groups),
        "park_id_masked": config["park_id_masked"],
        "date_from": config["date_from"],
        "date_to": config["date_to"],
        "generated_at": datetime.now(PET).isoformat(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, default=str, ensure_ascii=False)
    return path


async def run_ingestion(
    park_id: str,
    date_from: str,
    date_to: str,
    endpoint_groups: List[str],
    max_concurrency: int,
    max_pages: int,
    dry_run: bool,
    output_dir: str,
    resume: bool,
    partition_mode: str = "none",
    hour_window_size: int = 2,
    max_partitions_parallel: int = 2,
    max_pages_per_partition: int = 50,
    resume_run_id: Optional[str] = None,
    expected_total: Optional[int] = None,
    fail_on_coverage_below: Optional[float] = None,
    mark_stalled_after_minutes: int = 30,
) -> int:
    base_url = (settings.YANGO_API_BASE_URL or "").strip()
    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()

    if not dry_run and not settings.YANGO_API_ENABLED:
        print("ERROR: YANGO_API_ENABLED=false.", file=sys.stderr)
        return 1
    if not client_id or not api_key or not park_id:
        print("ERROR: missing credentials/park_id.", file=sys.stderr)
        return 1

    from_dt = datetime.strptime(date_from, "%Y-%m-%d")
    to_dt = datetime.strptime(date_to, "%Y-%m-%d")
    days = [
        (from_dt + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range((to_dt - from_dt).days + 1)
    ]

    run_id = f"ingest_{datetime.now(PET).strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(output_dir, exist_ok=True)

    config = {
        "run_id": run_id,
        "park_id_masked": _mask(park_id),
        "date_from": date_from,
        "date_to": date_to,
        "days_count": len(days),
        "endpoint_group": endpoint_groups,
        "dry_run": dry_run,
        "max_pages": max_pages,
        "max_concurrency": max_concurrency,
    }

    if dry_run:
        if partition_mode == "hour" and any(ep in endpoint_groups for ep in ("transactions", "orders")):
            partitions = _build_hour_partitions(date_from, date_to, hour_window_size)
            est_calls = len(partitions) * max_pages_per_partition
            print(f"\n[ingest] DRY RUN (partitioned) — no API calls, no DB writes.")
            print(f"  Mode: {partition_mode} | Window: {hour_window_size}h | Parallel: {max_partitions_parallel}")
            print(f"  Partitions: {len(partitions)} | Max pages/partition: {max_pages_per_partition}")
            print(f"  Estimated API calls: {est_calls}")
        else:
            plan_path = _write_dry_run_plan(output_dir, config, endpoint_groups, days, max_pages)
            print(f"\n[ingest] DRY RUN — no API calls, no DB writes.")
            print(f"  Plan saved to: {plan_path}")
            print(f"  Endpoint groups: {endpoint_groups}")
            print(f"  Days: {len(days)} ({date_from} -> {date_to})")
            print(f"  Estimated API calls: {len(days) * max_pages * len(endpoint_groups)}")
        return 0

    # ── Create ingestion run tracking ────────────────────────────
    for ep in endpoint_groups:
        try:
            create_ingestion_run(
                run_id=f"{run_id}_{ep}",
                endpoint_group=ep,
                park_id=park_id,
                date_from=date_from,
                date_to=date_to,
                max_concurrency=max_concurrency,
                script_version=SCHEMA_VERSION,
                source="yango_fleet_api",
                status="started",
            )
        except Exception:
            pass  # tracking is best-effort, don't block ingestion

    headers = _build_headers(client_id, api_key)
    sem = asyncio.Semaphore(max(1, max_concurrency))
    park_lock = asyncio.Lock()
    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)
    max_retries = settings.YANGO_API_MAX_RETRIES

    checkpoint = _load_checkpoint(output_dir) if resume else {}
    checkpoint["config"] = config
    _save_checkpoint(output_dir, checkpoint)

    metrics, errors = [], []
    results = {}
    t0 = time.perf_counter()

    insert_map = {
        "orders": _insert_orders,
        "transactions": _insert_transactions,
        "driver_profiles": _insert_driver_profiles,
    }

    body_map = {
        "orders": _orders_body,
        "transactions": _transactions_body,
        "driver_profiles": _drivers_body,
    }

    url_map = {
        "orders": f"{base_url.rstrip('/')}/v1/parks/orders/list",
        "transactions": f"{base_url.rstrip('/')}/v2/parks/transactions/list",
        "driver_profiles": f"{base_url.rstrip('/')}/v1/parks/driver-profiles/list",
    }

    pagination_map = {
        "orders": "cursor",
        "transactions": "cursor",
        "driver_profiles": "offset",
    }

    response_key_map = {
        "orders": "orders",
        "transactions": "transactions",
        "driver_profiles": "driver_profiles",
    }

    alt_keys_map = {
        "orders": [],
        "transactions": ["items"],
        "driver_profiles": [],
    }

    for ep in endpoint_groups:
        # ── Partitioned mode (hour windows) ──────────────────
        if partition_mode == "hour" and ep in ("transactions", "orders"):
            partitions = _build_hour_partitions(date_from, date_to, hour_window_size)
            part_checkpoint = _load_partitioned_checkpoint(output_dir) if resume else {}
            part_sem = asyncio.Semaphore(max(1, int(max_partitions_parallel)))

            part_body_hour = _transactions_body_hour if ep == "transactions" else _orders_body_hour
            part_page_size = 100 if ep == "transactions" else 500

            print(f"[ingest] {ep} — {len(partitions)} hour partitions "
                  f"(window={hour_window_size}h, parallel={max_partitions_parallel}, "
                  f"pages_per={max_pages_per_partition}, page_size={part_page_size})")

            async def _run_partition(day_str: str, h_from: int, h_to: int) -> dict:
                part_key = f"{park_id}_{ep}_{day_str}_{h_from:02d}_{h_to:02d}"
                async with part_sem:
                    if part_checkpoint.get(part_key):
                        return {"partition": part_key, "records": 0, "pages": 0, "status": "skipped"}
                    part_checkpoint[part_key] = "running"
                    _save_partitioned_checkpoint(output_dir, part_checkpoint)
                    part_body_fn = lambda pid, d, cur=None: part_body_hour(
                        pid, day_str, h_from, h_to, cur
                    )
                    r = await _ingest_endpoint(
                        client=httpx.AsyncClient(timeout=timeout),
                        url=url_map[ep],
                        headers=headers,
                        body_fn=part_body_fn,
                        pagination="cursor",
                        response_key=response_key_map[ep],
                        response_keys_alt=alt_keys_map[ep],
                        park_id=park_id,
                        days=["N/A"],
                        sem=asyncio.Semaphore(1),
                        park_lock=asyncio.Lock(),
                        max_pages=int(max_pages_per_partition),
                        max_retries=max_retries,
                        page_size=part_page_size,
                        metrics=metrics,
                        errors=errors,
                        checkpoint={},
                        output_dir=output_dir,
                        dry_run=False,
                        name=f"{ep}_{part_key}",
                    run_id=f"{run_id}_{ep}",
                    insert_fn=insert_map[ep],
                )
                total = r.get("total_records", 0)
                pages = r.get("pages_fetched", 0)
                part_checkpoint[part_key] = "done" if total == 0 else f"done:{total}"
                _save_partitioned_checkpoint(output_dir, part_checkpoint)
                return {"partition": part_key, "records": total, "pages": pages, "status": "ok"}

            tasks = [_run_partition(d, hf, ht) for d, hf, ht in partitions]
            part_results = await asyncio.gather(*tasks)
            part_records = sum(r.get("records", 0) for r in part_results)
            part_pages = sum(r.get("pages", 0) for r in part_results)
            results[ep] = {"endpoint": ep, "total_records": part_records, "pages_fetched": part_pages}
        else:
            # ── Sequential mode (original) ────────────────────
            print(f"[ingest] {ep} — {len(days) if pagination_map[ep] == 'cursor' else 'probing'} ...")
            results[ep] = await _ingest_endpoint(
                client=httpx.AsyncClient(timeout=timeout),
                url=url_map[ep],
                headers=headers,
                body_fn=body_map[ep],
                pagination=pagination_map[ep],
                response_key=response_key_map[ep],
                response_keys_alt=alt_keys_map[ep],
                park_id=park_id,
                days=days,
                sem=sem,
                park_lock=park_lock,
                max_pages=max_pages,
                max_retries=max_retries,
                page_size=(
                    500 if ep == "orders" else 100
                ),
                metrics=metrics,
                errors=errors,
                checkpoint=checkpoint,
                output_dir=output_dir,
                dry_run=False,
                name=ep,
                run_id=f"{run_id}_{ep}",
                insert_fn=insert_map[ep],
            )

    # ── Finalize ingestion run tracking ─────────────────────────
    has_errors = len(errors) > 0
    total_recs = sum(r.get("total_records", 0) for r in results.values())
    total_pages = sum(r.get("pages_fetched", 0) for r in results.values())

    for ep in endpoint_groups:
        ep_run_id = f"{run_id}_{ep}"
        ep_res = results.get(ep, {})
        ep_recs = ep_res.get("total_records", 0)
        ep_pages = ep_res.get("pages_fetched", 0)

        # ── Completion guard (OV2-B.6B) ─────────────────────────
        coverage_ok = True
        if expected_total and expected_total > 0:
            coverage = ep_recs / expected_total
            if coverage < (fail_on_coverage_below or 0.95):
                print(
                    f"\n[ingest] COVERAGE FAIL: {ep} ingested {ep_recs} / {expected_total} "
                    f"= {coverage*100:.1f}% < {fail_on_coverage_below*100:.0f}% threshold"
                )
                coverage_ok = False
            else:
                print(f"\n[ingest] COVERAGE OK: {ep} = {coverage*100:.1f}%")

        try:
            if ep_recs == 0 and not ep_res.get("dry_run", False):
                fail_ingestion_run(ep_run_id, "no_records" if not has_errors else "partial_or_no_records",
                                   ep_recs, ep_recs, 0)
            elif not coverage_ok:
                set_ingestion_status(ep_run_id, "failed")
                ep_run_id_fail = ep_run_id
                try:
                    fail_ingestion_run(
                        ep_run_id,
                        f"coverage_insufficient: {ep_recs}/{expected_total} = {ep_recs/expected_total*100:.1f}%",
                        ep_recs, ep_recs, len([e for e in errors if e.get("endpoint") == ep]),
                    )
                except Exception:
                    pass
            else:
                finish_ingestion_run(
                    ep_run_id, ep_recs, ep_recs, 0, 0,
                    error_count=len([e for e in errors if e.get("endpoint") == ep]),
                )
                try:
                    set_ingestion_expected_pages(ep_run_id, total_pages)
                except Exception:
                    pass
        except Exception:
            pass

    md = _build_summary_md(config, results, metrics, errors, t0, output_dir)
    mj = _build_metrics_json(config, results, metrics, errors, t0)

    paths = {
        "summary": os.path.join(output_dir, "ingestion_summary.md"),
        "metrics": os.path.join(output_dir, "ingestion_metrics.json"),
    }
    with open(paths["summary"], "w", encoding="utf-8") as f:
        f.write(md)
    with open(paths["metrics"], "w", encoding="utf-8") as f:
        json.dump(mj, f, indent=2, default=str, ensure_ascii=False)
    paths["errors_csv"] = _write_csv(
        output_dir,
        "ingestion_errors.csv",
        ["endpoint", "day", "page", "status_code", "error", "elapsed_ms"],
        [
            [
                e.get("endpoint"),
                e.get("day"),
                e.get("page"),
                e.get("status_code"),
                e.get("error"),
                e.get("elapsed_ms"),
            ]
            for e in errors
        ],
    )
    paths["latency_csv"] = _write_csv(
        output_dir,
        "ingestion_latency.csv",
        ["endpoint", "day", "page", "elapsed_ms", "status_code", "error"],
        [
            [
                m.get("endpoint"),
                m.get("day"),
                m.get("page"),
                m.get("elapsed_ms"),
                m.get("status_code"),
                m.get("error") or "",
            ]
            for m in metrics
        ],
    )

    pages = sum(r.get("pages_fetched", 0) for r in results.values())
    recs = sum(r.get("total_records", 0) for r in results.values())
    r429 = len([e for e in errors if e.get("status_code") == 429])
    print(f"\n[ingest] Done.")
    for k, v in paths.items():
        print(f"  {k}: {v}")
    print(f"  Pages: {pages} | Records: {recs} | Errors: {len(errors)} | 429s: {r429}")
    return 0


def main() -> int:
    yesterday = (datetime.now(PET) - timedelta(days=1)).strftime("%Y-%m-%d")

    ap = argparse.ArgumentParser(description="Yango Raw Landing — Safe ingestion script")
    ap.add_argument(
        "--park-id",
        default=(settings.YANGO_LIMA_PARK_ID or "").strip()
        or "08e20910d81d42658d4334d3f6d10ac0",
    )
    ap.add_argument("--country", default="peru")
    ap.add_argument("--city", default="lima")
    ap.add_argument(
        "--endpoint-group",
        choices=["orders", "transactions", "driver_profiles", "all"],
        default="transactions",
    )
    ap.add_argument("--date-from", default=yesterday)
    ap.add_argument("--date-to", default=yesterday)
    ap.add_argument("--max-days", type=int, default=3)
    ap.add_argument("--max-concurrency", type=int, default=3)
    ap.add_argument("--max-pages", type=int, default=20)
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    ap.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    ap.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required for real ingestion. Overrides --dry-run.",
    )
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--env-var-name", default=None)
    ap.add_argument(
        "--resume-run-id",
        default=None,
        help="Resume a specific run ID instead of creating a new one",
    )
    ap.add_argument(
        "--expected-total",
        type=int,
        default=None,
        help="Expected total records (for coverage validation)",
    )
    ap.add_argument(
        "--fail-on-coverage-below",
        type=float,
        default=None,
        help="Fail if coverage below this fraction (e.g. 0.99 for 99%%)",
    )
    ap.add_argument(
        "--mark-stalled-after-minutes",
        type=int,
        default=30,
        help="Mark old runs as stalled after N minutes (default: 30)",
    )
    ap.add_argument(
        "--output-audit-dir",
        default=os.path.join(
            _project_root(), "exports", "audits", "yango_raw_landing"
        ),
    )
    # ── Partition mode args ──────────────────────────────
    ap.add_argument(
        "--partition-mode",
        choices=["none", "hour"],
        default="none",
        help="Partition strategy for parallel ingestion (default: none)",
    )
    ap.add_argument(
        "--hour-window-size",
        type=int,
        default=2,
        help="Hour window size for partitioned ingestion (default: 2)",
    )
    ap.add_argument(
        "--max-partitions-parallel",
        type=int,
        default=2,
        help="Max concurrent partitions (default: 2)",
    )
    ap.add_argument(
        "--max-pages-per-partition",
        type=int,
        default=50,
        help="Max pages per partition (default: 50)",
    )
    ap.add_argument(
        "--resume-partitions",
        action="store_true",
        default=False,
        help="Resume from partitioned checkpoint (skip completed partitions)",
    )
    ap.add_argument(
        "--max-runtime-minutes",
        type=int,
        default=None,
        help="Max runtime in minutes before aborting",
    )
    ap.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=None,
        help="HTTP request timeout in seconds (default: from settings)",
    )
    args = ap.parse_args()

    try:
        fd = datetime.strptime(args.date_from, "%Y-%m-%d")
        td = datetime.strptime(args.date_to, "%Y-%m-%d")
    except ValueError:
        print("ERROR: dates must be YYYY-MM-DD", file=sys.stderr)
        return 1
    if (td - fd).days >= args.max_days:
        print(
            f"ERROR: date range ({args.date_from} -> {args.date_to}) "
            f"exceeds --max-days={args.max_days}",
            file=sys.stderr,
        )
        return 1

    if args.confirm_live:
        args.dry_run = False

    if not args.dry_run and not settings.YANGO_API_ENABLED:
        print(
            "WARNING: YANGO_API_ENABLED=false. Enabling --dry-run.",
            file=sys.stderr,
        )
        args.dry_run = True

    endpoint_groups = (
        ["orders", "transactions", "driver_profiles"]
        if args.endpoint_group == "all"
        else [args.endpoint_group]
    )

    print(f"\n[ingest] Yango Raw Landing")
    print(f"  Park: {_mask(args.park_id)}")
    print(f"  Range: {args.date_from} -> {args.date_to}")
    print(f"  Endpoints: {endpoint_groups}")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Max pages: {args.max_pages}")
    print(f"  Concurrency: {args.max_concurrency}")
    print(f"  Output: {args.output_audit_dir}")
    print()

    return asyncio.run(
        run_ingestion(
            park_id=args.park_id,
            date_from=args.date_from,
            date_to=args.date_to,
            endpoint_groups=endpoint_groups,
            max_concurrency=args.max_concurrency,
            max_pages=args.max_pages,
            dry_run=args.dry_run,
            output_dir=args.output_audit_dir,
            resume=args.resume,
            partition_mode=args.partition_mode,
            hour_window_size=args.hour_window_size,
            max_partitions_parallel=args.max_partitions_parallel,
            max_pages_per_partition=args.max_pages_per_partition,
            resume_run_id=args.resume_run_id,
            expected_total=args.expected_total,
            fail_on_coverage_below=args.fail_on_coverage_below,
            mark_stalled_after_minutes=args.mark_stalled_after_minutes,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
