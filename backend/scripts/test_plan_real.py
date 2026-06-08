import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.omniview_v2_plan_real_service import build_monthly_plan_real_matrix

r = build_monthly_plan_real_matrix("peru", "lima", "2026-01-01", None, "trips")
d = r.to_dict()

print(f"rows={d['metadata']['row_count']} cols={d['metadata']['column_count']} cells={d['metadata']['cell_count']}")

statuses = {}
for c in d["cells"]:
    s = c.get("comparison_status", "?")
    statuses[s] = statuses.get(s, 0) + 1
for s, n in sorted(statuses.items()):
    print(f"  {s}: {n}")

on_track = [c for c in d["cells"] if c.get("comparison_status") == "ON_TRACK"]
watch = [c for c in d["cells"] if c.get("comparison_status") == "WATCH"]
if on_track:
    print(f"\nON_TRACK sample ({len(on_track)} total):")
    for c in on_track[:5]:
        print(f"  row={c['row_id']} col={c['column_id']} val={c['value']} gap={c.get('delta_pct')}%")
if watch:
    print(f"\nWATCH sample ({len(watch)} total):")
    for c in watch[:3]:
        print(f"  row={c['row_id']} col={c['column_id']} val={c['value']} gap={c.get('delta_pct')}%")

# Also test other metrics
for metric in ["revenue", "active_drivers", "avg_ticket"]:
    r2 = build_monthly_plan_real_matrix("peru", "lima", "2026-01-01", None, metric)
    d2 = r2.to_dict()
    non_plan = [c for c in d2["cells"] if c.get("comparison_status") not in ("NO_PLAN", "NO_REAL")]
    print(f"\n{metric}: cells={d2['metadata']['cell_count']} matched={len(non_plan)}")
