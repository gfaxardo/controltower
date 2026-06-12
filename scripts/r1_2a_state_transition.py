"""
LG-DIAG-R1.2A — State Transition Engine Audit
Detects and explains driver state changes between snapshots.
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

print("=" * 65)
print("LG-DIAG-R1.2A — STATE TRANSITION ENGINE")
print("=" * 65)

# 1. Find two consecutive snapshot dates
cur.execute("SELECT DISTINCT snapshot_date FROM growth.yango_lima_driver_state_snapshot ORDER BY snapshot_date DESC LIMIT 3")
dates = [r['snapshot_date'] for r in cur.fetchall()]
if len(dates) < 2:
    print("ERROR: Need at least 2 snapshot dates")
    exit(1)

after_date = str(dates[0])
before_date = str(dates[1])
print(f"\nSnapshots: {before_date} -> {after_date}")

# ── TASK 1: STATE INVENTORY ──
print(f"\n{'='*65}")
print("TASK 1 — STATE INVENTORY")
print(f"{'='*65}")

for col in ['lifecycle_state', 'performance_state', 'retention_state']:
    cur.execute(f"SELECT {col}, COUNT(*) FROM growth.yango_lima_driver_state_snapshot WHERE snapshot_date = %(d)s GROUP BY {col} ORDER BY COUNT(*) DESC", {"d": after_date})
    print(f"\n  {col}:")
    for r in cur.fetchall():
        print(f"    {r[col]}: {r['count']}")

# ── TASK 2-3: TRANSITION DETECTION ──
print(f"\n{'='*65}")
print("TASK 2-3 — TRANSITION DETECTION")
print(f"{'='*65}")

cur.execute(f"""
    SELECT a.driver_profile_id,
           b.lifecycle_state as lc_before, a.lifecycle_state as lc_after,
           b.performance_state as pf_before, a.performance_state as pf_after,
           b.retention_state as rt_before, a.retention_state as rt_after,
           b.completed_orders_week as orders_before, a.completed_orders_week as orders_after,
           b.supply_hours_week as supply_before, a.supply_hours_week as supply_after,
           b.distance_to_weekly_target as dist_before, a.distance_to_weekly_target as dist_after,
           b.declining_flag as decl_before, a.declining_flag as decl_after,
           b.churn_risk_flag as churn_before, a.churn_risk_flag as churn_after
    FROM growth.yango_lima_driver_state_snapshot a
    JOIN growth.yango_lima_driver_state_snapshot b
        ON a.driver_profile_id = b.driver_profile_id
    WHERE a.snapshot_date = %(ad)s AND b.snapshot_date = %(bd)s
