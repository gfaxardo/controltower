import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.omniview_v2_plan_real_service import build_monthly_plan_real_matrix

r = build_monthly_plan_real_matrix("peru", "lima", "2026-01-01", None, "revenue")
d = r.to_dict()

print(f"Matrix: {d['matrix_id']} grain={d['grain']}")
print(f"Rows: {d['metadata']['row_count']} Cols: {d['metadata']['column_count']} Cells: {d['metadata']['cell_count']}")

cells = d["cells"]
statuses = {}
for c in cells:
    s = c.get("comparison_status", "unknown")
    statuses[s] = statuses.get(s, 0) + 1
print(f"\nStatus distribution:")
for s, n in sorted(statuses.items()):
    print(f"  {s}: {n}")

print(f"\nSample cells:")
for c in cells[:5]:
    print(f"  row={c['row_id']} col={c['column_id']} val={c['value']} formatted={c['formatted_value']} status={c.get('comparison_status')} gap={c.get('delta_pct')}")

# Also dump first 3 raw rows from the repository
from app.repositories.omniview_v2_plan_real_repository import get_monthly_plan_real
raw = get_monthly_plan_real("peru", "lima", "2026-01-01", None, "revenue")
print(f"\nRaw repo rows: {len(raw)}")
for r in raw[:5]:
    print(f"  period={r['period']} slice={r['business_slice_name']} plan={r['plan_value']} real={r['real_value']} status={r['status']}")
