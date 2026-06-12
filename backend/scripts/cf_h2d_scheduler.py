"""
CF-H2D — Lima Near Real-Time Shadow Scheduler

Incremental Yango API ingestion every ~5 minutes for Lima park.
Uses watermarks with last_event_at to fetch only new data.
Shadow mode — does NOT touch Omniview productivo.

Usage:
  python -m scripts.cf_h2d_scheduler --cycles 6 --interval 300
  python -m scripts.cf_h2d_scheduler --once
  python -m scripts.cf_h2d_scheduler --dry-run
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, time, re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import psycopg2
from psycopg2.extras import execute_values

from app.settings import settings

PET = timezone(timedelta(hours=-5))
LIMA = "08e20910d81d42658d4334d3f6d10ac0"
API_BASE = "https://fleet-api.yango.tech"
ORDERS_PATH = "/v1/parks/orders/list"
TXN_PATH = "/v2/parks/transactions/list"
PAGE_SIZE = 500
TXN_PAGE_SIZE = 1000
API_TIMEOUT = 60
MAX_RETRIES = 2
SAFETY_OVERLAP_MIN = 15


def _fmt(t: datetime) -> str:
    return t.isoformat()


def _now() -> datetime:
    return datetime.now(PET)


def _ts() -> str:
    return _now().isoformat()


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


def _db_conn():
    return psycopg2.connect(
        host=settings.DB_HOST or "localhost",
        port=settings.DB_PORT or 5432,
        database=settings.DB_NAME or "yego_integral",
        user=settings.DB_USER or "",
        password=settings.DB_PASSWORD or "",
        options="-c statement_timeout=600000",
    )


# ═══════════════════════════════════════════════════════════════════════
# WATERMARK
# ═══════════════════════════════════════════════════════════════════════

def _get_watermark(park_id: str, endpoint: str) -> Optional[Dict[str, Any]]:
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT last_event_at, last_source_date, last_run_id, status FROM raw_yango.ingestion_watermark WHERE park_id=%s AND endpoint_group=%s",
            (park_id, endpoint),
        )
        r = cur.fetchone()
        conn.close()
        if r:
            return {"last_event_at": r[0], "last_source_date": r[1], "last_run_id": r[2], "status": r[3]}
        return None
    except Exception:
        return None


def _update_watermark(park_id: str, endpoint: str, last_event_at: datetime, run_id: str):
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO raw_yango.ingestion_watermark (park_id, endpoint_group, last_event_at, last_source_date, last_run_id, last_run_at, status, records_total, consecutive_failures) VALUES (%s,%s,%s,%s,%s,NOW(),'active',0,0) ON CONFLICT (park_id, endpoint_group) DO UPDATE SET last_event_at=EXCLUDED.last_event_at, last_run_id=EXCLUDED.last_run_id, last_run_at=EXCLUDED.last_run_at, status='active', consecutive_failures=0, updated_at=NOW()",
            (park_id, endpoint, last_event_at, last_event_at.strftime("%Y-%m-%d"), run_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"    [WARN] watermark update: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════
# SCHEDULER RUN LOG
# ═══════════════════════════════════════════════════════════════════════

def _log_cycle_start(cycle_id: str, park_id: str, endpoint: str, wm_before, q_from, q_to) -> int:
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ops.yango_shadow_scheduler_run_log (cycle_id, park_id, endpoint_group, watermark_before, safety_overlap_min, query_from, query_to, status) VALUES (%s,%s,%s,%s,%s,%s,%s,'running') RETURNING id",
            (cycle_id, park_id, endpoint, wm_before, SAFETY_OVERLAP_MIN, q_from, q_to),
        )
        rid = cur.fetchone()[0]
        conn.commit()
        conn.close()
        return rid
    except Exception:
        return -1


def _log_cycle_finish(log_id: int, pages: int, fetched: int, inserted: int, skipped: int, errors: int, runtime: float, last_evt, freshness: float, status: str, err_msg: str = None):
    if log_id < 0:
        return
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE ops.yango_shadow_scheduler_run_log SET cycle_finished_at=NOW(), runtime_seconds=%s, pages_fetched=%s, records_fetched=%s, records_inserted=%s, records_skipped=%s, errors_count=%s, last_event_at=%s, freshness_seconds=%s, status=%s, error_message=%s WHERE id=%s",
            (runtime, pages, fetched, inserted, skipped, errors, last_evt, freshness, status, err_msg, log_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# API FETCH
# ═══════════════════════════════════════════════════════════════════════

def _fetch_page(url: str, hdrs: dict, body: dict) -> dict:
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, headers=hdrs, json=body, timeout=API_TIMEOUT)
            if resp.status_code == 429:
                time.sleep(3.0 * (attempt + 1))
                continue
            if resp.status_code == 200:
                return {"ok": True, "data": resp.json(), "status": 200, "error": None}
            if resp.status_code >= 500 and attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
                continue
            return {"ok": False, "data": None, "status": resp.status_code, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(2)
            continue
            return {"ok": False, "data": None, "status": 0, "error": str(e)[:100]}
    return {"ok": False, "data": None, "status": 0, "error": "max retries"}


# ═══════════════════════════════════════════════════════════════════════
# INCREMENTAL CYCLE
# ═══════════════════════════════════════════════════════════════════════

def _run_cycle(park_id: str, endpoint: str, dry_run: bool = False) -> Dict[str, Any]:
    cid, key = _get_creds()
    if not cid or not key:
        return {"error": "Missing credentials"}
    hdrs = _headers(cid, key)

    wm = _get_watermark(park_id, endpoint)
    now_ts = _now()
    cycle_id = str(uuid4())

    if wm and wm["last_event_at"]:
        q_from = wm["last_event_at"] - timedelta(minutes=SAFETY_OVERLAP_MIN)
    else:
        q_from = now_ts - timedelta(hours=1)

    q_to = now_ts

    log_id = -1
    if not dry_run:
        log_id = _log_cycle_start(cycle_id, park_id, endpoint, wm["last_event_at"] if wm else None, q_from, q_to)

    path = TXN_PATH if endpoint == "transactions" else ORDERS_PATH
    pg_size = TXN_PAGE_SIZE if endpoint == "transactions" else PAGE_SIZE
    event_field = "event_at" if endpoint == "transactions" else "ended_at"
    response_key = "transactions" if endpoint == "transactions" else "orders"
    table = "raw_yango.transactions_raw" if endpoint == "transactions" else "raw_yango.orders_raw"

    if endpoint == "transactions":
        query_filter = {"park": {"id": park_id, "transaction": {"event_at": {"from": _fmt(q_from), "to": _fmt(q_to)}}}}
    else:
        query_filter = {"park": {"id": park_id, "order": {"ended_at": {"from": _fmt(q_from), "to": _fmt(q_to)}, "statuses": ["complete"]}}}

    body = {"limit": pg_size, "query": query_filter}
    url = f"{API_BASE}{path}"

    cursor_val = None
    pages = 0
    fetched_total = 0
    inserted_total = 0
    skipped_total = 0
    errors = 0
    max_event_at = wm["last_event_at"] if wm and wm["last_event_at"] else None
    start_time = time.time()

    while True:
        if cursor_val:
            body["cursor"] = cursor_val

        result = _fetch_page(url, hdrs, body)
        if not result["ok"]:
            errors += 1
            break

        data = result["data"]
        records = data.get(response_key, [])
        if not records:
            for k in [response_key, "items"]:
                if k in data and isinstance(data[k], list):
                    records = data[k]
                    break

        pages += 1
        fetched = len(records)
        fetched_total += fetched

        if records and not dry_run:
            rows = []
            for rec in records:
                ph = _hash(rec)
                evt_str = rec.get(event_field)
                if evt_str:
                    try:
                        evt_dt = datetime.fromisoformat(str(evt_str).replace("Z", "+00:00"))
                        if max_event_at is None or evt_dt > max_event_at:
                            max_event_at = evt_dt
                    except Exception:
                        pass

                if endpoint == "orders":
                    rows.append((
                        str(rec.get("id", "")), park_id, str(rec.get("status", "")),
                        rec.get("created_at"), rec.get("booked_at"), rec.get("ended_at"),
                        str((rec.get("driver_profile") or {}).get("id", "")),
                        str((rec.get("car") or {}).get("id", "")),
                        str(rec.get("category", "")), str(rec.get("payment_method", "")),
                        str(rec.get("provider", "")),
                        float(rec["price"]) if rec.get("price") else None,
                        float(rec["mileage"]) if rec.get("mileage") else None,
                        "PEN",
                        json.dumps(rec, default=str, ensure_ascii=False), ph,
                        datetime.now(PET), cycle_id, endpoint, "1.0",
                    ))
                else:
                    rows.append((
                        str(rec.get("id", "")), park_id, rec.get("event_at"),
                        str(rec.get("category_id", "")), str(rec.get("category_name", "")),
                        str(rec.get("group_id", "")),
                        float(rec["amount"]) if rec.get("amount") else 0.0,
                        str(rec.get("currency_code", "PEN")),
                        str(rec.get("description", "")),
                        str(rec.get("driver_profile_id", "")),
                        str(rec.get("order_id", "")),
                        str((rec.get("created_by") or {}).get("identity", "")),
                        json.dumps(rec, default=str, ensure_ascii=False), ph,
                        datetime.now(PET), cycle_id, endpoint, "1.0",
                    ))

            if rows:
                try:
                    conn = _db_conn()
                    cur = conn.cursor()
                    if endpoint == "orders":
                        sql = "INSERT INTO raw_yango.orders_raw (order_id, park_id, order_status, order_created_at, order_booked_at, order_ended_at, driver_profile_id, car_id, category, payment_method, provider, price, mileage, currency_code, raw_payload, raw_payload_hash, api_fetched_at, api_run_id, source_endpoint, schema_version) VALUES %s ON CONFLICT (park_id, order_id, raw_payload_hash) DO NOTHING"
                    else:
                        sql = "INSERT INTO raw_yango.transactions_raw (transaction_id, park_id, event_at, category_id, category_name, group_id, amount, currency_code, description, driver_profile_id, order_id, created_by_identity, raw_payload, raw_payload_hash, api_fetched_at, api_run_id, source_endpoint, schema_version) VALUES %s ON CONFLICT (park_id, transaction_id, raw_payload_hash) DO NOTHING"
                    execute_values(cur, sql, rows, page_size=len(rows))
                    inserted_total += cur.rowcount
                    conn.commit()
                    conn.close()
                except Exception as e:
                    errors += 1
                    print(f"    DB error: {str(e)[:80]}")

        elapsed = time.time() - start_time
        print(f"    pg{pages}: {fetched} recs (fetched={fetched_total} ins={inserted_total}) [{elapsed:.0f}s]")

        next_cursor = data.get("cursor") or data.get("next_cursor")
        if not next_cursor:
            break
        cursor_val = next_cursor
        time.sleep(0.2)

    duration = round(time.time() - start_time, 2)
    freshness = round((now_ts - max_event_at).total_seconds(), 1) if max_event_at else None

    status = "completed"
    if errors > 0:
        status = "partial"

    if not dry_run:
        _update_watermark(park_id, endpoint, max_event_at or now_ts, cycle_id)
        _log_cycle_finish(log_id, pages, fetched_total, inserted_total, 0, errors, duration, max_event_at, freshness, status)

    return {
        "cycle_id": cycle_id[:12],
        "endpoint": endpoint,
        "pages": pages,
        "fetched": fetched_total,
        "inserted": inserted_total,
        "errors": errors,
        "duration_sec": duration,
        "freshness_sec": freshness,
        "max_event_at": str(max_event_at)[:19] if max_event_at else None,
        "status": status,
    }


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def _clean_zombies():
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute("UPDATE ops.yango_shadow_scheduler_run_log SET status='zombie', error_message='stale cycle' WHERE status='running' AND cycle_started_at < NOW() - INTERVAL '30 minutes'")
        n = cur.rowcount
        conn.commit()
        conn.close()
        if n:
            print(f"  Cleaned {n} zombie scheduler cycles")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description="CF-H2D Near Real-Time Shadow Scheduler")
    ap.add_argument("--cycles", type=int, default=6, help="Number of cycles to run")
    ap.add_argument("--interval", type=int, default=300, help="Seconds between cycles (default 300 = 5 min)")
    ap.add_argument("--once", action="store_true", help="Run single cycle")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--park-id", default=LIMA)
    ap.add_argument("--endpoint", choices=["orders", "transactions", "both"], default="both")
    args = ap.parse_args()

    if args.once:
        args.cycles = 1
        args.interval = 0

    cid, key = _get_creds()
    print(f"CF-H2D Near Real-Time Shadow Scheduler")
    print(f"  Park: {_mask(args.park_id)}")
    print(f"  Endpoints: {args.endpoint}")
    print(f"  Cycles: {args.cycles} | Interval: {args.interval}s")
    print(f"  Credentials: {'OK' if cid and key else 'MISSING'}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  Safety overlap: {SAFETY_OVERLAP_MIN} min")
    print()

    endpoints = ["orders", "transactions"] if args.endpoint == "both" else [args.endpoint]

    all_results = []
    for cycle_num in range(1, args.cycles + 1):
        _clean_zombies()
        cycle_start = _now()
        print(f"[Cycle {cycle_num}/{args.cycles}] {_ts()}")
        print("-" * 50)

        cycle_results = []
        for ep in endpoints:
            wm = _get_watermark(args.park_id, ep)
            wm_str = str(wm["last_event_at"])[:19] if wm and wm["last_event_at"] else "NONE"
            print(f"  {ep}: watermark={wm_str}")

            r = _run_cycle(args.park_id, ep, dry_run=args.dry_run)
            cycle_results.append(r)

            if r.get("error"):
                print(f"    ERROR: {r['error']}")
            else:
                print(f"    -> {r['fetched']} recs, {r['pages']} pages, "
                      f"ins={r['inserted']}, {r['duration_sec']}s, "
                      f"freshness={r['freshness_sec']}s, "
                      f"last_event={r['max_event_at']} [{r['status']}]")

        all_results.append({"cycle": cycle_num, "results": cycle_results})

        cycle_elapsed = (_now() - cycle_start).total_seconds()
        print(f"  Cycle {cycle_num} done in {cycle_elapsed:.0f}s")
        print()

        if cycle_num < args.cycles and args.interval > 0:
            wait = max(0, args.interval - cycle_elapsed)
            if wait > 0:
                print(f"  Waiting {wait:.0f}s until next cycle...")
                time.sleep(wait)

    print("=" * 60)
    print("DONE")
    for cr in all_results:
        for r in cr["results"]:
            print(f"  Cycle {cr['cycle']:>2d} {r['endpoint']:15s}: "
                  f"fetched={r.get('fetched', 0):>5d} ins={r.get('inserted', 0):>5d} "
                  f"pages={r.get('pages', 0):>2d} "
                  f"runtime={r.get('duration_sec', 0):>6.1f}s "
                  f"freshness={r.get('freshness_sec', 0):>6.1f}s "
                  f"[{r.get('status', '?')}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
