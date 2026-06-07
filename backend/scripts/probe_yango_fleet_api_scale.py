#!/usr/bin/env python3
"""
Scale Probe — Yango Fleet API concurrency/latency benchmark.
Read-only. NO inserts, NO writes, NO serving-facts impact.

Usage:
  cd backend
  python -m scripts.probe_yango_fleet_api_scale --date-from 2026-06-01 --date-to 2026-06-03
  python -m scripts.probe_yango_fleet_api_scale --dry-run
  python -m scripts.probe_yango_fleet_api_scale --endpoint-group all --max-concurrency 3
  python -m scripts.probe_yango_fleet_api_scale --resume
"""
from __future__ import annotations

import argparse, asyncio, csv, json, os, sys, time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.settings import settings
import httpx

PET = timezone(timedelta(hours=-5))
MASK_SUFFIX = "***"
MIN_INTER_REQUEST_SEC = 0.5
BACKOFF_429_SEC = 3.0
CHECKPOINT_FILE = "_scale_probe_checkpoint.json"


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mask(val: Optional[str], keep: int = 8) -> str:
    if not val or not isinstance(val, str):
        return MASK_SUFFIX
    return (val[:keep] + MASK_SUFFIX) if len(val) > keep else val[:2] + MASK_SUFFIX


def _mask_payload(obj: Any, depth: int = 0) -> Any:
    if depth > 5:
        return MASK_SUFFIX
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return _mask(obj) if len(obj) > 20 else obj
    if isinstance(obj, list):
        return [_mask_payload(it, depth + 1) for it in obj[:5]]
    if isinstance(obj, dict):
        r: Dict[str, Any] = {}
        for k, v in obj.items():
            lower = k.lower()
            if lower in ("api_key", "apikey", "x-api-key", "x-client-id",
                         "token", "secret", "password", "key"):
                r[k] = MASK_SUFFIX
            elif lower.endswith("_id") or lower == "id":
                r[k] = _mask(str(v)) if isinstance(v, str) else v
            else:
                r[k] = _mask_payload(v, depth + 1)
        return r
    return str(obj)[:100]


def _pct(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    return sorted_vals[min(int(len(sorted_vals) * pct / 100.0), len(sorted_vals) - 1)]


def _build_headers(client_id: str, api_key: str) -> Dict[str, str]:
    return {"X-Client-ID": client_id, "X-API-Key": api_key,
            "Accept-Language": "en", "Content-Type": "application/json"}


def _fmt_iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


def _dt_tuple(day_str: str):
    t = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=PET)
    return t, t.replace(hour=23, minute=59, second=59)


def _orders_body(park_id: str, day: str, cursor: Optional[str] = None) -> dict:
    f, t = _dt_tuple(day)
    b = {"limit": 500, "query": {"park": {"id": park_id, "order": {
        "ended_at": {"from": _fmt_iso(f), "to": _fmt_iso(t)}, "statuses": ["complete"]}}}}
    if cursor:
        b["cursor"] = cursor
    return b


def _transactions_body(park_id: str, day: str, cursor: Optional[str] = None) -> dict:
    f, t = _dt_tuple(day)
    b = {"limit": 100, "query": {"park": {"id": park_id, "transaction": {
        "event_at": {"from": _fmt_iso(f), "to": _fmt_iso(t)}}}}}
    if cursor:
        b["cursor"] = cursor
    return b


