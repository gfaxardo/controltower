"""
CF-H2C.0A — Lima Recovery & Re-Ingestion Script

Dedicated synchronous ingestion for Lima park (08e20910...).
Orders + Transactions from 2026-06-01 to date.
No max_pages truncation. Full cursor traversal. Checkpoint/resume.

Usage:
  python -m scripts.cf_h2c0a_lima_reingest --endpoint orders --date 2026-06-10
  python -m scripts.cf_h2c0a_lima_reingest --endpoint orders --date-from 2026-06-01 --date-to 2026-06-11
  python -m scripts.cf_h2c0a_lima_reingest --endpoint transactions --date 2026-06-10
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from psycopg2.extras import execute_values

from app.db.connection import get_db
from app.repositories.raw_yango_repository import create_ingestion_run, finish_ingestion_run, fail_ingestion_run
from app.settings import settings

PET = timezone(timedelta(hours=-5))
LIMA_PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"
API_BASE = "https://fleet-api.yango.tech"
ORDERS_PAGE_SIZE = 500
TXN_PAGE_SIZE = 1000
REQUEST_TIMEOUT = 60
MAX_RETRIES = 2
MIN_INTERVAL = 0.3


def _get_creds():
    prefix = "YANGO_LIMA"
    cid = os.environ.get(f"{prefix}_CLIENT_ID") or settings.YANGO_CLIENT_ID or ""
    key = os.environ.get(f"{prefix}_API_KEY") or settings.YANGO_API_KEY or ""
    return cid, key


def _headers(client_id, api_key):
    return {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept-Language": "en",
    }


def _fmt(t: datetime) -> str:
    return t.isoformat()


def _hash(d: dict) -> str:
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()


def _mask(v: str) -> str:
    return (v[:8] + "***") if v and len(v) > 8 else "***"


def _mark_zombie_runs():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE raw_yango.api_ingestion_run
            SET status = 'failed',
                notes = COALESCE(notes, '') || ' [zombie cleanup]'
            WHERE status = 'running'
              AND started_at < NOW() - INTERVAL '1 hour'
        """)
        n = cur.rowcount
        if n:
            print(f"  Cleaned {n} zombie runs")
        conn.commit()
        cur.close()


def _check_completed_run(park_id: str, endpoint: str, date_str: str) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM raw_yango.api_ingestion_run
            WHERE park_id = %s AND endpoint_group = %s
              AND date_from = %s AND date_to = %s AND status = 'completed'
            LIMIT 1
        """, (park_id, endpoint, date_str, date_str))
        exists = cur.fetchone() is not None
        cur.close()
        return exists


def _upsert_watermark(park_id: str, endpoint: str, source_date: str, run_id: str, records: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO raw_yango.ingestion_watermark
                (park_id, endpoint_group, last_source_date, last_run_id,
                 records_total, status, consecutive_failures, last_completed_at)
            VALUES (%s, %s, %s, %s, %s, 'active', 0, NOW())
            ON CONFLICT (park_id, endpoint_group) DO UPDATE SET
                last_source_date = EXCLUDED.last_source_date,
                last_run_id = EXCLUDED.last_run_id,
                records_total = raw_yango.ingestion_watermark.records_total + %s,
                status = 'active',
                consecutive_failures = 0,
                last_completed_at = EXCLUDED.last_completed_at,
                updated_at = NOW()
        """, (park_id, endpoint, source_date, run_id, records, records))
        conn.commit()
        cur.close()


