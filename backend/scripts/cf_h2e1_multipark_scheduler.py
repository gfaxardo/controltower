"""
CF-H2E.1 — Multipark Shadow Scheduler

Iterates all active parks from raw_yango.api_park_credentials_registry.
Runs orders + transactions ingestion per park with independent watermarks.
Failure isolation: one park failing does not stop others.

Usage:
    python -m scripts.cf_h2e1_multipark_scheduler --once
    python -m scripts.cf_h2e1_multipark_scheduler --dry-run
    python -m scripts.cf_h2e1_multipark_scheduler --parks lima,trujillo
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
import psycopg2
from psycopg2.extras import execute_values

from app.settings import settings

PET = timezone(timedelta(hours=-5))
API_BASE = "https://fleet-api.yango.tech"
ORDERS_PATH = "/v1/parks/orders/list"
TXN_PATH = "/v2/parks/transactions/list"
PAGE_SIZE = 500
TXN_PAGE_SIZE = 1000
API_TIMEOUT = 60
MAX_RETRIES = 2
SAFETY_OVERLAP_MIN = 15

PILOT_PARKS = [
    "08e20910d81d42658d4334d3f6d10ac0",  # Lima
    "851e30755bba4d298e2e837f571b4ab8",  # Trujillo
    "56e4607dfc354e0a9cde4f0aa7973003",  # Arequipa
    "64085dd85e124e2c808806f70d527ea8",  # Pro
    "e3e07c00ed914f82a59c03283a178d6e",  # TukTuk
]


def _fmt(t: datetime) -> str:
    return t.isoformat()


def _now() -> datetime:
    return datetime.now(PET)


def _hash(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _mask(v: str) -> str:
    return (v[:8] + "***") if v and len(v) > 8 else "***"


def _db_conn():
    return psycopg2.connect(
        host=settings.DB_HOST or "localhost",
        port=settings.DB_PORT or 5432,
        database=settings.DB_NAME or "yego_integral",
        user=settings.DB_USER or "",
        password=settings.DB_PASSWORD or "",
        options="-c statement_timeout=600000",
    )


def _get_parks_from_registry() -> List[Dict[str, Any]]:
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT park_id, fleet_name, park_name, city, env_var_name, credential_status "
            "FROM raw_yango.api_park_credentials_registry "
            "WHERE is_active = true AND credential_status != 'INVALID' "
            "ORDER BY park_id"
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {"park_id": r[0], "fleet_name": r[1], "park_name": r[2],
             "city": r[3], "env_var_name": r[4], "credential_status": r[5]}
            for r in rows
        ]
    except Exception as e:
        print(f"[WARN] Cannot read credential registry: {e}")
        return []


def _get_park_creds(env_var_name: str) -> tuple:
    if not env_var_name:
        return "", ""
    cid = os.environ.get(f"{env_var_name}_CLIENT_ID", "")
    key = os.environ.get(f"{env_var_name}_API_KEY", "")
    if not cid:
        cid = os.environ.get(env_var_name, "")
    return cid, key


def _headers(cid, key):
    return {"X-Client-ID": cid, "X-API-Key": key, "Content-Type": "application/json", "Accept-Language": "en"}


def _get_watermark(park_id: str, endpoint: str) -> Optional[Dict[str, Any]]:
    try:
        conn = _db_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT last_event_at, last_source_date, last_run_id, status "
            "FROM raw_yango.ingestion_watermark WHERE park_id=%s AND endpoint_group=%s",
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
            "INSERT INTO raw_yango.ingestion_watermark "
            "(park_id, endpoint_group, last_event_at, last_source_date, last_run_id, last_run_at, status, records_total, consecutive_failures) "
            "VALUES (%s,%s,%s,%s,%s,NOW(),'active',0,0) "
            "ON CONFLICT (park_id, endpoint_group) DO UPDATE SET "
            "last_event_at=EXCLUDED.last_event_at, last_run_id=EXCLUDED.last_run_id, last_run_at=EXCLUDED.last_run_at, "
            "status='active', consecutive_failures=0, updated_at=NOW()",
            (park_id, endpoint, last_event_at, last_event_at.strftime("%Y-%m-%d"), run_id),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"    [WARN] watermark update for {_mask(park_id)}: {e}")
        return False


def _run_cycle(park_id: str, park_name: str, cid: str, key: str,
               endpoint: str, dry_run: bool = False) -> Dict[str, Any]:
    if not cid or not key:
        return {"error": "Missing credentials", "status": "failed"}

    hdrs = _headers(cid, key)
    wm = _get_watermark(park_id, endpoint)
    now_ts = _now()
    cycle_id = str(uuid4())

    if wm and wm["last_event_at"]:
        q_from = wm["last_event_at"] - timedelta(minutes=SAFETY_OVERLAP_MIN)
    else:
        q_from = now_ts - timedelta(hours=1)

    q_to = now_ts
    path = TXN_PATH if endpoint == "transactions" else ORDERS_PATH
    pg_size = TXN_PAGE_SIZE if endpoint == "transactions" else PAGE_SIZE
    event_field = "event_at" if endpoint == "transactions" else "ended_at"
    response_key = "transactions" if endpoint == "transactions" else "orders"

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
    errors = 0
    max_event_at = wm["last_event_at"] if wm and wm["last_event_at"] else None
    start_time = time.time()

    def _fetch_page(url, hdrs, body):
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
                    conn2 = _db_conn()
                    cur2 = conn2.cursor()
                    if endpoint == "orders":
                        sql = ("INSERT INTO raw_yango.orders_raw "
                               "(order_id, park_id, order_status, order_created_at, order_booked_at, order_ended_at, "
                               "driver_profile_id, car_id, category, payment_method, provider, price, mileage, "
                               "currency_code, raw_payload, raw_payload_hash, api_fetched_at, api_run_id, "
                               "source_endpoint, schema_version) VALUES %s "
                               "ON CONFLICT (park_id, order_id, raw_payload_hash) DO NOTHING")
                    else:
                        sql = ("INSERT INTO raw_yango.transactions_raw "
                               "(transaction_id, park_id, event_at, category_id, category_name, group_id, "
                               "amount, currency_code, description, driver_profile_id, order_id, "
                               "created_by_identity, raw_payload, raw_payload_hash, api_fetched_at, "
                               "api_run_id, source_endpoint, schema_version) VALUES %s "
                               "ON CONFLICT (park_id, transaction_id, raw_payload_hash) DO NOTHING")
                    execute_values(cur2, sql, rows, page_size=len(rows))
                    inserted_total += cur2.rowcount
                    conn2.commit()
                    conn2.close()
                except Exception as e:
                    errors += 1
                    print(f"      DB error [{_mask(park_id)}]: {str(e)[:80]}")

        next_cursor = data.get("cursor") or data.get("next_cursor")
        if not next_cursor:
            break
        cursor_val = next_cursor
        time.sleep(0.2)

    duration = round(time.time() - start_time, 2)
    freshness = round((now_ts - max_event_at).total_seconds(), 1) if max_event_at else None

    if errors > 0:
        status = "partial"
    elif fetched_total == 0:
        status = "empty"
    else:
        status = "completed"

    if not dry_run and max_event_at:
        _update_watermark(park_id, endpoint, max_event_at or now_ts, cycle_id)

    return {
        "park_id": _mask(park_id),
        "park_name": park_name,
        "endpoint": endpoint,
        "pages": pages,
        "fetched": fetched_total,
        "inserted": inserted_total,
        "errors": errors,
        "duration_sec": duration,
        "freshness_sec": freshness,
        "status": status,
    }


def main():
    ap = argparse.ArgumentParser(description="CF-H2E.1 Multipark Shadow Scheduler")
    ap.add_argument("--once", action="store_true", help="Single cycle for all parks")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--parks", type=str, help="Comma-separated park_ids or 'all'")
    ap.add_argument("--endpoint", choices=["orders", "transactions", "both"], default="both")
    ap.add_argument("--max-parks", type=int, default=5)
    args = ap.parse_args()

    parks = _get_parks_from_registry()
    if not parks:
        parks = [{"park_id": pid, "park_name": pid[:8], "env_var_name": None} for pid in PILOT_PARKS]

    if args.parks and args.parks != "all":
        requested = set(args.parks.split(","))
        parks = [p for p in parks if p["park_id"] in requested or p["park_id"][:8] in requested]

    parks = parks[:args.max_parks]

    print("=" * 70)
    print("CF-H2E.1 Multipark Shadow Scheduler")
    print("=" * 70)
    print(f"  Parks: {len(parks)}")
    for p in parks:
        print(f"    {_mask(p['park_id'])} | {p['park_name']:<20} | {p.get('city','?'):<12} | env={p.get('env_var_name','NONE')}")
    print(f"  Endpoints: {args.endpoint}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    endpoints = ["orders", "transactions"] if args.endpoint == "both" else [args.endpoint]
    all_results = []
    park_errors = []

    for park in parks:
        park_id = park["park_id"]
        park_name = park.get("park_name", park_id[:8])
        env_var = park.get("env_var_name")

        print(f"[{park_name}] ({_mask(park_id)})")
        print("-" * 50)

        cid, key = _get_park_creds(env_var)
        if not cid or not key:
            if park_id == PILOT_PARKS[0]:
                cid = os.environ.get("YANGO_LIMA_CLIENT_ID") or settings.YANGO_CLIENT_ID or ""
                key = os.environ.get("YANGO_LIMA_API_KEY") or settings.YANGO_API_KEY or ""

        if not cid or not key:
            print(f"  SKIP: No credentials for park (env_var={env_var})")
            park_errors.append({"park": park_name, "error": "missing_credentials"})
            print()
            continue

        park_results = []
        for ep in endpoints:
            wm = _get_watermark(park_id, ep)
            wm_str = str(wm["last_event_at"])[:19] if wm and wm["last_event_at"] else "NONE"
            print(f"  {ep}: watermark={wm_str}")

            try:
                r = _run_cycle(park_id, park_name, cid, key, ep, dry_run=args.dry_run)
            except Exception as e:
                r = {"error": str(e)[:150], "status": "failed", "park_name": park_name, "endpoint": ep}
                print(f"    EXCEPTION: {str(e)[:100]}")

            park_results.append(r)

            if r.get("error"):
                print(f"    ERROR: {r['error']}")
            else:
                print(f"    -> {r['fetched']} recs, {r['pages']} pages, "
                      f"ins={r['inserted']}, {r['duration_sec']}s, "
                      f"fresh={r['freshness_sec']}s [{r['status']}]")

        all_results.append({"park_id": _mask(park_id), "park_name": park_name, "results": park_results})
        print()

    print("=" * 70)
    print("MULTIPARK SUMMARY")
    print("=" * 70)
    total_fetched = 0
    total_inserted = 0
    total_runtime = 0
    success_parks = 0
    for pr in all_results:
        park_ok = True
        for r in pr["results"]:
            if r.get("error"):
                park_ok = False
            total_fetched += r.get("fetched", 0)
            total_inserted += r.get("inserted", 0)
            total_runtime += r.get("duration_sec", 0)
            status = r.get("status", "?")
            print(f"  {pr['park_name']:<20} {r.get('endpoint','?'):<15} "
                  f"fetched={r.get('fetched',0):>6d} ins={r.get('inserted',0):>6d} "
                  f"pages={r.get('pages',0):>3d} {r.get('duration_sec',0):>6.1f}s [{status}]")
        if park_ok:
            success_parks += 1

    print(f"\n  TOTAL: fetched={total_fetched} inserted={total_inserted} runtime={total_runtime:.0f}s")
    print(f"  Parks: {success_parks}/{len(all_results)} successful")
    if park_errors:
        print(f"  Park errors: {len(park_errors)}")
        for pe in park_errors:
            print(f"    - {pe['park']}: {pe['error']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
