"""
CF-H2C.0B.1 — Hardened Transactions Ingestion Worker

Architecture: Day-by-day ingestion with checkpoint-resume.
Each day is an independent job. Fresh DB connection per page.
No global timeout dependency. Watermark-driven skip for completed days.

Usage:
  python -m scripts.cf_h2c0b1_txn_ingest --date 2026-06-10
  python -m scripts.cf_h2c0b1_txn_ingest --date-from 2026-06-01 --date-to 2026-06-11
  python -m scripts.cf_h2c0b1_txn_ingest --date-from 2026-06-01 --date-to 2026-06-11 --dry-run
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, time, re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from app.settings import settings

PET = timezone(timedelta(hours=-5))
LIMA = "08e20910d81d42658d4334d3f6d10ac0"
API_BASE = "https://fleet-api.yango.tech"
TXN_PATH = "/v2/parks/transactions/list"
PAGE_SIZE = 1000
API_TIMEOUT = 90
MAX_RETRIES = 3
MIN_INTERVAL = 0.3
BACKOFF_429 = 3.0

# ═══════════════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════════════

def _fmt(t: datetime) -> str:
    return t.isoformat()

def _hash(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()

def _mask(v: str) -> str:
    return (v[:8] + "***") if v and len(v) > 8 else "***"

def _get_creds():
    cid = os.environ.get("YANGO_LIMA_CLIENT_ID") or settings.YANGO_CLIENT_ID or ""
    key = os.environ.get("YANGO_LIMA_API_KEY") or settings.YANGO_API_KEY or ""
    return cid, key

def _headers(cid, key):
    return {"X-Client-ID": cid, "X-API-Key": key, "Content-Type": "application/json", "Accept-Language": "en"}

# ═══════════════════════════════════════════════════════════════════════
# DB (no pool dependency — fresh connection per operation)
# ═══════════════════════════════════════════════════════════════════════

import psycopg2
from psycopg2.extras import execute_values

def _db_params():
    return {
        "host": settings.DB_HOST or "localhost",
        "port": settings.DB_PORT or 5432,
        "database": settings.DB_NAME or "yego_integral",
        "user": settings.DB_USER or "",
        "password": settings.DB_PASSWORD or "",
        "options": "-c statement_timeout=600000",
    }

def _db_conn():
    return psycopg2.connect(**_db_params())

# ═══════════════════════════════════════════════════════════════════════
# API CALL
# ═══════════════════════════════════════════════════════════════════════

def _fetch_page(url: str, hdrs: dict, body: dict) -> dict:
    """Returns {'ok': bool, 'data': dict|None, 'status': int, 'error': str|None}"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, headers=hdrs, json=body, timeout=API_TIMEOUT)
            if resp.status_code == 429:
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_429 * (attempt + 1))
                continue
            if resp.status_code == 200:
                return {"ok": True, "data": resp.json(), "status": 200, "error": None}
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            return {"ok": False, "data": None, "status": resp.status_code, "error": f"HTTP {resp.status_code}"}
        except requests.Timeout:
            if attempt < MAX_RETRIES:
                time.sleep(2)
            continue
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(2)
            continue
            return {"ok": False, "data": None, "status": 0, "error": str(e)[:100]}
    return {"ok": False, "data": None, "status": 0, "error": "max retries exceeded"}

# ═══════════════════════════════════════════════════════════════════════
# WATERMARK + RUN TRACKING
# ═══════════════════════════════════════════════════════════════════════

def _is_day_completed(park_id: str, date_str: str) -> bool:
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM raw_yango.api_ingestion_run WHERE park_id=%s AND endpoint_group='transactions' AND date_from=%s AND date_to=%s AND status='completed' LIMIT 1", (park_id, date_str, date_str))
        ok = cur.fetchone() is not None
        conn.close()
        return ok
    except Exception:
        return False

def _create_run(run_id: str, park_id: str, date_str: str) -> bool:
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO raw_yango.api_ingestion_run (run_id, endpoint_group, park_id, date_from, date_to, status, source) VALUES (%s,%s,%s,%s,%s,'running','yango_fleet_api')", (run_id, "transactions", park_id, date_str, date_str))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"    [WARN] create_run: {e}")
        return False

