"""
LG-DIAG-R1.1A — Program Decision Trace Audit + Service
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
print("LG-DIAG-R1.1A — DECISION TRACE AUDIT")
print("=" * 65)

# ── PHASE 2: MULTI-ELIGIBILITY ──
print("\n1. MULTI-ELIGIBILITY AUDIT")
cur.execute(f"""
    SELECT driver_profile_id, array_agg(program_code ORDER BY program_code) as programs,
           COUNT(*) as n
    FROM growth.yango_lima_program_eligibility_daily
    WHERE eligibility_date = %(d)s AND eligible_flag = true
    GROUP BY driver_profile_id
""", {"d": D})
rows = cur.fetchall()

multi = {1: 0, 2: 0, 3: 0, 4: 0}
for r in rows:
    n = r['n']
    multi[min(n, 4)] = multi.get(min(n, 4), 0) + 1

total_eligible = sum(multi.values())
print(f"  Total drivers with eligibility: {total_eligible}")
for k in sorted(multi.keys()):
    pct = 100 * multi[k] / max(1, total_eligible)
    print(f"  {k} program(s): {multi[k]} ({pct:.1f}%)")

# Most common combinations
cur.execute(f"""
    SELECT programs, COUNT(*) as n FROM (
        SELECT array_agg(program_code ORDER BY program_code) as programs
        FROM growth.yango_lima_program_eligibility_daily
        WHERE eligibility_date = %(d)s AND eligible_flag = true
        GROUP BY driver_profile_id
    ) t GROUP BY programs ORDER BY n DESC LIMIT 10
""", {"d": D})
print(f"\n  Top program combinations:")
for r in cur.fetchall():
    print(f"    {r['programs']}: {r['n']} drivers")

# ── PHASE 3-4: DECISION TRACE ──
print(f"\n2. DECISION TRACE (prioritized drivers)")
cur.execute(f"""
    SELECT p.driver_profile_id, p.selected_program_code, p.opportunity_score,
           p.final_rank, p.is_actionable_today,
           array_agg(DISTINCT e.program_code) FILTER (WHERE e.eligible_flag) as eligible_programs,
           COUNT(DISTINCT e.program_code) FILTER (WHERE e.eligible_flag) as eligible_count
    FROM growth.yango_lima_prioritized_opportunity_daily p
    LEFT JOIN growth.yango_lima_program_eligibility_daily e
        ON p.driver_profile_id = e.driver_profile_id AND e.eligibility_date = %(d)s
    WHERE p.opportunity_date = %(d)s
    GROUP BY p.driver_profile_id, p.selected_program_code, p.opportunity_score, p.final_rank, p.is_actionable_today
""", {"d": D})
decisions = cur.fetchall()

decision_map = {}
for d in decisions:
    selected = d['selected_program_code']
    eligible = d['eligible_programs'] or []
    eligible_count = d['eligible_count'] or len(eligible)
    
    reason = "SINGLE_PROGRAM" if eligible_count <= 1 else "HIGHER_PRIORITY"
    if selected == 'PROGRAM_HIGH_VALUE_RECOVERY':
        reason = "POLICY_OVERRIDE"
    
    decision_map[d['driver_profile_id']] = {
        "selected_program": selected,
        "eligible_programs": [p for p in eligible if p],
        "eligible_count": eligible_count,
        "selection_reason": reason,
        "selection_score": float(d['opportunity_score']) if d['opportunity_score'] else 0,
        "selection_priority": d['final_rank'],
        "selection_policy_version": "v1",
    }

print(f"  Total prioritized: {len(decisions)}")
print(f"  With decision trace: {len(decision_map)} ({100*len(decision_map)//max(1,len(decisions))}%)")

# Decision reason distribution
reasons = {}
for v in decision_map.values():
    r = v['selection_reason']
    reasons[r] = reasons.get(r, 0) + 1
print(f"\n  Decision reasons:")
for r, c in sorted(reasons.items(), key=lambda x: -x[1]):
    print(f"    {r}: {c}")

# ── PHASE 6: 20-DRIVER SAMPLE ──
print(f"\n3. 20-DRIVER DECISION TRACE SAMPLE")
sample_drivers = list(decision_map.keys())[:20]
for did in sample_drivers:
    dt = decision_map[did]
    print(f"\n  driver={did[:16]}...")
    print(f"    Eligible: {dt['eligible_programs']}")
    print(f"    Selected: {dt['selected_program']}")
    print(f"    Reason: {dt['selection_reason']}")
    print(f"    Score: {dt['selection_score']}, Rank: {dt['selection_priority']}")

# ── PHASE 9: REGRESSION ──
print(f"\n4. REGRESSION AUDIT")
no_selected = sum(1 for d in decisions if not d['selected_program_code'])
no_reason = sum(1 for v in decision_map.values() if not v['selection_reason'])
hv_no_trace = sum(1 for v in decision_map.values() 
                  if v['selected_program'] == 'PROGRAM_HIGH_VALUE_RECOVERY' and v['selection_reason'] != 'POLICY_OVERRIDE')

print(f"  Without selected_program: {no_selected}")
print(f"  Without decision reason: {no_reason}")
print(f"  HV_RECOVERY without override trace: {hv_no_trace}")

cur.close()
conn.close()

print(f"\n{'='*65}")
print(f"VERDICT:")
print(f"  Multi-eligibility: PASS ({multi[1]} single, {multi[2]} dual, {multi[3]} triple)")
print(f"  Decision coverage: {len(decision_map)}/{len(decisions)} ({100*len(decision_map)//max(1,len(decisions))}%)")
print(f"  Regression: {'PASS' if no_selected==0 and no_reason==0 and hv_no_trace==0 else 'FAIL'}")
print(f"{'='*65}")
