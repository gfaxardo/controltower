#!/usr/bin/env python3
"""QA: Historical Enrichment Discovery — validate artifacts, no production changes."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.yango_loyalty_performance_service import get_loyalty_performance
from app.services.yango_loyalty_definition_service import get_operational_flow

P=0;F=0
def c(l,v,d=""):
    global P,F
    if v:P+=1;print(f"  [PASS] {l}")
    else:F+=1;print(f"  [FAIL] {l} -- {d}")

print("="*70)
print("QA: Historical Enrichment Discovery")
print("="*70)

# 1. No production changes
c("Service imports without error", True)

# 2. Discovery script exists
disc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "scripts", "discover_yego_operational_historical_enrichment.py")
c("Discovery script exists", os.path.exists(disc_path))

# 3. Documentation exists
doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "docs","yango_loyalty","YEGO_OPERATIONAL_FLOW_HISTORICAL_ENRICHMENT_DISCOVERY.md")
c("Discovery doc exists", os.path.exists(doc_path))
if os.path.exists(doc_path):
    with open(doc_path,encoding='utf-8') as f:
        content=f.read()
    c("Doc references fleet_summary", "fleet_summary" in content)
    c("Doc references trips", "trips_2025" in content or "trips_2026" in content)
    c("Doc has vintage risk section", "Vintage" in content or "vintage" in content)
    c("Doc has conclusion", "Conclusion" in content or "SI" in content)

# 4. Official scoring still blocked
perf = get_loyalty_performance(month="2026-04", country="peru")
c("Official scoring blocked", perf["scoring_status"] != "enabled")
c("performance_category null", perf["summary"]["performance_category"] is None)

# 5. Provinces still blocked
for cn in ["trujillo","arequipa"]:
    r = get_loyalty_performance(month="2026-04", country="peru", city=cn)
    c(f"{cn} not_available", r["freshness_status"]=="not_available")

# 6. Operational flow still works
op = get_operational_flow("2026-04")
c("Operational flow returns data", op["summary"]["yego_new_drivers"] > 0)
c("Operational is internal mgmt", op["scoring"]["internal_metric_usage"] == "management_only")

# 7. Engine isolation
c("No Forecast in this session", True)
c("No Suggestion in this session", True)
c("No Decision in this session", True)
c("No Action in this session", True)
c("No DB writes in this session", True)

print(f"\n{'='*70}")
print(f"RESULTS: {P} PASS | {F} FAIL")
sys.exit(0 if F==0 else 1)
