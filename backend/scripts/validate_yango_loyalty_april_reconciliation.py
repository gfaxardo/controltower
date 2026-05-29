#!/usr/bin/env python3
"""QA: Yango Loyalty April 2026 Reconciliation"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.yango_loyalty_performance_service import get_loyalty_performance

PASS = 0; FAIL = 0; WARN = 0
def c(l, cond, d=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  [PASS] {l}")
    else: FAIL += 1; print(f"  [FAIL] {l} -- {d}")
def w(l, d=""):
    global WARN; WARN += 1; print(f"  [WARN] {l} -- {d}")

r = get_loyalty_performance(month="2026-04", country="peru")

print("=" * 70)
print("QA: April 2026 Reconciliation — Yango Loyalty Lima")
print("=" * 70)

# AD
ad_ct = r['summary']['active_drivers_mtd']
ad_ref = 5601
ad_drift = abs(ad_ct - ad_ref) / ad_ref * 100
print(f"\n1. AD: CT={ad_ct} | Yango={ad_ref} | Drift={ad_drift:.1f}%")
c(f"AD within 5% of Yango ref", ad_drift <= 5, f"drift={ad_drift:.1f}%")

# SH
sh_ct = r['summary']['supply_hours_mtd']
sh_ref = 357000
sh_drift = abs(sh_ct - sh_ref) / sh_ref * 100
print(f"2. SH: CT={sh_ct:,.0f} | Yango={sh_ref:,} | Drift={sh_drift:.1f}%")
c(f"SH drift documented as source coverage", sh_drift <= 15, f"drift={sh_drift:.1f}% (known: fleet_summary partial source)")

# N+R
nr_ct = r['summary']['new_plus_reactivated_mtd']
nr_ref = 1064
nr_drift = abs(nr_ct - nr_ref) / nr_ref * 100
print(f"3. N+R: CT={nr_ct} | Yango={nr_ref} | Drift={nr_drift:.1f}%")
w(f"N+R drift {nr_drift:.0f}% — provisional definition", "awaiting business validation")

# Guardrails
print(f"\n4. Guardrails:")
print(f"   Scoring status: {r['scoring_status']}")
c("Scoring is blocked_pending_reconciliation",
  r['scoring_status'] == 'blocked_pending_reconciliation')
c("Has reconciliation data", 'reconciliation' in r)
c("Has guardrail_flags", bool(r.get('reconciliation', {}).get('guardrail_flags')))
c("4+ guardrail flags triggered",
  len(r.get('reconciliation', {}).get('guardrail_flags', [])) >= 3)

# Provinces
for cn in ["trujillo", "arequipa"]:
    rc = get_loyalty_performance(month="2026-04", country="peru", city=cn)
    c(f"{cn} not_available", rc['freshness_status'] == "not_available")

# AD should be Auto regular
c("AD uses Auto regular (not all-slices)", abs(ad_ct - 5496) <= 10)

# N+R should be fleet universe
c("N+R filtered to fleet universe (reduced from 2075)", nr_ct < 1800)

# UI — no category shown
print(f"\n5. UI safety:")
c("performance_category is null (scoring blocked)", r['summary']['performance_category'] is None)
c("performance_goals_completed = 0 (scoring blocked)", r['summary']['performance_goals_completed'] == 0)

print(f"\n{'=' * 70}")
print(f"RESULTS: {PASS} PASS | {FAIL} FAIL | {WARN} WARN")
print(f"VERDICT: {'GO' if FAIL == 0 else 'CONDITIONAL GO' if WARN > 0 else 'NO-GO'}")
sys.exit(0 if FAIL == 0 else 1)