def _drivers_body(park_id: str, limit: int, offset: int) -> dict:
    return {
        "query": {"park": {"id": park_id, "driver_profile": {
            "work_status": ["working", "not_working"]}}},
        "fields": {"driver_profile": ["id", "park_id", "created_date", "first_name",
            "last_name", "work_rule_id", "work_status", "employment_type",
            "has_contract_issue"],
            "current_status": ["status", "status_updated_at"],
            "car": ["id", "status", "category", "callsign", "brand", "model", "year", "number"],
            "account": ["id", "balance", "balance_limit", "currency", "last_transaction_date"],
            "park": ["id", "city", "name"]},
        "limit": limit, "offset": offset}


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
    client: httpx.AsyncClient, url: str, headers: dict, body: dict,
    sem: asyncio.Semaphore, park_id: str, park_lock: asyncio.Lock,
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
                    await _backoff(attempt); continue
                return None, last_elapsed, 0, "timeout"
            except Exception as exc:
                last_elapsed = round((time.perf_counter() - start) * 1000, 1)
                if attempt < max_retries:
                    await _backoff(attempt); continue
                msg = str(exc)[:200]
                for s in ((settings.YANGO_API_KEY or "").strip(),
                          (settings.YANGO_CLIENT_ID or "").strip()):
                    if s and len(s) > 4:
                        msg = msg.replace(s, MASK_SUFFIX)
                return None, last_elapsed, 0, msg

        elapsed = round((time.perf_counter() - start) * 1000, 1)
        if resp.status_code == 429:
            last_elapsed, last_status, last_err = elapsed, 429, "rate_limited"
            if attempt < max_retries:
                await asyncio.sleep(BACKOFF_429_SEC); continue
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
            await _backoff(attempt); continue
        try:
            return resp.json(), elapsed, resp.status_code, last_err
        except Exception:
            return None, elapsed, resp.status_code, last_err
    return None, last_elapsed, last_status or 0, last_err or "max_retries_exceeded"


async def _probe_endpoint(
    client: httpx.AsyncClient, url: str, headers: dict,
    body_fn, pagination: str,  # "cursor" | "offset"
    response_key: str, response_keys_alt: List[str],
    park_id: str, days: List[str],
    sem: asyncio.Semaphore, park_lock: asyncio.Lock,
    max_pages: int, max_retries: int, page_size: int,
    metrics: list, errors_list: list, payload_samples: list,
    checkpoint: dict, output_dir: str, dry_run: bool, name: str,
) -> dict:
    total_records, pages_fetched = 0, 0
    if dry_run:
        return {"endpoint": url, "dry_run": True, "days": len(days),
                "estimated_calls": len(days) * max_pages}

    if pagination == "offset":
        days_iter = ["N/A"]  # single iteration, no date loop
    else:
        days_iter = days

    offset = 0
    for day_str in days_iter:
        cursor = None
        day_pages = 0
        while day_pages < max_pages:
            ck = f"{name}_{day_str}_{day_pages}" if pagination == "cursor" else f"{name}_{pages_fetched}"
            if checkpoint.get("completed_pages", {}).get(ck):
                day_pages += 1
                if pagination == "offset":
                    pages_fetched += 1; offset += page_size
                continue

            if pagination == "offset":
                body = body_fn(park_id, page_size, offset)
            else:
                body = body_fn(park_id, day_str, cursor)

            data, elapsed, status, err = await _retry_fetch(
                client, url, headers, body, sem, park_id, park_lock, max_retries)
            metrics.append({"endpoint": name, "day": day_str, "page": day_pages + 1,
                           "elapsed_ms": elapsed, "status_code": status, "error": err})
            if err or status != 200:
                errors_list.append({"endpoint": name, "day": day_str,
                    "page": day_pages + 1, "status_code": status, "error": err,
                    "elapsed_ms": elapsed})
                if status == 429:
                    continue
                break
            if data and isinstance(data, dict):
                items = None
                for k in [response_key] + response_keys_alt:
                    items = data.get(k)
                    if items is not None:
                        break
                items = items or []
                total_records += len(items)
                if len(payload_samples) < 5 and items:
                    payload_samples.append({"endpoint": name, "day": day_str,
                        "page": day_pages + 1, "masked": _mask_payload(items[0])})
                next_cursor = data.get("cursor") or data.get("next_cursor")
                cursor = next_cursor if (next_cursor and items) else None
            else:
                cursor = None
            pages_fetched += 1; day_pages += 1
            if pagination == "offset":
                offset += page_size
            checkpoint.setdefault("completed_pages", {})[ck] = True
            _save_checkpoint(output_dir, checkpoint)
            if not cursor and pagination == "cursor":
                break
    return {"endpoint": name, "total_records": total_records, "pages_fetched": pages_fetched}


