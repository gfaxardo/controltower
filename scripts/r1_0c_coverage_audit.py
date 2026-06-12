"""
LG-DIAG-R1.0C — Explainability Coverage Audit
Validates 20 queue drivers + regression checks.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=5432,
    dbname='yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

print("=" * 65)
print("LG-DIAG-R1.0C — EXPLAINABILITY COVERAGE AUDIT")
print("=" * 65)

# Get 20 drivers from queue
cur.execute("""
    SELECT driver_id, queue_status, program_code
    FROM growth.yego_lima_assignment_queue
    WHERE assignment_date = '2026-06-05'
    ORDER BY CASE queue_status WHEN 'READY' THEN 1 WHEN 'HELD' THEN 2 ELSE 3 END
    LIMIT 20
""")
drivers = cur.fetchall()

# Run explainability for each
from app.services.yego_lima_program_explainability_service import get_driver_program_explainability

pass_count = 0
fail_count = 0
regression_fails = 0

print(f"\nValidating {len(drivers)} drivers...\n")

for d in drivers:
    did = d[0]
    qstatus = d[1]
    program = d[2]
    try:
        result = get_driver_program_explainability(did)
        if not result.get('found'):
            print(f"  [FAIL] {did[:16]}... NOT_FOUND in snapshot")
            fail_count += 1
            continue

        snap = result.get('snapshot', {})
        
        # R1.0B regression checks
        checks = []
        df = snap.get('declining_flag')
        cf = snap.get('churn_risk_flag')
        rf = snap.get('reached_target_flag')
        dt = snap.get('distance_to_weekly_target')
        
        if df is not None and not isinstance(df, bool):
            checks.append(f"declining_flag={df} (not bool!)")
            regression_fails += 1
        if cf is not None and not isinstance(cf, bool):
            checks.append(f"churn_risk_flag={cf} (not bool!)")
            regression_fails += 1
        if rf is not None and not isinstance(rf, bool):
            checks.append(f"reached_target_flag={rf} (not bool!)")
            regression_fails += 1
        
        has_reason = any(p['eligible'] for p in result.get('programs', []))
        has_rules = any(
            rule.get('source_field') and rule.get('rule_id')
            for p in result.get('programs', [])
            for rule in p.get('rules', [])
        )
        
        if has_reason and has_rules and not checks:
            pass_count += 1
        else:
            print(f"  [WARN] {did[:16]}... q={qstatus}, checks={checks}")
            fail_count += 1
            
    except Exception as e:
        print(f"  [FAIL] {did[:16]}... ERROR: {str(e)[:60]}")
        fail_count += 1

# All prioritized
print(f"\n--- All Prioritized Coverage ---")
cur.execute("SELECT COUNT(*) FROM growth.yango_lima_prioritized_opportunity_daily WHERE opportunity_date = '2026-06-05'")
total_pri = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM growth.yango_lima_prioritized_opportunity_daily WHERE opportunity_date = '2026-06-05' AND selected_program_code IS NOT NULL")
with_prog = cur.fetchone()[0]
print(f"  Total prioritized: {total_pri}")
print(f"  With selected_program_code: {with_prog} ({100*with_prog//max(1,total_pri)}%)")

# HV Recovery specifically  
cur.execute("""
    SELECT COUNT(*) FROM growth.yango_lima_prioritized_opportunity_daily
    WHERE opportunity_date = '2026-06-05' AND selected_program_code = 'PROGRAM_HIGH_VALUE_RECOVERY'
""")
hv = cur.fetchone()[0]
print(f"  HIGH_VALUE_RECOVERY: {hv} drivers (policy engine override)")

# Queue coverage
print(f"\n--- Queue Coverage ---")
cur.execute("""
    SELECT queue_status, COUNT(*) FROM growth.yego_lima_assignment_queue
    WHERE assignment_date = '2026-06-05' GROUP BY queue_status
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

cur.close()
conn.close()

# Summary
print(f"\n{'='*65}")
print(f"RESULTS")
print(f"{'='*65}")
print(f"  Drivers validated: {len(drivers)}")
print(f"  PASS: {pass_count}")
print(f"  FAIL: {fail_count}")
print(f"  R1.0B regression fails: {regression_fails}")
print(f"  Coverage: {100*pass_count//max(1,len(drivers))}%")
print(f"\n  VERDICT: {'PASS' if fail_count == 0 and regression_fails == 0 else 'FAIL'}")
