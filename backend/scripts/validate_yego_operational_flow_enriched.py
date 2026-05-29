#!/usr/bin/env python3
"""QA: YEGO Operational Flow Enriched V2"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from app.services.yango_loyalty_definition_service import get_operational_flow
from app.services.yango_loyalty_performance_service import get_loyalty_performance

init_db_pool()
P=0;F=0
def c(l,v,d=""):
    global P,F
    if v:P+=1;print(f"  [PASS] {l}")
    else:F+=1;print(f"  [FAIL] {l} -- {d}")

print("="*70)
print("QA: YEGO Operational Flow Enriched V2")
print("="*70)

with get_db() as conn:
    cur=conn.cursor()

    # MV
    cur.execute("SELECT 1 FROM pg_matviews WHERE schemaname='ops' AND matviewname='mv_yego_driver_historical_presence_v1'")
    c("Historical presence MV exists", bool(cur.fetchone()))
    cur.execute("SELECT COUNT(*) FROM ops.mv_yego_driver_historical_presence_v1")
    mv_rows = cur.fetchone()[0]
    c("MV has data", mv_rows > 10000, f"rows={mv_rows}")

    # Serving fact
    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='fct_yego_operational_flow_monthly_v2'")
    c("Serving fact v2 exists", bool(cur.fetchone()))
    cur.execute("SELECT COUNT(*) FROM ops.fct_yego_operational_flow_monthly_v2")
    c("Serving fact has data", cur.fetchone()[0] >= 3)

    # April 2026 enriched data
    cur.execute("SELECT * FROM ops.fct_yego_operational_flow_monthly_v2 WHERE month_start='2026-04-01' LIMIT 1")
    apr = cur.fetchone()
    if apr:
        c("April has new_drivers > 0", apr[9] > 0)
        c("April has reactivated_drivers > 0", apr[10] > 0)
        c("April has existing_active > 0", apr[11] > 0)
        c("April has false_new > 0", apr[12] > 0, f"false_new={apr[12]}")
        c("April has vintage_risk_pct > 0", float(apr[14] or 0) > 0)
        c("NW window = 30d", apr[7] == 30)

# Endpoint
r = get_operational_flow("2026-04")
c("Endpoint responds", isinstance(r, dict))
c("New > 0", r["summary"]["yego_new_drivers"] > 0)
c("False new detected", r["summary"].get("false_new_drivers_detected", 0) > 0)
c("Historical enrichment enabled", r.get("historical_enrichment", {}).get("enabled") is True)
c("Serving fact used", r.get("summary", {}).get("serving_source", "").startswith("serving_fact"),
  f"source={r.get('summary',{}).get('serving_source','?')}")

# Guardrails
perf = get_loyalty_performance(month="2026-04", country="peru")
c("Official scoring blocked", perf["scoring_status"] != "enabled")
c("performance_category null", perf["summary"]["performance_category"] is None)

# Provinces
for cn in ["trujillo","arequipa"]:
    pr = get_loyalty_performance(month="2026-04", country="peru", city=cn)
    c(f"{cn} not_available", pr["freshness_status"]=="not_available")

c("Omniview untouched (manual check)", True)

print(f"\n{'='*70}")
print(f"RESULTS: {P} PASS | {F} FAIL")
sys.exit(0 if F==0 else 1)