def _build_summary_md(config: dict, results: dict, metrics: list, errors: list,
                      start_time: float) -> str:
    elapsed = time.perf_counter() - start_time
    ok = [m for m in metrics if m.get("status_code") == 200 and m.get("error") is None]
    lats = sorted([m["elapsed_ms"] for m in ok])
    per_ep: Dict[str, list] = {}
    for m in ok:
        per_ep.setdefault(m["endpoint"], []).append(m["elapsed_ms"])
    err_n = len(errors)
    r429 = len([e for e in errors if e.get("status_code") == 429])
    pages = sum(r.get("pages_fetched", 0) for r in results.values())
    recs = sum(r.get("total_records", 0) for r in results.values())
    rpm = round(recs / (elapsed / 60.0), 1) if elapsed > 0 else 0
    h, m = int(elapsed // 3600), int((elapsed % 3600) // 60)

    out = [
        "# Yango Fleet API — Scale Probe Summary", "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Range:** {config.get('date_from')} -> {config.get('date_to')} ({config.get('days_count')}d)",
        f"**Park:** {config.get('park_id_masked')}",
        f"**Groups:** {', '.join(config.get('endpoint_groups', []))}",
        f"**Concurrency:** {config.get('max_concurrency')} (per-park: {config.get('max_concurrency_per_park')})",
        f"**Max pages/endpoint:** {config.get('max_pages_per_endpoint')}",
        f"**Sample only:** {config.get('sample_only')} | **Dry run:** {config.get('dry_run')}",
        "", "## Latency",
        f"- Requests: {len(metrics)} | Success: {len(ok)} | Errors: {err_n} | 429s: {r429}",
        f"- p50: {_pct(lats, 50):.1f}ms | p95: {_pct(lats, 95):.1f}ms | avg: {round(sum(lats)/len(lats),1) if lats else 0:.1f}ms",
        f"- Min: {lats[0] if lats else 0:.1f}ms | Max: {lats[-1] if lats else 0:.1f}ms",
        "", "## Throughput",
        f"- Pages: {pages} | Records: {recs} | Records/min: {rpm}",
        f"- Elapsed: {h}h {m}m {elapsed%60:.1f}s",
        "", "## Per-Endpoint",
    ]
    for ep_name in ["orders", "drivers", "transactions"]:
        ep = sorted(per_ep.get(ep_name, []))
        if not ep:
            out.append(f"- **{ep_name}**: no successes")
            continue
        r = results.get(ep_name, {})
        out.append(f"- **{ep_name}**: p50={_pct(ep, 50):.0f}ms p95={_pct(ep, 95):.0f}ms "
                   f"avg={sum(ep)/len(ep):.0f}ms pages={r.get('pages_fetched',0)} recs={r.get('total_records',0)}")
    out.extend(["", "## Errors"])
    if errors:
        cnt: Dict[str, int] = {}
        for e in errors:
            k = f"{e.get('endpoint')} {e.get('status_code')} {e.get('error')}"
            cnt[k] = cnt.get(k, 0) + 1
        for k, v in sorted(cnt.items()):
            out.append(f"- {k}: {v}")
    else:
        out.append("- None")
    return "\n".join(out)


def _build_metrics_json(config: dict, results: dict, metrics: list,
                        errors: list, start_time: float) -> dict:
    elapsed = time.perf_counter() - start_time
    ok = [m for m in metrics if m.get("status_code") == 200 and m.get("error") is None]
    lats = sorted([m["elapsed_ms"] for m in ok])
    per_ep = {}
    for ep_name in ["orders", "drivers", "transactions"]:
        ep_l = sorted([m["elapsed_ms"] for m in ok if m["endpoint"] == ep_name])
        per_ep[ep_name] = {"p50_ms": _pct(ep_l, 50), "p95_ms": _pct(ep_l, 95),
            "avg_ms": round(sum(ep_l)/len(ep_l), 1) if ep_l else 0,
            "min_ms": ep_l[0] if ep_l else 0, "max_ms": ep_l[-1] if ep_l else 0, "count": len(ep_l)}
    return {"probe_id": f"scale_probe_{config.get('date_from')}_{config.get('date_to')}",
        "generated_at": datetime.now(PET).isoformat(), "config": config,
        "latency": {"p50_ms": _pct(lats, 50), "p95_ms": _pct(lats, 95),
            "avg_ms": round(sum(lats)/len(lats), 1) if lats else 0,
            "min_ms": lats[0] if lats else 0, "max_ms": lats[-1] if lats else 0},
        "per_endpoint": per_ep,
        "counts": {"requests": len(metrics), "success": len(ok), "errors": len(errors),
            "rate_limits_429": len([e for e in errors if e.get("status_code") == 429]),
            "total_pages": sum(r.get("pages_fetched", 0) for r in results.values()),
            "total_records": sum(r.get("total_records", 0) for r in results.values())},
        "elapsed_total_seconds": round(elapsed, 1)}


def _write_csv(output_dir: str, filename: str, headers_row: list, rows: list) -> str:
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers_row)
        for row in rows:
            w.writerow(row)
    return path