def ingest_orders(park_id: str, date_str: str, dry_run: bool = False) -> dict:
    cid, key = _get_creds()
    if not cid or not key:
        return {"error": "Missing credentials"}
    hdrs = _headers(cid, key)

    base = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=PET)
    t_from = base
    t_to = base.replace(hour=23, minute=59, second=59)

    body = {
        "limit": ORDERS_PAGE_SIZE,
        "query": {
            "park": {
                "id": park_id,
                "order": {
                    "ended_at": {"from": _fmt(t_from), "to": _fmt(t_to)},
                    "statuses": ["complete"],
                },
            }
        },
    }

    run_id = str(uuid4())
    print(f"  run={run_id[:12]}...")

    if not dry_run:
        create_ingestion_run(run_id, "orders", park_id, date_str, date_str)

    cursor_val = None
    fetched_total = 0
    inserted_total = 0
    skipped_total = 0
    pages = 0
    errors = 0
    start_time = time.time()

    while True:
        if cursor_val:
            body["cursor"] = cursor_val

        data = None
        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    f"{API_BASE}/v1/parks/orders/list",
                    headers=hdrs, json=body, timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 429:
                    time.sleep(3.0)
                    continue
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}"
                    if resp.status_code >= 500 and attempt < MAX_RETRIES:
                        time.sleep(2 ** attempt)
                        continue
                    break
                data = resp.json()
                last_err = None
                break
            except requests.Timeout:
                last_err = "timeout"
                if attempt < MAX_RETRIES:
                    time.sleep(2)
                continue
            except Exception as e:
                last_err = str(e)[:100]
                if attempt < MAX_RETRIES:
                    time.sleep(2)
                continue

        if last_err or data is None:
            errors += 1
            print(f"    page {pages + 1}: ERROR {last_err or 'no data'}")
            break

        orders = data.get("orders", [])
        pages += 1
        fetched = len(orders)
        fetched_total += fetched

        if orders and not dry_run:
            rows = []
            for o in orders:
                ph = _hash(o)
                rows.append((
                    str(o.get("id", "")),
                    park_id,
                    str(o.get("status", "")),
                    str(o.get("short_id", ""))[:20] if o.get("short_id") else None,
                    o.get("created_at"),
                    o.get("booked_at"),
                    o.get("ended_at"),
                    str((o.get("driver_profile") or {}).get("id", "")),
                    str((o.get("car") or {}).get("id", "")),
                    str(o.get("category", "")),
                    str(o.get("payment_method", "")),
                    str(o.get("provider", "")),
                    float(o["price"]) if o.get("price") else None,
                    float(o["mileage"]) if o.get("mileage") else None,
                    "PEN",
                    json.dumps(o, default=str, ensure_ascii=False),
                    ph,
                    datetime.now(PET),
                    run_id,
                    "orders/list",
                    "1.0",
                ))

            try:
                with get_db() as conn:
                    cur = conn.cursor()
                    for r in rows:
                        try:
                            cur.execute("""
                                INSERT INTO raw_yango.orders_raw (
                                    order_id, park_id, order_status, order_short_id,
                                    order_created_at, order_booked_at, order_ended_at,
                                    driver_profile_id, car_id, category, payment_method,
                                    provider, price, mileage, currency_code,
                                    raw_payload, raw_payload_hash, api_fetched_at,
                                    api_run_id, source_endpoint, schema_version
                                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (park_id, order_id, raw_payload_hash) DO NOTHING
                            """, r)
                            if cur.rowcount > 0:
                                inserted_total += 1
                            else:
                                skipped_total += 1
                        except Exception:
                            skipped_total += 1
                    conn.commit()
                    cur.close()
            except Exception as e:
                print(f"    DB error (skipping batch): {str(e)[:80]}")

        elapsed = time.time() - start_time
        print(f"    page {pages}: {fetched} orders (total={fetched_total} ins={inserted_total} skip={skipped_total}) "
              f"[{elapsed:.0f}s]")

        next_cursor = data.get("cursor") or data.get("next_cursor")
        if not next_cursor:
            print(f"  CURSOR EXHAUSTED after {pages} pages")
            break

        cursor_val = next_cursor
        time.sleep(MIN_INTERVAL)

    duration = time.time() - start_time
    result = {
        "run_id": run_id, "date": date_str, "park_id": park_id,
        "endpoint": "orders", "pages": pages, "fetched": fetched_total,
        "inserted": inserted_total, "skipped": skipped_total,
        "errors": errors, "duration_sec": duration, "dry_run": dry_run,
    }

    if not dry_run:
        if errors == 0:
            finish_ingestion_run(run_id, fetched_total, inserted_total, 0, skipped_total, errors)
            _upsert_watermark(park_id, "orders", date_str, run_id, inserted_total)
        else:
            fail_ingestion_run(run_id, f"errors={errors}", fetched_total, inserted_total, errors)

    return result


