#!/usr/bin/env python3
"""Preview all definition sets against April 2026 Lima reference."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.yango_loyalty_definition_service import preview_all_sets

r = preview_all_sets()

print("=" * 95)
print("Yango Loyalty Metric Definition Preview — April 2026 Lima")
print("=" * 95)

ref = {"active_drivers": 5601, "supply_hours": 357000, "new_plus_reactivated": 1064}

print(f"{'Definition Set':<28} {'AD':>6} {'AD_ref':>6} {'AD%':>6} {'SH':>11} {'SH_ref':>8} {'SH%':>6} {'N+R':>5} {'N+R_ref':>6} {'NR%':>6} {'Val':>8}")
print(f"{'-'*28} {'-'*6} {'-'*6} {'-'*6} {'-'*11} {'-'*8} {'-'*6} {'-'*5} {'-'*6} {'-'*6} {'-'*8}")

for p in r["previews"]:
    ad_d = p["ad_diff_pct"] or 0
    sh_d = p["sh_diff_pct"] or 0
    nr_d = p["nr_diff_pct"] or 0
    print(f"{p['definition_set_id']:<28} {p['active_drivers']:>6} {ref['active_drivers']:>6} {ad_d:>5.0f}% "
          f"{p['supply_hours']:>11,.0f} {ref['supply_hours']:>8,} {sh_d:>5.0f}% "
          f"{p['new_plus_reactivated']:>5} {ref['new_plus_reactivated']:>6} {nr_d:>5.0f}% "
          f"{p['validation_status']:>8}")

print(f"\nBest candidates by drift:")
scored = [(p, (p['ad_diff_pct'] or 999)+(p['sh_diff_pct'] or 999)+(p['nr_diff_pct'] or 999)) for p in r['previews']]
scored.sort(key=lambda x: x[1])
for p, score in scored[:3]:
    print(f"  {p['definition_set_id']}: total_drift={score:.0f}% validation={p['validation_status']}")
