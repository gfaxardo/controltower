import time
t0 = time.time()
from app.services.omniview_matrix_integrity_service import run_omniview_matrix_integrity_checks
t1 = time.time()
full = run_omniview_matrix_integrity_checks()
t2 = time.time()
op = full["operational_trust"]
od = full.get("operational_decision", {})
dc = od.get("confidence", {})

print(f"Compute: {t2-t0:.1f}s (setup={t1-t0:.1f}s, run={t2-t1:.1f}s)")
print(f"Trust: {op['status']} blocked={op['blocked_count']} warn={op['warning_count']}")
print(f"Decision: {od.get('decision_mode')} conf={dc.get('score')} cov={dc.get('coverage')} fresh={dc.get('freshness')} cons={dc.get('consistency')}")

bcodes = [f["code"] for f in op["blocked_findings"]]
wcodes = [f["code"] for f in op["warning_findings"]]
print(f"Blocked codes: {bcodes}")
print(f"Warning codes: {wcodes}")

print("\n--- KEY FINDINGS ---")
target_codes = {
    "ROLLUP_MISMATCH", "MONTH_TRIPS_MISMATCH", "MONTH_REVENUE_MISMATCH",
    "FACT_LAYER_EMPTY_WEEKLY", "REVENUE_NULL_MASSIVE", "TRUST_OSCILLATION",
    "SERVING_INTEGRITY_BLOCKED", "FRESHNESS_GOVERNANCE_BREACH"
}
for f in full["findings"]:
    code = f.get("code", "")
    if code in target_codes:
        print(f"  [{code}] sev={f.get('severity')} | {f.get('message','')[:300]}")