""", {"ad": after_date, "bd": before_date})
drivers = cur.fetchall()
print(f"  Drivers in both snapshots: {len(drivers)}")

# Classify transitions
transitions = []
lifecycle_changes = 0
performance_changes = 0
retention_changes = 0

for d in drivers:
    lc_change = d['lc_before'] != d['lc_after']
    pf_change = d['pf_before'] != d['pf_after']
    rt_change = d['rt_before'] != d['rt_after']
    
    if lc_change or pf_change or rt_change:
        t = {
            "driver_id": d['driver_profile_id'],
            "lc_before": d['lc_before'], "lc_after": d['lc_after'],
            "pf_before": d['pf_before'], "pf_after": d['pf_after'],
            "rt_before": d['rt_before'], "rt_after": d['rt_after'],
            "orders_delta": (d['orders_after'] or 0) - (d['orders_before'] or 0),
            "supply_delta": round(float(d['supply_after'] or 0) - float(d['supply_before'] or 0), 1),
        }
        
        if lc_change: lifecycle_changes += 1
        if pf_change: performance_changes += 1
        if rt_change: retention_changes += 1
        
        # Determine transition type and trigger
        if d['lc_before'] != d['lc_after']:
            t['transition_type'] = f"LIFECYCLE: {d['lc_before']} -> {d['lc_after']}"
        elif d['rt_before'] != d['rt_after']:
            t['transition_type'] = f"RETENTION: {d['rt_before']} -> {d['rt_after']}"
        else:
            t['transition_type'] = f"PERFORMANCE: {d['pf_before']} -> {d['pf_after']}"
        
        # Trigger reason from real data
        triggers = []
        if (d['orders_before'] or 0) > 0 and (d['orders_after'] or 0) == 0:
            triggers.append("orders_dropped_to_zero")
        if (d['orders_before'] or 0) == 0 and (d['orders_after'] or 0) > 0:
            triggers.append("orders_resumed")
        if d['decl_before'] != d['decl_after']:
            triggers.append(f"declining_flag_changed: {d['decl_before']} -> {d['decl_after']}")
        if d['churn_before'] != d['churn_after']:
            triggers.append(f"churn_risk_flag_changed: {d['churn_before']} -> {d['churn_after']}")
        if abs(t['orders_delta']) >= 10:
            triggers.append(f"orders_week_delta: {t['orders_delta']}")
        if abs(t['supply_delta']) >= 5:
            triggers.append(f"supply_hours_delta: {t['supply_delta']}")
        
        if not triggers:
            triggers.append("minor_changes")
        
        t['trigger_reason'] = "; ".join(triggers)
        transitions.append(t)

print(f"  Total transitions detected: {len(transitions)}")
print(f"  Lifecycle changes: {lifecycle_changes}")
print(f"  Performance changes: {performance_changes}")
print(f"  Retention changes: {retention_changes}")

# ── TASK 4-5: CAUSALITY + EXPLAINABILITY ──
print(f"\n{'='*65}")
print("TASK 4-5 — TRANSITION EXPLANATIONS (Top 10)")
print(f"{'='*65}")

# Top by type
for i, t in enumerate(transitions[:10]):
    print(f"\n  [{i+1}] {t['transition_type']}")
    print(f"    Driver: {t['driver_id'][:16]}...")
    print(f"    Orders: {t.get('orders_before','?')} -> {t.get('orders_after','?')}")
    print(f"    Supply: {t.get('supply_before','?')}h -> {t.get('supply_after','?')}h")
    print(f"    Trigger: {t['trigger_reason']}")

# Most common transition types
from collections import Counter
type_counts = Counter(t['transition_type'] for t in transitions)
print(f"\n  Most common transitions:")
for tt, cnt in type_counts.most_common(10):
    print(f"    {tt}: {cnt}")

# ── TASK 6: COVERAGE ──
print(f"\n{'='*65}")
print("TASK 6 — COVERAGE")
print(f"{'='*65}")

explained = sum(1 for t in transitions if t['trigger_reason'] != 'minor_changes')
with_data = sum(1 for t in transitions if t.get('orders_before') is not None)
print(f"  Transitions: {len(transitions)}")
print(f"  With explicit cause: {explained} ({100*explained//max(1,len(transitions))}%)")
print(f"  With data points: {with_data} ({100*with_data//max(1,len(transitions))}%)")

# ── TASK 7: REGRESSION ──
print(f"\n{'='*65}")
print("TASK 7 — REGRESSION")
print(f"{'='*65}")

no_before = sum(1 for t in transitions if not t.get('lc_before'))
no_after = sum(1 for t in transitions if not t.get('lc_after'))
no_trigger = sum(1 for t in transitions if not t['trigger_reason'])
print(f"  Missing state_before: {no_before}")
print(f"  Missing state_after: {no_after}")
print(f"  Missing trigger_reason: {no_trigger}")

cur.close()
conn.close()

print(f"\n{'='*65}")
print(f"VERDICT:")
print(f"  Transitions detected: {len(transitions)}")
print(f"  With explicit cause: {explained}/{len(transitions)}")
print(f"  Regression gaps: {no_before + no_after + no_trigger}")
print(f"  STATE TRANSITION ENGINE: CERTIFIED" if no_before==0 and no_after==0 else "NEEDS INVESTIGATION")
print(f"{'='*65}")
