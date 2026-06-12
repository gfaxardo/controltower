"""
LG-DIAG-R1.0D — Full Queue Trace Audit: 100% traceability
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from psycopg2.extras import RealDictCursor
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=5432,
    dbname='yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor(cursor_factory=RealDictCursor)

D = '2026-06-05'

print("=" * 65)
print("LG-DIAG-R1.0D — FULL QUEUE TRACE AUDIT")
print("=" * 65)

# Get ALL queue drivers with full trace
cur.execute(f"""
    SELECT q.driver_id, q.queue_status, q.program_code as queue_program,
           q.assigned_channel, q.priority_rank,
           p.selected_program_code as pri_program,
           p.opportunity_score, p.final_rank, p.is_actionable_today,
           e.program_code as elig_program, e.eligible_flag,
           s.lifecycle_state, s.performance_state, s.retention_state
    FROM growth.yego_lima_assignment_queue q
    LEFT JOIN growth.yango_lima_prioritized_opportunity_daily p
        ON q.driver_id = p.driver_profile_id AND p.opportunity_date = %(d)s
    LEFT JOIN growth.yango_lima_program_eligibility_daily e
        ON q.driver_id = e.driver_profile_id AND e.eligibility_date = %(d)s
        AND (q.program_code = e.program_code OR p.selected_program_code = e.program_code)
    LEFT JOIN growth.yango_lima_driver_state_snapshot s
        ON q.driver_id = s.driver_profile_id AND s.snapshot_date = %(d)s
    WHERE q.assignment_date = %(d)s
""", {"d": D})
all_drivers = cur.fetchall()

total = len(all_drivers)
trace_pass = 0
policy_override_pass = 0
trace_fail = 0
orphans = []

for d in all_drivers:
    did = d['driver_id']
    has_snapshot = d['lifecycle_state'] is not None
    has_prioritized = d['pri_program'] is not None
    has_eligibility = d['eligible_flag'] is True
    queue_prog = d['queue_program'] or ''
    
    # Classify
    if has_eligibility and has_prioritized:
        trace_pass += 1
    elif has_prioritized and not has_eligibility:
        # Policy override case
        if d['pri_program'] == 'PROGRAM_HIGH_VALUE_RECOVERY':
            policy_override_pass += 1
        else:
            trace_fail += 1
            orphans.append({
                "driver_id": did, "queue_status": d['queue_status'],
                "queue_program": queue_prog, "pri_program": d['pri_program'],
                "reason": "prioritized but no eligibility (not HV_RECOVERY)"
            })
    elif has_snapshot and not has_prioritized and not has_eligibility:
        # In queue but no prioritized and no eligibility - stale?
        trace_fail += 1
        orphans.append({
            "driver_id": did, "queue_status": d['queue_status'],
            "queue_program": queue_prog,
            "reason": "in queue but no prioritized and no eligibility"
        })
    else:
        trace_fail += 1
        orphans.append({
            "driver_id": did, "queue_status": d['queue_status'],
            "queue_program": queue_prog,
            "reason": "unknown trace gap"
        })

print(f"\nTotal queue drivers: {total}")
print(f"  TRACE_PASS (eligibility + prioritized): {trace_pass}")
print(f"  POLICY_OVERRIDE_PASS (HV_RECOVERY): {policy_override_pass}")
print(f"  TRACE_FAIL: {trace_fail}")

print(f"\nOrphans ({len(orphans)}):")
for o in orphans:
    print(f"  {o['driver_id'][:16]}... status={o['queue_status']}, prog={o['queue_program']}, reason={o['reason']}")

# Classify root causes
print(f"\nRoot cause classification:")
for o in orphans:
    did = o['driver_id']
    cur.execute(f"""
        SELECT p.selected_program_code FROM growth.yango_lima_prioritized_opportunity_daily p
        WHERE p.driver_profile_id = %(did)s AND p.opportunity_date = %(d)s
    """, {"did": did, "d": D})
    pri = cur.fetchone()
    cur.execute(f"""
        SELECT program_code FROM growth.yango_lima_program_eligibility_daily e
        WHERE e.driver_profile_id = %(did)s AND e.eligibility_date = %(d)s
    """, {"did": did, "d": D})
    elig = cur.fetchall()
    cur.execute(f"""
        SELECT lifecycle_state FROM growth.yango_lima_driver_state_snapshot s
        WHERE s.driver_profile_id = %(did)s AND s.snapshot_date = %(d)s
    """, {"did": did, "d": D})
    snap = cur.fetchone()
    
    cause = "F) data artifact"
    if pri and pri['selected_program_code'] == 'PROGRAM_HIGH_VALUE_RECOVERY':
        cause = "A) HV_RECOVERY policy override"
    elif not snap:
        cause = "E) eligibility missing - no snapshot"
    elif snap and not pri:
        cause = "C) policy engine skipped this driver"
    
    print(f"  {did[:16]}... cause={cause}")

cur.close()
conn.close()

print(f"\n{'='*65}")
print(f"VERDICT: {'PASS' if trace_fail == 0 else 'FAIL - ' + str(trace_fail) + ' orphans found'}")
print(f"{'='*65}")