def _finish_run(run_id: str, fetched: int, inserted: int, skipped: int, errors: int) -> bool:
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE raw_yango.api_ingestion_run SET status='completed', records_fetched=%s, records_inserted=%s, record_skips=%s, error_count=%s, finished_at=NOW() WHERE run_id=%s", (fetched, inserted, skipped, errors, run_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"    [WARN] finish_run: {e}")
        return False

def _fail_run(run_id: str, msg: str) -> bool:
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE raw_yango.api_ingestion_run SET status='failed', notes=%s, finished_at=NOW() WHERE run_id=%s", (msg[:500], run_id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def _upsert_watermark(park_id: str, date_str: str, run_id: str, records: int):
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO raw_yango.ingestion_watermark (park_id, endpoint_group, last_source_date, last_run_id, records_total, status, consecutive_failures, last_completed_at) VALUES (%s,'transactions',%s,%s,%s,'active',0,NOW()) ON CONFLICT (park_id, endpoint_group) DO UPDATE SET last_source_date=EXCLUDED.last_source_date, last_run_id=EXCLUDED.last_run_id, records_total=raw_yango.ingestion_watermark.records_total+%s, status='active', consecutive_failures=0, last_completed_at=EXCLUDED.last_completed_at, updated_at=NOW()", (park_id, date_str, run_id, records, records))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"    [WARN] watermark: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════
# INGEST ONE DAY
# ═══════════════════════════════════════════════════════════════════════

