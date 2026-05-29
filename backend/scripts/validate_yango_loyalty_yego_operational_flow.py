#!/usr/bin/env python3
"""QA: YEGO Operational Flow Internal KPI"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from app.services.yango_loyalty_definition_service import get_operational_flow
from app.services.yango_loyalty_performance_service import get_loyalty_performance

init_db_pool()
P=0;F=0;W=0
def c(l,v,d=""):
    global P,F
    if v:P+=1;print(f"  [PASS] {l}")
    else:F+=1;print(f"  [FAIL] {l} -- {d}")
def w(l,d=""):
    global W;W+=1;print(f"  [WARN] {l} -- {d}")

print("="*70)
print("QA: YEGO Operational Flow")
print("="*70)

with get_db() as conn:
    cur=conn.cursor()
    cur.execute("SELECT 1 FROM ops.yango_loyalty_metric_definition_sets WHERE metric_universe='yego_operational'")
    c("yego_operational universe exists", bool(cur.fetchone()))
    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_metric_rules WHERE metric_universe='yego_operational'")
    c("yego_operational rules exist", cur.fetchone()[0]>=15)
    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_metric_definition_sets WHERE metric_universe='yego_operational'")
    c("5 yego def sets", cur.fetchone()[0]>=5)
    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_metric_definition_sets WHERE status='active' AND metric_universe='yego_operational'")
    c("No active yego def set", cur.fetchone()[0]==0)

# Operational flow
r = get_operational_flow("2026-04")
c("Endpoint responds", isinstance(r, dict))
c("Has yego_new_drivers", r["summary"]["yego_new_drivers"] > 0, f"got {r['summary']['yego_new_drivers']}")
c("Has yego_reactivated_drivers", r["summary"]["yego_reactivated_drivers"] is not None)
c("Split available", r["summary"]["split_available"] == True)
c("Not official comparable", r["scope"]["official_comparable"] == False)
c("Internal management", r["scoring"]["internal_metric_usage"] == "management_only")

# Official scoring still blocked
perf = get_loyalty_performance(month="2026-04", country="peru")
c("Official scoring blocked", perf["scoring_status"] != "enabled")
c("Official category null", perf["summary"]["performance_category"] is None)
c("Not using internal metric for official",
  "yego_operational" not in str(perf.get("summary","")))

# Provinces
for cn in ["trujillo","arequipa"]:
    pr = get_loyalty_performance(month="2026-04", country="peru", city=cn)
    c(f"{cn} not_available", pr["freshness_status"]=="not_available")

# Engine
svc=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"app","services","yango_loyalty_definition_service.py")
with open(svc,encoding='utf-8') as f:
    src=f.read()
c("No Forecast", "ForecastEngine" not in src)
c("No Suggestion", "SuggestionEngine" not in src)

print(f"\n{'='*70}")
print(f"RESULTS: {P} PASS | {F} FAIL | {W} WARN")
sys.exit(0 if F==0 else 1)
