#!/usr/bin/env python3
"""QA: Yango Loyalty Metric Definition Registry"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from app.services.yango_loyalty_definition_service import preview_all_sets, get_sources, get_definition_sets
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
print("QA: Metric Definition Registry")
print("="*70)

with get_db() as conn:
    cur=conn.cursor()

    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='yango_loyalty_source_registry'")
    c("source_registry exists", bool(cur.fetchone()))

    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='yango_loyalty_metric_definition_sets'")
    c("metric_definition_sets exists", bool(cur.fetchone()))

    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='yango_loyalty_metric_rules'")
    c("metric_rules exists", bool(cur.fetchone()))

    cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='yango_loyalty_official_reconciliation_reference'")
    c("official_reconciliation_reference exists", bool(cur.fetchone()))

    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_source_registry")
    c("sources populated", cur.fetchone()[0] >= 5)

    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_metric_definition_sets")
    c(">=3 definition sets", cur.fetchone()[0] >= 3)

    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_metric_rules")
    c(">=15 metric rules", cur.fetchone()[0] >= 15)

    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_official_reconciliation_reference")
    c("3 April reference rows", cur.fetchone()[0] == 3)

    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_metric_definition_sets WHERE status='active'")
    c("No definition set active automatically", cur.fetchone()[0] == 0)

# Preview
r = preview_all_sets()
c("Preview returns dict", isinstance(r, dict))
c("Preview has 5 previews", len(r.get("previews",[])) >= 5)
for p in r["previews"]:
    c(f"Set {p['definition_set_id']} has AD", p["active_drivers"] is not None)
    c(f"Set {p['definition_set_id']} has SH", p["supply_hours"] > 0)
    c(f"Set {p['definition_set_id']} has N+R", p["new_plus_reactivated"] is not None)
    break

# Performance endpoint
perf = get_loyalty_performance(month="2026-04", country="peru")
c("Scoring blocked", perf["scoring_status"] == "blocked_pending_reconciliation")
c("No performance_category", perf["summary"]["performance_category"] is None)

# Provinces
for cn in ["trujillo","arequipa"]:
    pr = get_loyalty_performance(month="2026-04", country="peru", city=cn)
    c(f"{cn} not_available", pr["freshness_status"]=="not_available")

# Engine isolation
svc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "app","services","yango_loyalty_definition_service.py")
try:
    with open(svc_path, encoding='utf-8') as f:
        src=f.read()
    c("No ForecastEngine", "Forecast" not in src or "NO Forecast" in src)
    c("No SuggestionEngine", "Suggestion" not in src or "NO Suggestion" in src)
except: pass

print(f"\n{'='*70}")
print(f"RESULTS: {P} PASS | {F} FAIL | {W} WARN")
print(f"VERDICT: {'GO' if F==0 else 'NO-GO'}")
sys.exit(0 if F==0 else 1)