def ingest_transactions_day(park_id: str, date_str: str, dry_run: bool = False) -> dict:
    cid, key = _get_creds()
    if not cid or not key:
        return {"error": "Missing credentials", "date": date_str}

    hdrs = _headers(cid, key)
    base = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=PET)
    t_from = base
    t_to = base.replace(hour=23, minute=59, second=59)

    body_template = {
        "limit": PAGE_SIZE,
        "query": {"park": {"id": park_id, "transaction": {"event_at": {"from": _fmt(t_from), "to": _fmt(t_to)}}}},
    }

    run_id = str(uuid4())
    print(f"  run={run_id[:12]}... park={_mask(park_id)} date={date_str}")

    if not dry_run:
        _create_run(run_id, park_id, date_str)

    cursor_val = None
    pages = 0
    fetched_total = 0
    inserted_total = 0
    skipped_total = 0
    errors = 0
    start_time = time.time()

    body = dict(body_template)

    while True:
        if cursor_val:
            body["cursor"] = cursor_val

        result = _fetch_page(f"{API_BASE}{TXN_PATH}", hdrs, body)
        if not result["ok"]:
            errors += 1
            print(f"    page {pages + 1}: ERROR {result['error']} (status={result['status']})")
            break

        data = result["data"]
        txns = data.get("transactions", []) or data.get("items", [])
        if not txns:
            for k in ["items"]:
                if k in data and isinstance(data[k], list):
                    txns = data[k]
                    break

        pages += 1
        fetched = len(txns)
        fetched_total += fetched

        # ══════════════════════════════════════════════════════════════
        # INSERT BATCH (fresh connection, no pool)
        # ══════════════════════════════════════════════════════════════
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

            try:
                conn = _db_conn()
                cur = conn.cursor()
                sql = """
                    INSERT INTO raw_yango.transactions_raw (
                        transaction_id, park_id, event_at,
                        category_id, category_name, group_id,
                        amount, currency_code, description,
                        driver_profile_id, order_id, created_by_identity,
                        raw_payload, raw_payload_hash, api_fetched_at,
                        api_run_id, source_endpoint, schema_version
                    ) VALUES %s
                    ON CONFLICT (park_id, transaction_id, raw_payload_hash) DO NOTHING
                """
                execute_values(cur, sql, rows, page_size=len(rows))
                inserted_total += cur.rowcount
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"    DB error (page {pages}): {str(e)[:80]}")

        elapsed = time.time() - start_time
        print(f"    page {pages}: {fetched} txns (total={fetched_total} ins={inserted_total} skip={skipped_total}) [{elapsed:.0f}s]")

        next_cursor = data.get("cursor") or data.get("next_cursor")
        if not next_cursor:
            print(f"    CURSOR EXHAUSTED at page {pages}")
            break

        cursor_val = next_cursor
        time.sleep(MIN_INTERVAL)

        # Re-create body with just cursor (remove query to avoid re-sending full body)
        body = {"limit": PAGE_SIZE, "cursor": cursor_val, "query": body_template["query"]}

    duration = time.time() - start_time

    if not dry_run:
        if errors == 0:
            _finish_run(run_id, fetched_total, inserted_total, skipped_total, errors)
            _upsert_watermark(park_id, date_str, run_id, inserted_total)
        else:
            _fail_run(run_id, f"errors={errors}")

    return {
        "date": date_str, "park_id": park_id, "run_id": run_id,
        "endpoint": "transactions", "pages": pages, "fetched": fetched_total,
        "inserted": inserted_total, "skipped": skipped_total,
        "errors": errors, "duration_sec": round(duration, 1), "dry_run": dry_run,
    }


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="CF-H2C.0B.1 Hardened Transactions Ingestion")
    ap.add_argument("--date", type=str, help="Single date YYYY-MM-DD")
    ap.add_argument("--date-from", type=str, help="Start date")
    ap.add_argument("--date-to", type=str, help="End date")
    ap.add_argument("--park-id", default=LIMA)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-completed", action="store_true", default=True)
    args = ap.parse_args()

    if args.date:
        dates = [args.date]
    elif args.date_from and args.date_to:
        d = datetime.strptime(args.date_from, "%Y-%m-%d").date()
        end = datetime.strptime(args.date_to, "%Y-%m-%d").date()
        dates = []
        while d <= end:
            dates.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
    else:
        print("ERROR: need --date or --date-from/--date-to")
        return 1

    cid, key = _get_creds()
    print(f"CF-H2C.0B.1 Hardened Transactions Ingestion")
    print(f"  Park: {_mask(args.park_id)}")
    print(f"  Dates: {len(dates)} days ({dates[0]} -> {dates[-1]})")
    print(f"  Credentials: {'OK' if cid and key else 'MISSING'}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  Page size: {PAGE_SIZE} | API timeout: {API_TIMEOUT}s | DB: fresh per page")
    print()

    results = []
    for i, d in enumerate(dates):
        if args.skip_completed and _is_day_completed(args.park_id, d):
            print(f"[{i + 1}/{len(dates)}] {d}: SKIP (already completed)")
            results.append({"date": d, "skipped": True})
            continue

        print(f"[{i + 1}/{len(dates)}] {d}:")
        r = ingest_transactions_day(args.park_id, d, dry_run=args.dry_run)
        results.append(r)
        if r.get("error"):
            print(f"  -> ERROR: {r['error']}")
        else:
            print(f"  -> {r.get('fetched', 0)} txns, {r.get('pages', 0)} pages, {r.get('duration_sec', 0)}s")
        print()

    completed = [r for r in results if not r.get("skipped") and not r.get("error")]
    skipped = [r for r in results if r.get("skipped")]
    errors = [r for r in results if r.get("error")]
    total_txn = sum(r.get("fetched", 0) for r in completed)
    total_pages = sum(r.get("pages", 0) for r in completed)
    total_time = sum(r.get("duration_sec", 0) for r in completed)

    print("=" * 60)
    print(f"DONE: {len(completed)} ingested, {len(skipped)} skipped, {len(errors)} errors")
    print(f"  Total txns: {total_txn} | Total pages: {total_pages} | Total time: {total_time:.0f}s")
    if not args.dry_run:
        print(f"  Verify: SELECT event_at::date, COUNT(*) FROM raw_yango.transactions_raw WHERE park_id='{_mask(args.park_id)}...' GROUP BY 1 ORDER BY 1;")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
