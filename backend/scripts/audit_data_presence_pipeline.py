"""
OV2-CX.1D — Data Presence Reconciliation: trace entire pipeline for 2026-06-05.
"""
import json, os, sys
sys.path.insert(0, r"C:\cursor\controltower\controltower\backend")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "omniview_v2_data_recon")
os.makedirs(OUTPUT_DIR, exist_ok=True)

DATE = "2026-06-05"
SOURCE = "CT_TRIPS_2026"
GRAIN = "day"

print("=" * 60)
print(f"OV2-CX.1D Pipeline Audit: {SOURCE} / {GRAIN} / {DATE}")
print("=" * 60)

# ── T1: Source (DB directly) ──────────────────────────
print(f"\n[T1] Source: ops.real_business_slice_day_fact WHERE trip_date='{DATE}' AND country='peru' AND city='lima'")
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
with get_db() as c:
    cur = c.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT trip_date, business_slice_name, trips_completed, revenue_yego_final, active_drivers
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
          AND trip_date = %s
        ORDER BY business_slice_name
    """, (DATE,))
    source_rows = [dict(r) for r in cur.fetchall()]
    cur.close()

print(f"  SOURCE rows: {len(source_rows)}")
if source_rows:
    total_trips = sum(int(r.get("trips_completed", 0) or 0) for r in source_rows)
    total_rev = sum(float(r.get("revenue_yego_final", 0) or 0) for r in source_rows)
    print(f"  Total trips: {total_trips:,}")
    print(f"  Total revenue: {total_rev:,.2f}")
    for r in source_rows[:3]:
        print(f"    slice={r['business_slice_name']}, trips={r['trips_completed']}, rev={r['revenue_yego_final']}")
else:
    print("  *** SOURCE HAS 0 ROWS ***")

# ── T2: Repository ───────────────────────────────────
print(f"\n[T2] Repository: get_ct_matrix_data(grain='{GRAIN}', date_from='{DATE}', date_to='{DATE}')")
from app.repositories.omniview_v2_matrix_repository import get_ct_matrix_data
repo_status, repo_rows = get_ct_matrix_data(grain=GRAIN, date_from=DATE, date_to=DATE)
print(f"  REPO status: {repo_status}")
print(f"  REPO rows: {len(repo_rows)}")
for r in repo_rows[:3]:
    period = r.get("period_date", "?")
    trips = r.get("trips_completed", "?")
    print(f"    period={period}, slice={r.get('business_slice_name','?')}, trips={trips}")

# ── T3: ViewModel ────────────────────────────────────
print(f"\n[T3] ViewModel: build_matrix_response(source='{SOURCE}', grain='{GRAIN}', date_from='{DATE}', date_to='{DATE}')")
from app.services.omniview_v2_matrix_view_model_service import build_matrix_response
vm_resp = build_matrix_response(source_system=SOURCE, grain=GRAIN, date_from=DATE, date_to=DATE)
vm_d = vm_resp.to_dict()
vm_rows = vm_d.get("rows", [])
vm_cols = vm_d.get("columns", [])
vm_cells = vm_d.get("cells", [])
print(f"  VIEWMODEL rows: {len(vm_rows)}")
print(f"  VIEWMODEL columns: {len(vm_cols)}")
print(f"  VIEWMODEL cells: {len(vm_cells)}")
print(f"  VIEWMODEL canonical_ready: {vm_d.get('canonical_ready')}")
print(f"  VIEWMODEL metadata.row_count: {vm_d.get('metadata',{}).get('row_count','?')}")
print(f"  VIEWMODEL metadata.cell_count: {vm_d.get('metadata',{}).get('cell_count','?')}")
print(f"  VIEWMODEL metadata.coverage_pct: {vm_d.get('metadata',{}).get('coverage_pct','?')}")
print(f"  VIEWMODEL metadata.data_date: {vm_d.get('metadata',{}).get('data_date','?')}")
vm_warnings = [w.get("code","?") for w in vm_d.get("warnings", [])]
print(f"  VIEWMODEL warnings: {vm_warnings}")
for c in vm_cells[:3]:
    print(f"    cell: row={c.get('row_id','?')} col={c.get('period','?')} val={c.get('value')} status={c.get('cell_status','?')}")

# Save full response
with open(os.path.join(OUTPUT_DIR, "matrix_response_2026-06-05.json"), "w", encoding="utf-8") as f:
    json.dump(vm_d, f, indent=2, default=str, ensure_ascii=False)

# ── T4: Endpoint equivalent ──────────────────────────
print(f"\n[T4] Endpoint: /matrix?source_system={SOURCE}&grain={GRAIN}&date_from={DATE}&date_to={DATE}")
# This is the same as T3 since we call build_matrix_response directly
print(f"  ENDPOINT cells: {len(vm_cells)} (same as ViewModel)")

# ── T5: Classification ───────────────────────────────
print("\n" + "=" * 60)
print("CLASSIFICATION")
print("=" * 60)

src_ok = len(source_rows) > 0
repo_ok = len(repo_rows) > 0
vm_ok = len(vm_cells) > 0

print(f"  Source has data:    {'YES' if src_ok else 'NO'} ({len(source_rows)} rows)")
print(f"  Repository returns: {'YES' if repo_ok else 'NO'} ({len(repo_rows)} rows)")
print(f"  ViewModel produces: {'YES' if vm_ok else 'NO'} ({len(vm_cells)} cells)")

if not src_ok:
    classification = "SOURCE_EMPTY — no data in DB for this date"
elif not repo_ok:
    classification = "REPOSITORY_LOST_DATA — source has rows but repo returns empty"
elif not vm_ok:
    classification = "VIEWMODEL_LOST_DATA — repo has rows but viewmodel produces 0 cells"
else:
    classification = "BACKEND_OK — data flows correctly. Bug is in FRONTEND."

print(f"  Classification: {classification}")

print(f"\n[output] {OUTPUT_DIR}")