def ingest_transactions(park_id: str, date_str: str, dry_run: bool = False) -> dict:
    cid, key = _get_creds()
    if not cid or not key:
        return {"error": "Missing credentials"}
    hdrs = _headers(cid, key)

    base = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=PET)
    t_from = base
    t_to = base.replace(hour=23, minute=59, second=59)

    body = {
        "limit": TXN_PAGE_SIZE,
        "query": {
            "park": {
                "id": park_id,
                "transaction": {
                    "event_at": {"from": _fmt(t_from), "to": _fmt(t_to)},
                },
            }
        },
    }

    run_id = str(uuid4())
    print(f"  run={run_id[:12]}...")

    if not dry_run:
        create_ingestion_run(run_id, "transactions", park_id, date_str, date_str)

    cursor_val = None
    fetched_total = 0
    inserted_total = 0
    skipped_total = 0
    pages = 0
    errors = 0
    start_time = time.time()

    while True:
        if cursor_val:
            body["cursor"] = cursor_val

        data = None
        last_err = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    f"{API_BASE}/v2/parks/transactions/list",
                    headers=hdrs, json=body, timeout=REQUEST_TIMEOUT,
                )
                if resp.status_code == 429:
                    time.sleep(3.0)
                    continue
                if resp.status_code != 200:
                    last_err = f"HTTP {resp.status_code}"
                    if resp.status_code >= 500 and attempt < MAX_RETRIES:
                        time.sleep(2 ** attempt)
                        continue
                    break
                data = resp.json()
                last_err = None
                break
            except requests.Timeout:
                last_err = "timeout"
                if attempt < MAX_RETRIES:
                    time.sleep(2)
                continue
            except Exception as e:
                last_err = str(e)[:100]
                if attempt < MAX_RETRIES:
                    time.sleep(2)
                continue

        if last_err or data is None:
            errors += 1
            print(f"    page {pages + 1}: ERROR {last_err or 'no data'}")
            break

        txns = data.get("transactions", [])
        if not txns:
            alt_keys = ["items"]
            for k in alt_keys:
                if k in data:
                    txns = data[k]
                    break
        pages += 1
        fetched = len(txns)
        fetched_total += fetched

        if txns and not dry_run:
            rows = []
            for t in txns:
                ph = _hash(t)
                rows.append((
                    str(t.get("id", "")),
                    park_id,
                    t.get("event_at"),
                    str(t.get("category_id", "")),
                    str(t.get("category_name", "")),
                    str(t.get("group_id", "")),
                    float(t["amount"]) if t.get("amount") else 0.0,
                    str(t.get("currency_code", "PEN")),
                    str(t.get("description", "")),
                    str(t.get("driver_profile_id", "")),
                    str(t.get("order_id", "")),
                    str((t.get("created_by") or {}).get("identity", "")),
                    json.dumps(t, default=str, ensure_ascii=False),
                    ph,
                    datetime.now(PET),
                    run_id,
                    "transactions/list",
                    "1.0",
                ))

            with get_db() as conn:
                cur = conn.cursor()
                for r in rows:
                    try:
                        cur.execute("""
                            INSERT INTO raw_yango.transactions_raw (
                                transaction_id, park_id, event_at,
                                category_id, category_name, group_id,
                                amount, currency_code, description,
                                driver_profile_id, order_id, created_by_identity,
                                raw_payload, raw_payload_hash, api_fetched_at,
                                api_run_id, source_endpoint, schema_version
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (park_id, transaction_id, raw_payload_hash) DO NOTHING
                        """, r)
                        if cur.rowcount > 0:
                            inserted_total += 1
                        else:
                            skipped_total += 1
                    except Exception as e:
                        print(f"      insert error: {str(e)[:80]}")
                conn.commit()
                cur.close()

        elapsed = time.time() - start_time
        print(f"    page {pages}: {fetched} txns (total={fetched_total} ins={inserted_total} skip={skipped_total}) "
              f"[{elapsed:.0f}s]")

        next_cursor = data.get("cursor") or data.get("next_cursor")
        if not next_cursor:
            print(f"  CURSOR EXHAUSTED after {pages} pages")
            break

        cursor_val = next_cursor
        time.sleep(MIN_INTERVAL)

    duration = time.time() - start_time
    result = {
        "run_id": run_id, "date": date_str, "park_id": park_id,
        "endpoint": "transactions", "pages": pages, "fetched": fetched_total,
        "inserted": inserted_total, "skipped": skipped_total,
        "errors": errors, "duration_sec": duration, "dry_run": dry_run,
    }

    if not dry_run:
        if errors == 0:
            finish_ingestion_run(run_id, fetched_total, inserted_total, 0, skipped_total, errors)
            _upsert_watermark(park_id, "transactions", date_str, run_id, inserted_total)
        else:
            fail_ingestion_run(run_id, f"errors={errors}", fetched_total, inserted_total, errors)

    return result


