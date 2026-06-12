"""
LG-INFRA-R3.0F — Yango Orders Recovery + Cascade Freshness
Phase 1-2: Root cause audit + live ingestion attempt
"""
import sys, os, json, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

print("=" * 65)
print("R3.0F — YANGO ORDERS ROOT CAUSE AUDIT")
print("=" * 65)

# ═══ PHASE 1: ROOT CAUSE ═══
print("\n1. RAW ORDERS STATUS")
cur.execute("SELECT COUNT(*), MIN(api_fetched_at), MAX(api_fetched_at) FROM raw_yango.orders_raw")
r = cur.fetchone()
print(f"   raw_yango.orders_raw: {r[0]} rows, min_fetch={r[1]}, max_fetch={r[2]}")

# Check ingestion runs
cur.execute("SELECT COUNT(*), MAX(started_at), MAX(heartbeat_at) FROM raw_yango.api_ingestion_run")
r = cur.fetchone()
print(f"   ingestion_runs: {r[0]}, latest_started={r[1]}, latest_heartbeat={r[2]}")

cur.execute("SELECT status, COUNT(*) FROM raw_yango.api_ingestion_run GROUP BY status")
for r in cur.fetchall():
    print(f"   runs status={r[0]}: {r[1]}")

cur.execute("SELECT endpoint_group, status, started_at, finished_at, records_fetched FROM raw_yango.api_ingestion_run ORDER BY started_at DESC LIMIT 5")
for r in cur.fetchall():
    print(f"   run: endpoint={r[0]}, status={r[1]}, started={r[2]}, fetched={r[3]}")

# Check normalized orders
cur.execute("SELECT COUNT(*), MIN(ended_at), MAX(ended_at) FROM growth.yango_lima_orders_raw")
r = cur.fetchone()
print(f"\n2. NORMALIZED ORDERS")
print(f"   growth.yango_lima_orders_raw: {r[0]} rows, min={r[1]}, max={r[2]}")

cur.execute("SELECT DATE(ended_at) as d, COUNT(*) FROM growth.yango_lima_orders_raw GROUP BY d ORDER BY d DESC LIMIT 10")
print(f"   orders by date:")
for r in cur.fetchall():
    print(f"     {r[0]}: {r[1]} orders")

# Check for ingestion errors
try:
    cur.execute("SELECT COUNT(*), MAX(error_message) FROM raw_yango.ingestion_errors")
    r = cur.fetchone()
    print(f"\n3. INGESTION ERRORS: {r[0]}")
except:
    print(f"\n3. INGESTION ERRORS: table not found")

# ROOT CAUSE ANALYSIS
print(f"\n4. ROOT CAUSE ANALYSIS")
print(f"""
   Observations:
   - raw_yango.orders_raw has 11,087 rows (raw API data exists)
   - growth.yango_lima_orders_raw has 237 rows (normalized, only 06-01)
   - Last ingestion run heartbeat: (see above)
   - There's a gap between raw and normalized counts
   
   Most likely cause:
   A) Yango API ingestion stopped after 06-01 (no new raw data fetched)
      OR
   B) Normalization step (upsert_raw_orders) not running
      OR
   C) API rate limit or auth issue
      OR
   D) Pipeline step that feeds orders_raw is dead/skipped
   
   Next: Attempt live ingestion via lab endpoint
""")

cur.close()
conn.close()

# ═══ PHASE 2: ATTEMPT INGESTION ═══
print("=" * 65)
print("PHASE 2 — ATTEMPTING LIVE INGESTION")
print("=" * 65)

import requests

try:
    resp = requests.post(
        "http://localhost:8000/yego-lima-growth/lab/capture-orders-range",
        json={"from": "2026-06-02T00:00:00", "to": "2026-06-07T23:59:59", "max_pages": 5},
        timeout=120
    )
    result = resp.json()
    print(f"   Status: {resp.status_code}")
    print(f"   Result: {json.dumps(result, indent=2, default=str)[:800]}")
except requests.exceptions.Timeout:
    print("   TIMEOUT - API call taking too long (normal for Yango ingestion)")
except Exception as e:
    print(f"   ERROR: {e}")
