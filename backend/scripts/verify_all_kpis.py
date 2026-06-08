import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.omniview_v2_plan_real_service import build_monthly_plan_real_matrix

for metric in ["trips", "revenue", "active_drivers", "avg_ticket", "trips_per_driver"]:
    r = build_monthly_plan_real_matrix("peru", "lima", "2026-01-01", None, metric)
    d = r.to_dict()
    cells = d["cells"]
    statuses = {}
    for c in cells:
        s = c.get("comparison_status", "?")
        statuses[s] = statuses.get(s, 0) + 1
    on_track = statuses.get("ON_TRACK", 0)
    watch = statuses.get("WATCH", 0)
    off = statuses.get("OFF_TRACK", 0)
    no_plan = statuses.get("NO_PLAN", 0)
    no_real = statuses.get("NO_REAL", 0)
    total = len(cells)
    print(f"{metric:20s} cells={total:3d} ON_TRACK={on_track:2d} WATCH={watch:2d} OFF_TRACK={off:2d} NO_PLAN={no_plan:2d} NO_REAL={no_real:2d}")
