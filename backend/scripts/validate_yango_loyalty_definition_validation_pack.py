#!/usr/bin/env python3
"""QA: Yango Loyalty Definition Validation Pack — Final Guardrail Check"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from app.services.yango_loyalty_performance_service import get_loyalty_performance
from app.services.yango_loyalty_definition_service import get_validation_pack, preview_all_sets

init_db_pool()
P=0;F=0;W=0
def c(l,v,d=""):
    global P,F
    if v:P+=1;print(f"  [PASS] {l}")
    else:F+=1;print(f"  [FAIL] {l} -- {d}")
def w(l,d=""):
    global W;W+=1;print(f"  [WARN] {l} -- {d}")

print("="*70)
print("QA: Definition Validation Pack")
print("="*70)

# Registry
with get_db() as conn:
    cur=conn.cursor()
    for t in ["yango_loyalty_source_registry","yango_loyalty_metric_definition_sets",
              "yango_loyalty_metric_rules","yango_loyalty_official_reconciliation_reference"]:
        cur.execute(f"SELECT 1 FROM information_schema.tables WHERE table_schema='ops' AND table_name='{t}'")
        c(f"Table {t} exists", bool(cur.fetchone()))

    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_official_reconciliation_reference")
    c("3 April ref rows", cur.fetchone()[0]==3)

    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_metric_definition_sets")
    c("Has definition sets", cur.fetchone()[0]>=3)

    cur.execute("SELECT COUNT(*) FROM ops.yango_loyalty_metric_definition_sets WHERE status='active'")
    c("No active definition set", cur.fetchone()[0]==0)

# Scoring guardrail
perf = get_loyalty_performance(month="2026-04",country="peru")
c("scoring = blocked_pending_yango_definition_validation",
  perf["scoring_status"]=="blocked_pending_yango_definition_validation",
  f"got {perf['scoring_status']}")
c("performance_category = null", perf["summary"]["performance_category"] is None)
c("SH drift generates warning", "SH_drift_13pct" in str(perf.get("reconciliation",{}).get("guardrail_flags",[])))
c("N+R drift blocks scoring", "NR_drift" in str(perf.get("reconciliation",{}).get("guardrail_flags",[])))

# N+R diff check
preview = preview_all_sets()
hybrid = next((p for p in preview["previews"] if p["definition_set_id"]=="hybrid_ct_default"), {})
nr_drift = hybrid.get("nr_diff_pct",0)
c(f"N+R drift >10% blocks scoring ({nr_drift:.0f}%)", nr_drift > 10 or hybrid.get("new_plus_reactivated",0)==0)

# Validation pack endpoint
vp = get_validation_pack()
c("Validation pack responds", isinstance(vp, dict))
c("Validation pack has previews", len(vp.get("previews",[]))>0)
c("Validation pack has pending_questions", len(vp.get("pending_questions",[]))>=4)
c("Validation pack has risks", len(vp.get("risks",[]))>=2)
c("scoring_allowed = false", vp.get("scoring_allowed")==False)
c("recommendation present", bool(vp.get("recommendation")))

# Markdown doc exists
doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "docs","yango_loyalty","YANGO_LOYALTY_NR_DEFINITION_VALIDATION_PACK.md")
c("Validation pack markdown exists", os.path.exists(doc_path))
if os.path.exists(doc_path):
    with open(doc_path, encoding='utf-8') as f:
        content = f.read()
    c("Doc contains Preguntas", "Preguntas Exactas" in content)
    c("Doc contains NO-GO", "NO-GO" in content)
    c("Doc contains reference values", "5,601" in content and "357,000" in content and "1,064" in content)

# Provinces still blocked
for cn in ["trujillo","arequipa"]:
    r = get_loyalty_performance(month="2026-04",country="peru",city=cn)
    c(f"{cn} not_available", r["freshness_status"]=="not_available")

# Engine isolation
svc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "app","services","yango_loyalty_performance_service.py")
with open(svc, encoding='utf-8') as f:
    src=f.read()
c("No ForecastEngine", "ForecastEngine" not in src)
c("No SuggestionEngine", "SuggestionEngine" not in src)
c("No DecisionEngine", "DecisionEngine" not in src)
c("No ActionEngine", "ActionEngine" not in src)

print(f"\n{'='*70}")
print(f"RESULTS: {P} PASS | {F} FAIL | {W} WARN")
print(f"VERDICT: {'GO' if F==0 else 'NO-GO'}")
sys.exit(0 if F==0 else 1)