async def run_scale_probe(park_id: str, date_from: str, date_to: str,
                          endpoint_groups: List[str], max_concurrency: int,
                          max_concurrency_per_park: int, max_pages_per_endpoint: int,
                          sample_only: bool, dry_run: bool, output_dir: str,
                          resume: bool) -> int:
    base_url = (settings.YANGO_API_BASE_URL or "").strip()
    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    if not settings.YANGO_API_ENABLED:
        print("ERROR: YANGO_API_ENABLED=false.", file=sys.stderr); return 1
    if not client_id or not api_key or not park_id:
        print("ERROR: missing credentials/park_id.", file=sys.stderr); return 1

    from_dt = datetime.strptime(date_from, "%Y-%m-%d")
    to_dt = datetime.strptime(date_to, "%Y-%m-%d")
    days = [(from_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range((to_dt - from_dt).days + 1)]

    headers = _build_headers(client_id, api_key)
    sem = asyncio.Semaphore(max(1, min(max_concurrency, max_concurrency_per_park)))
    park_lock = asyncio.Lock()
    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)
    max_retries = settings.YANGO_API_MAX_RETRIES

    checkpoint = _load_checkpoint(output_dir) if resume else {}
    os.makedirs(output_dir, exist_ok=True)
    config = {"park_id_masked": _mask(park_id), "date_from": date_from,
        "date_to": date_to, "days_count": len(days),
        "endpoint_groups": endpoint_groups, "max_concurrency": max_concurrency,
        "max_concurrency_per_park": max_concurrency_per_park,
        "max_pages_per_endpoint": max_pages_per_endpoint, "sample_only": sample_only,
        "dry_run": dry_run, "timezone": "America/Lima (UTC-5)"}
    checkpoint["config"] = config
    _save_checkpoint(output_dir, checkpoint)

    metrics, errors, payloads = [], [], []
    results = {}
    t0 = time.perf_counter()

    async with httpx.AsyncClient(timeout=timeout) as client:
        if "orders" in endpoint_groups:
            print(f"[scale_probe] orders  — {len(days)} day(s)")
            results["orders"] = await _probe_endpoint(
                client, f"{base_url.rstrip('/')}/v1/parks/orders/list", headers,
                _orders_body, "cursor", "orders", [],
                park_id, days, sem, park_lock, max_pages_per_endpoint, max_retries, 500,
                metrics, errors, payloads, checkpoint, output_dir, dry_run, "orders")
        if "drivers" in endpoint_groups:
            print(f"[scale_probe] drivers — probing")
            results["drivers"] = await _probe_endpoint(
                client, f"{base_url.rstrip('/')}/v1/parks/driver-profiles/list", headers,
                _drivers_body, "offset", "driver_profiles", [],
                park_id, days, sem, park_lock, max_pages_per_endpoint, max_retries, 100,
                metrics, errors, payloads, checkpoint, output_dir, dry_run, "drivers")
        if "transactions" in endpoint_groups:
            print(f"[scale_probe] transactions — {len(days)} day(s)")
            results["transactions"] = await _probe_endpoint(
                client, f"{base_url.rstrip('/')}/v2/parks/transactions/list", headers,
                _transactions_body, "cursor", "transactions", ["items"],
                park_id, days, sem, park_lock, max_pages_per_endpoint, max_retries, 100,
                metrics, errors, payloads, checkpoint, output_dir, dry_run, "transactions")

    if dry_run:
        print("\n[scale_probe] DRY RUN — no API calls.")
        print(json.dumps(results, indent=2, default=str, ensure_ascii=False))
        return 0

    md = _build_summary_md(config, results, metrics, errors, t0)
    mj = _build_metrics_json(config, results, metrics, errors, t0)

    paths = {
        "summary": os.path.join(output_dir, "scale_probe_summary.md"),
        "metrics": os.path.join(output_dir, "scale_probe_metrics.json"),
        "payloads": os.path.join(output_dir, "scale_probe_payload_samples.json"),
    }
    with open(paths["summary"], "w", encoding="utf-8") as f:
        f.write(md)
    with open(paths["metrics"], "w", encoding="utf-8") as f:
        json.dump(mj, f, indent=2, default=str, ensure_ascii=False)
    with open(paths["payloads"], "w", encoding="utf-8") as f:
        json.dump(payloads, f, indent=2, default=str, ensure_ascii=False)
    paths["errors_csv"] = _write_csv(output_dir, "scale_probe_errors.csv",
        ["endpoint", "day", "page", "status_code", "error", "elapsed_ms"],
        [[e.get("endpoint"), e.get("day"), e.get("page"),
          e.get("status_code"), e.get("error"), e.get("elapsed_ms")] for e in errors])
    paths["latency_csv"] = _write_csv(output_dir, "scale_probe_latency_by_endpoint.csv",
        ["endpoint", "day", "page", "elapsed_ms", "status_code", "error"],
        [[m.get("endpoint"), m.get("day"), m.get("page"),
          m.get("elapsed_ms"), m.get("status_code"), m.get("error") or ""] for m in metrics])

    pages = sum(r.get("pages_fetched", 0) for r in results.values())
    recs = sum(r.get("total_records", 0) for r in results.values())
    r429 = len([e for e in errors if e.get("status_code") == 429])
    print(f"\n[scale_probe] Done.")
    for k, v in paths.items():
        print(f"  {k}: {v}")
    print(f"  Pages: {pages} | Records: {recs} | Errors: {len(errors)} | 429s: {r429}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Scale Probe — Yango Fleet API benchmark")
    ap.add_argument("--park-id",
        default=(settings.YANGO_LIMA_PARK_ID or "").strip() or "08e20910d81d42658d4334d3f6d10ac0")
    ap.add_argument("--date-from", default="2026-06-01")
    ap.add_argument("--date-to", default="2026-06-03")
    ap.add_argument("--max-days", type=int, default=3)
    ap.add_argument("--max-concurrency", type=int, default=5)
    ap.add_argument("--max-concurrency-per-park", type=int, default=2)
    ap.add_argument("--endpoint-group", choices=["orders", "drivers", "transactions", "all"],
                    default="orders")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output-dir",
        default=os.path.join(_project_root(), "exports", "audits", "growth_api_probe", "scale_probe"))
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--sample-only", action="store_true", default=True)
    ap.add_argument("--no-sample-only", action="store_false", dest="sample_only")
    ap.add_argument("--max-pages-per-endpoint", type=int, default=3)
    args = ap.parse_args()

    try:
        fd = datetime.strptime(args.date_from, "%Y-%m-%d")
        td = datetime.strptime(args.date_to, "%Y-%m-%d")
    except ValueError:
        print("ERROR: dates must be YYYY-MM-DD", file=sys.stderr); return 1
    if (td - fd).days > args.max_days:
        print(f"ERROR: range exceeds --max-days={args.max_days}", file=sys.stderr); return 1
    if not settings.YANGO_API_ENABLED and not args.dry_run:
        print("WARNING: YANGO_API_ENABLED=false. Enabling --dry-run.", file=sys.stderr)
        args.dry_run = True

    groups = ["orders", "drivers", "transactions"] if args.endpoint_group == "all" else [args.endpoint_group]
    return asyncio.run(run_scale_probe(
        park_id=args.park_id, date_from=args.date_from, date_to=args.date_to,
        endpoint_groups=groups, max_concurrency=args.max_concurrency,
        max_concurrency_per_park=args.max_concurrency_per_park,
        max_pages_per_endpoint=args.max_pages_per_endpoint,
        sample_only=args.sample_only, dry_run=args.dry_run,
        output_dir=args.output_dir, resume=args.resume))


if __name__ == "__main__":
    raise SystemExit(main())
