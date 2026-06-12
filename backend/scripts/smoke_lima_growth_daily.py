"""
LG-OPS-DAILY-1A — Daily Smoke Script
Validates all critical Lima Growth endpoints.
Usage: python scripts/smoke_lima_growth_daily.py [--url http://localhost:8001]
"""
import sys
import time
import urllib.request
import urllib.error
import json


BASE = "http://localhost:8001"
TIMEOUT = 30

ENDPOINTS = [
    ("health", "/health", 5),
    ("growth/health", "/growth/health", 30),
    ("growth/freshness", "/growth/freshness", 30),
    ("growth/operability", "/growth/operability", 30),
    ("operational-summary", "/yego-lima-growth/operational-summary?date=2026-06-12", 15),
    ("programs/summary", "/yego-lima-growth/programs/summary?date=2026-06-12", 15),
    ("taxonomy/summary", "/yego-lima-growth/taxonomy/summary?date=2026-06-10", 15),
    ("movement-analytics/stats", "/yego-lima-growth/movement-analytics/stats", 15),
    ("rna-priority/summary", "/yego-lima-growth/rna-priority/summary", 15),
    ("rna-pilot/summary", "/yego-lima-growth/rna-pilot/summary", 15),
    ("effectiveness/summary", "/yego-lima-growth/effectiveness/summary", 15),
    ("export/options", "/yego-lima-growth/export/options", 10),
]

def smoke(base_url: str):
    results = []
    overall = "PASS"

    for label, path, timeout in ENDPOINTS:
        url = f"{base_url}{path}"
        start = time.time()
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=timeout)
            elapsed = round((time.time() - start) * 1000)
            body = resp.read().decode("utf-8", errors="replace")
            code = resp.status
            size = len(body)
            if code == 200:
                status = "PASS"
            else:
                status = f"WARNING ({code})"
                overall = "WARNING"
            results.append(f"  [{status}] {label}  {elapsed}ms  {size}c")
        except Exception as e:
            elapsed = round((time.time() - start) * 1000)
            msg = str(e)[:100]
            overall = "FAIL"
            results.append(f"  [FAIL] {label}  {elapsed}ms  {msg}")

    print(f"\nLIMA GROWTH DAILY SMOKE — {time.strftime('%Y-%m-%d %H:%M')}")
    print(f"Base URL: {base_url}")
    print(f"Overall: {overall}")
    print("-" * 60)
    for r in results:
        print(r)
    print("-" * 60)
    return overall


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("--url"):
        BASE = sys.argv[1].split("=", 1)[1] if "=" in sys.argv[1] else sys.argv[2]
    result = smoke(BASE)
    if result == "FAIL":
        sys.exit(1)
