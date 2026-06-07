"""
OV2-CX.4 — Comprehensive Serving Trace & Bottleneck Analysis
"""
import json, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SOURCE = "CT_TRIPS_2026"
GRAIN = "day"
DATE = "2026-06-05"

def ms(elapsed):
    return int(elapsed * 1000)

now = time.perf_counter

print("=" * 70)
print(f"OV2-CX.4 TRACE: {SOURCE} / {GRAIN} / {DATE}")
print("=" * 70)

# ═══ SHELL SNAPSHOT ═══
print("\n--- SHELL SNAPSHOT ---")
t_total = now()

t0 = now()
from app.services.omniview_v2_snapshot_service import get_served_payload
snap = get_served_payload(SOURCE, GRAIN, DATE, "shell")
snap_ms = ms(now() - t0)

t_db = now()
from app.repositories.omniview_v2_snapshot_repository import get_snapshot
snap_raw = get_snapshot(SOURCE, GRAIN, DATE, "shell")
db_ms = ms(now() - t_db)

t_json = now()
if snap_raw:
    p = snap_raw.get("payload", {})
    if isinstance(p, str):
        json.loads(p)
json_ms = ms(now() - t_json)

t_meta = now()
if isinstance(snap, dict):
    snap["metadata"] = snap.get("metadata", {})
meta_ms = ms(now() - t_meta)

t_ser = now()
if snap:
    json.dumps(snap, default=str)
ser_ms = ms(now() - t_ser)

shell_total = ms(now() - t_total)
print(f"  get_served_payload: {snap_ms}ms")
print(f"  get_snapshot (DB):  {db_ms}ms")
print(f"  JSON parse:         {json_ms}ms")
print(f"  Metadata inject:    {meta_ms}ms")
print(f"  Response serialize: {ser_ms}ms")
print(f"  TOTAL:              {shell_total}ms")

shell_j = json.dumps(snap, default=str, ensure_ascii=False) if snap else "{}"
print(f"  Payload size:       {len(shell_j):,} bytes")
print(f"  Sections:           {len(snap.get('sections', [])) if snap else 0}")

# ═══ MATRIX SNAPSHOT ═══
print("\n--- MATRIX SNAPSHOT ---")
t_total_m = now()

t0 = now()
snap_m = get_served_payload(SOURCE, GRAIN, DATE, "matrix")
m_snap_ms = ms(now() - t0)

t_db_m = now()
snap_raw_m = get_snapshot(SOURCE, GRAIN, DATE, "matrix")
m_db_ms = ms(now() - t_db_m)

m_total = ms(now() - t_total_m)
print(f"  get_served_payload: {m_snap_ms}ms")
print(f"  get_snapshot (DB):  {m_db_ms}ms")
print(f"  TOTAL:              {m_total}ms")

matrix_j = json.dumps(snap_m, default=str, ensure_ascii=False) if snap_m else "{}"
print(f"  Payload size:       {len(matrix_j):,} bytes")
print(f"  Cells:              {len(snap_m.get('cells', [])) if snap_m else 0}")

# ═══ RUNTIME COMPARISON ═══
print("\n--- RUNTIME (no snapshot) ---")
t0 = now()
from app.services.omniview_v2_matrix_view_model_service import build_matrix_response
build_matrix_response(SOURCE, GRAIN, DATE, DATE)
print(f"  matrix runtime: {ms(now() - t0)}ms")

# ═══ DB PLAN ═══
print("\n--- DB PLAN ---")
from app.db.connection import get_db
with get_db() as c:
    cur = c.cursor()
    cur.execute("""
        EXPLAIN ANALYZE
        SELECT * FROM ops.omniview_v2_serving_snapshot
        WHERE source_system='CT_TRIPS_2026' AND grain='day'
          AND operating_date='2026-06-05' AND payload_type='shell'
          AND status='READY'
        ORDER BY generated_at DESC LIMIT 1
    """)
    for r in cur.fetchall():
        print(f"  {r[0][:300]}")
    cur.close()

# ═══ SNAPSHOT PURITY ═══
print("\n--- SNAPSHOT PURITY ---")
if snap:
    print(f"  source_system:  {snap.get('source_system')}")
    print(f"  canonical_ready:{snap.get('canonical_ready')}")
    print(f"  sections:       {len(snap.get('sections', []))}")
    print(f"  served_from:    {snap.get('metadata', {}).get('served_from_snapshot')}")
    print(f"  snapshot_at:    {snap.get('metadata', {}).get('snapshot_generated_at', 'N/A')[:30]}")

# ═══ BOTTLENECKS ═══
print("\n--- BOTTLENECKS ---")
items = [
    ("DB query", db_ms),
    ("JSON deserialize", json_ms),
    ("Response serialize", ser_ms),
    ("Metadata injection", meta_ms),
]
items.sort(key=lambda x: -x[1])
for i, (name, n) in enumerate(items):
    pct = (n / shell_total * 100) if shell_total > 0 else 0
    print(f"  {i+1}. {name}: {n}ms ({pct:.0f}%)")
unaccounted = shell_total - sum(m for _, m in items)
print(f"  Unaccounted: {unaccounted}ms")

print("\nDone.")
