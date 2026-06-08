#!/usr/bin/env python3
"""
OV2-H.1 — Endpoint Concurrency Audit (Light)
Probes OV2 endpoints with controlled low concurrency (1, 3, 5).
Measures success, timeout, connection errors, p50, p95, max.
DOES NOT use high concurrency. DOES NOT overload DB.

Output:
  backend/exports/audits/infrastructure_health/ov2_endpoint_concurrency.csv
  backend/exports/audits/infrastructure_health/ov2_endpoint_concurrency_summary.md
"""
from __future__ import annotations

import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

BASE_URL = os.environ.get("CT_BACKEND_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 15  # seconds — generous to avoid false positives

ENDPOINTS = [
    "/ops/omniview-v2/operating-date?source_system=CT_TRIPS_2026",
    "/ops/omniview-v2/matrix?source_system=CT_TRIPS_2026&grain=day",
    "/ops/omniview-v2/shell?source_system=CT_TRIPS_2026&grain=day",
]

CONCURRENCY_LEVELS = [1, 3, 5]
REQUESTS_PER_LEVEL = 15  # enough for reasonable percentiles

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "infrastructure_health",
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

TIMESTAMP = datetime.now(timezone.utc).isoformat()


def _percentile(sorted_vals: list, pct: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_vals) else f
    dk = k - f
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * dk


def probe_endpoint(url: str) -> dict:
    t0 = time.perf_counter()
    result = {
        "url": url,
        "success": False,
        "http_status": None,
        "response_ms": 0,
        "error": None,
    }
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        elapsed = (time.perf_counter() - t0) * 1000
        result["response_ms"] = round(elapsed, 1)
        result["http_status"] = resp.status_code
        result["success"] = 200 <= resp.status_code < 500
        if resp.status_code >= 500:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
        result["response_ms"] = REQUEST_TIMEOUT * 1000
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"connection_error: {str(e)[:200]}"
        result["response_ms"] = REQUEST_TIMEOUT * 1000
    except Exception as e:
        result["error"] = f"exception: {str(e)[:200]}"
        result["response_ms"] = REQUEST_TIMEOUT * 1000
    return result


def run_concurrency_test(endpoint_rel: str, concurrency: int, n_requests: int) -> list:
    url = f"{BASE_URL}{endpoint_rel}"
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(probe_endpoint, url) for _ in range(n_requests)]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def summarize(name: str, results: list) -> dict:
    total = len(results)
    success = sum(1 for r in results if r["success"])
    timeouts = sum(1 for r in results if r.get("error") == "timeout")
    conn_errors = sum(1 for r in results if (r.get("error") or "").startswith("connection_error"))
    failures = total - success
    response_times = sorted([r["response_ms"] for r in results])
    return {
        "endpoint": name,
        "total_requests": total,
        "successful": success,
        "timeouts": timeouts,
        "connection_errors": conn_errors,
        "other_failures": failures - timeouts - conn_errors,
        "p50_ms": round(_percentile(response_times, 50), 1),
        "p95_ms": round(_percentile(response_times, 95), 1),
        "max_ms": round(max(response_times), 1) if response_times else 0,
        "min_ms": round(min(response_times), 1) if response_times else 0,
    }


def main() -> int:
    print("[OV2-H.1] Endpoint Concurrency Audit (LIGHT — max 5 concurrent)")
    print(f"  BASE_URL={BASE_URL}")
    print(f"  Endpoints={len(ENDPOINTS)} Concurrency levels={CONCURRENCY_LEVELS}")
    print()

    csv_rows = []
    summaries = []

    for endpoint_rel in ENDPOINTS:
        endpoint_name = endpoint_rel.split("?")[0]
        for concurrency in CONCURRENCY_LEVELS:
            label = f"{endpoint_name} @ c={concurrency}"
            print(f"  Testing {label}...")
            results = run_concurrency_test(endpoint_rel, concurrency, REQUESTS_PER_LEVEL)
            summary = summarize(label, results)
            summary["concurrency"] = concurrency
            summaries.append(summary)
            for r in results:
                csv_rows.append({
                    "endpoint": label,
                    "concurrency": concurrency,
                    "success": r["success"],
                    "http_status": r.get("http_status", ""),
                    "response_ms": r["response_ms"],
                    "error": r.get("error", ""),
                })
            print(f"    success={summary['successful']}/{summary['total_requests']} "
                  f"p50={summary['p50_ms']}ms p95={summary['p95_ms']}ms max={summary['max_ms']}ms")

    # Write CSV
    csv_path = os.path.join(OUTPUT_DIR, "ov2_endpoint_concurrency.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "endpoint", "concurrency", "success", "http_status", "response_ms", "error"
        ])
        writer.writeheader()
        writer.writerows(csv_rows)

    # Write MD summary
    md_lines = [
        "# OV2 Endpoint Concurrency Audit Summary",
        "",
        f"**Generated:** {TIMESTAMP}",
        f"**Base URL:** {BASE_URL}",
        f"**Requests per test:** {REQUESTS_PER_LEVEL}",
        "",
        "## Summary Table",
        "",
        "| Endpoint | Conc | Success | Timeouts | Conn Errors | Other | p50 (ms) | p95 (ms) | Max (ms) |",
        "|----------|------|---------|----------|-------------|-------|----------|----------|----------|",
    ]
    for s in summaries:
        md_lines.append(
            f"| {s['endpoint']} | c={s['concurrency']} | {s['successful']}/{s['total_requests']} "
            f"| {s['timeouts']} | {s['connection_errors']} | {s['other_failures']} "
            f"| {s['p50_ms']} | {s['p95_ms']} | {s['max_ms']} |"
        )

    # Add PASS/FAIL per concurrency level
    md_lines += [
        "",
        "## Per-Concurrency Health",
        "",
    ]
    for concurrency in CONCURRENCY_LEVELS:
        level_summaries = [s for s in summaries if s["concurrency"] == concurrency]
        all_ok = all(s["successful"] == s["total_requests"] for s in level_summaries)
        status = "PASS" if all_ok else "FAIL"
        md_lines.append(f"### Concurrency {concurrency}: **{status}**")
        for s in level_summaries:
            md_lines.append(f"- {s['endpoint']}: {s['successful']}/{s['total_requests']} success, "
                            f"p50={s['p50_ms']}ms p95={s['p95_ms']}ms max={s['max_ms']}ms")
        md_lines.append("")

    md_lines += [
        "## GO/NO-GO Assessment",
        "",
    ]
    all_pass = all(
        s["successful"] == s["total_requests"] and s["connection_errors"] == 0
        for s in summaries
    )
    if all_pass:
        md_lines.append("**GO** — All endpoints respond correctly under controlled concurrency 1/3/5. No connection errors.")
    else:
        md_lines.append("**NO-GO** — Failures or connection errors detected. Review failed rows above.")

    md_path = os.path.join(OUTPUT_DIR, "ov2_endpoint_concurrency_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"\n  CSV: {csv_path}")
    print(f"  MD:  {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