def main():
    ap = argparse.ArgumentParser(description="CF-H2C.0A Lima Re-Ingestion")
    ap.add_argument("--endpoint", choices=["orders", "transactions"], required=True)
    ap.add_argument("--date", type=str, help="Single date YYYY-MM-DD")
    ap.add_argument("--date-from", type=str, help="Start date YYYY-MM-DD")
    ap.add_argument("--date-to", type=str, help="End date YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-completed", action="store_true", help="Skip dates with completed runs")
    args = ap.parse_args()

    dates = []
    if args.date:
        dates = [args.date]
    elif args.date_from and args.date_to:
        d = datetime.strptime(args.date_from, "%Y-%m-%d").date()
        end = datetime.strptime(args.date_to, "%Y-%m-%d").date()
        while d <= end:
            dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
    else:
        print("ERROR: need --date or --date-from/--date-to")
        return 1

    cid, key = _get_creds()
    print(f"CF-H2C.0A Lima Re-Ingestion")
    print(f"  Park: {_mask(LIMA_PARK_ID)}")
    print(f"  Endpoint: {args.endpoint}")
    print(f"  Dates: {len(dates)} days ({dates[0]} -> {dates[-1]})")
    print(f"  Credentials: {'OK' if cid and key else 'MISSING'}")
    print(f"  Dry run: {args.dry_run}")
    print()

    _mark_zombie_runs()

    fn = ingest_orders if args.endpoint == "orders" else ingest_transactions

    results = []
    for i, d in enumerate(dates):
        if args.skip_completed and _check_completed_run(LIMA_PARK_ID, args.endpoint, d):
            print(f"[{i + 1}/{len(dates)}] {d}: SKIP (already completed)")
            results.append({"date": d, "skipped": True})
            continue

        print(f"[{i + 1}/{len(dates)}] {d}:")
        r = fn(LIMA_PARK_ID, d, dry_run=args.dry_run)
        results.append(r)
        print(f"  -> {r.get('fetched', 0)} records, {r.get('pages', 0)} pages, "
              f"{r.get('duration_sec', 0):.0f}s\n")

    total_fetched = sum(r.get("fetched", 0) for r in results)
    total_pages = sum(r.get("pages", 0) for r in results)
    total_time = sum(r.get("duration_sec", 0) for r in results)
    print(f"DONE: {len(results)} days, {total_fetched} records, {total_pages} pages, {total_time:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
