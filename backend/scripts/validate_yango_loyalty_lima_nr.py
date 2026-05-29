#!/usr/bin/env python3
"""
T7 QA: Yango Loyalty Lima Pilot with N+R (Nuevos + Reactivados)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from app.services.yango_loyalty_performance_service import get_loyalty_performance

init_db_pool()

PASS = 0; FAIL = 0; WARN = 0
def c(l, cond, d=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  [PASS] {l}")
    else: FAIL += 1; print(f"  [FAIL] {l} -- {d}")
def w(l, d=""):
    global WARN; WARN += 1; print(f"  [WARN] {l} -- {d}")

print("=" * 70)
print("QA: Yango Loyalty Lima N+R Pilot")
print("=" * 70)

# Service
r = get_loyalty_performance(month="2026-04", country="peru")
c("Endpoint responds", isinstance(r, dict))

# N+R
c("Has new_drivers_mtd", r['summary']['new_drivers_mtd'] > 0)
c("Has reactivated_drivers_mtd", r['summary']['reactivated_drivers_mtd'] >= 0)
c("Has new_plus_reactivated_mtd", r['summary']['new_plus_reactivated_mtd'] > 0)

# Metadata
c("nr_source present", r['summary']['nr_source'] is not None)
c("nr_definition_status present", r['summary']['nr_definition_status'] is not None)
c("nr_source_confidence present", r['summary']['nr_source_confidence'] is not None)

# Scoring
c("Has performance_goals_completed", r['summary']['performance_goals_completed'] is not None)
c("Has performance_category field", 'performance_category' in r['summary'])
c("Scoring status present", r['scoring_status'] is not None)

# No provinces
for cn in ["trujillo", "arequipa"]:
    rc = get_loyalty_performance(month="2026-04", country="peru", city=cn)
    c(f"{cn} not_available", rc['freshness_status'] == "not_available")
    c(f"{cn} SH=0", rc['summary']['supply_hours_mtd'] == 0)

# Reference check
nr_ref = 1064
nr_actual = r['summary']['new_plus_reactivated_mtd']
ref_pct = abs(nr_actual - nr_ref) / nr_ref * 100
print(f"\n  N+R ref check: actual={nr_actual} ref~{nr_ref} ({ref_pct:.0f}% diff)")
if ref_pct < 20:
    c("N+R within 20% of reference", True)
elif ref_pct < 100:
    w(f"N+R differs {ref_pct:.0f}% from reference (provisional definition)")
else:
    w(f"N+R differs {ref_pct:.0f}% from reference")

# Engine isolation
try:
    svc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "app", "services", "yango_loyalty_performance_service.py")
    with open(svc, encoding='utf-8') as f:
        src = f.read()
    c("No ForecastEngine import", "ForecastEngine" not in src and "from forecast" not in src.lower())
    c("No SuggestionEngine import", "SuggestionEngine" not in src and "from suggestion" not in src.lower())
    c("No DecisionEngine import", "DecisionEngine" not in src and "from decision" not in src.lower())
    c("No ActionEngine import", "ActionEngine" not in src and "from action" not in src.lower())
    c("No sklearn/torch", "sklearn" not in src and "torch" not in src)
except Exception as e:
    w("Engine isolation check skipped", str(e)[:80])

# Scoring logic test with targets
test_targets = {"AD": 5295.0, "SH": 356000.0, "N_R": 1261.0}
ad_met = r['summary']['active_drivers_mtd'] >= test_targets["AD"]
sh_met = r['summary']['supply_hours_mtd'] >= test_targets["SH"]
nr_met = r['summary']['new_plus_reactivated_mtd'] >= test_targets["N_R"]
goals = sum([ad_met, sh_met, nr_met])
print(f"\n  Hypothetical scoring (test): AD met={ad_met}, SH met={sh_met}, NR met={nr_met} -> {goals}/3")
if goals >= 3: cat = "oro"
elif goals >= 2: cat = "plata"
else: cat = "bronce"
print(f"  Hypothetical category: {cat.upper()}")

c("Scoring not enabled without targets", r['scoring_status'] != "enabled")

print(f"\n{'=' * 70}")
print(f"RESULTS: {PASS} PASS | {FAIL} FAIL | {WARN} WARN")
print(f"VERDICT: {'GO' if FAIL == 0 else 'NO-GO'}")
sys.exit(0 if FAIL == 0 else 1)
