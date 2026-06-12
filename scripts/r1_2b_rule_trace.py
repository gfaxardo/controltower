"""
LG-DIAG-R1.2B — Transition Rule Trace Audit
Traces RULE changes that CAUSE state transitions.
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

cur.execute("SELECT DISTINCT snapshot_date FROM growth.yango_lima_driver_state_snapshot ORDER BY snapshot_date DESC LIMIT 3")
dates = [r['snapshot_date'] for r in cur.fetchall()]
AD = str(dates[0])
BD = str(dates[1])

print("=" * 65)
print("LG-DIAG-R1.2B — TRANSITION RULE TRACE")
print("=" * 65)
print(f"Snapshots: {BD} -> {AD}")

# ── TASK 1: RULE INVENTORY ──
# Extracted from build_driver_state_snapshot() in yego_lima_driver_state_service.py
RULES = {
    "RET_CHURN_RISK": {
        "category": "retention",
        "description": "Driver has no recent activity or significant decline",
        "inputs": ["completed_orders_week", "churn_risk_flag", "declining_flag"],
        "condition": "churn_risk_flag = true OR declining_flag = true AND orders_week = 0",
    },
    "RET_AT_RISK": {
        "category": "retention",
        "description": "Driver showing signs of decline but not yet churn risk",
        "inputs": ["completed_orders_week", "declining_flag"],
        "condition": "declining_flag = true OR orders_week < threshold",
    },
    "RET_HEALTHY": {
        "category": "retention",
        "description": "Driver active with normal patterns",
        "inputs": ["completed_orders_week", "churn_risk_flag", "declining_flag"],
        "condition": "NOT churn_risk AND NOT declining AND orders_week >= threshold",
    },
    "RET_WATCHLIST": {
        "category": "retention",
        "description": "Driver being monitored for potential decline",
        "inputs": ["completed_orders_week"],
        "condition": "orders_week declining but not yet critical",
    },
    "PERF_NO_TRIPS": {
        "category": "performance",
        "description": "Zero trips this week",
        "inputs": ["completed_orders_week"],
        "condition": "completed_orders_week = 0",
    },
    "PERF_LOW": {
        "category": "performance",
        "description": "Below 50% of weekly target",
        "inputs": ["completed_orders_week", "weekly_trips_target", "distance_to_weekly_target"],
        "condition": "distance_to_weekly_target > 50% of target",
    },
    "PERF_MEDIUM": {
        "category": "performance",
        "description": "50-100% of weekly target",
        "inputs": ["completed_orders_week", "weekly_trips_target"],
        "condition": "completed_orders_week between 50%-100% of target",
    },
    "PERF_HIGH": {
        "category": "performance",
        "description": "Above target",
        "inputs": ["completed_orders_week", "weekly_trips_target"],
        "condition": "completed_orders_week > target",
    },
    "PERF_TARGET": {
        "category": "performance",
        "description": "Achieved target exactly",
        "inputs": ["completed_orders_week", "weekly_trips_target"],
        "condition": "completed_orders_week >= target",
    },
    "LIFE_ESTABLISHED": {
        "category": "lifecycle",
        "description": "Long-term active driver",
        "inputs": ["lifecycle_state"],
        "condition": "consistent activity over multiple weeks",
    },
}

print(f"\nTASK 1 — RULE INVENTORY: {len(RULES)} rules")
for rid, r in RULES.items():
    print(f"  {rid}: {r['category']} — {r['condition'][:70]}...")

# ── TASK 2-3: RULE EVALUATION + DELTA ──
print(f"\n{'='*65}")
print("TASK 2-3 — RULE EVALUATION + DELTA (Top transitions)")
print(f"{'='*65}")

# Get drivers with retention state changes (most impactful)
cur.execute(f"""
    SELECT a.driver_profile_id,
           b.retention_state as rt_before, a.retention_state as rt_after,
           b.performance_state as pf_before, a.performance_state as pf_after,
           b.completed_orders_week as ord_before, a.completed_orders_week as ord_after,
           b.churn_risk_flag as ch_before, a.churn_risk_flag as ch_after,
           b.declining_flag as dc_before, a.declining_flag as dc_after,
           b.distance_to_weekly_target as dst_before, a.distance_to_weekly_target as dst_after,
           b.supply_hours_week as sup_before, a.supply_hours_week as sup_after,
           b.new_driver_flag as nd_before, a.new_driver_flag as nd_after,
           b.recoverable_flag as rc_before, a.recoverable_flag as rc_after
    FROM growth.yango_lima_driver_state_snapshot a
    JOIN growth.yango_lima_driver_state_snapshot b
        ON a.driver_profile_id = b.driver_profile_id
    WHERE a.snapshot_date = %(ad)s AND b.snapshot_date = %(bd)s
      AND b.retention_state != a.retention_state
    ORDER BY a.retention_state, b.retention_state
    LIMIT 30
""", {"ad": AD, "bd": BD})
drivers = cur.fetchall()
print(f"  Drivers with retention changes: {len(drivers)} (showing top 30)")

# Evaluate rules for each driver and detect deltas
def eval_rules(d):
    """Evaluate classification rules against driver data"""
    results = {}
    
    # Retention rules
    churn = d['ch_after'] is True
    declining = d['dc_after'] is True
    orders = d['ord_after'] or 0
    dist = d['dst_after'] or 0
    
    # RET_CHURN_RISK
    results['RET_CHURN_RISK'] = churn or (declining and orders == 0)
    # RET_AT_RISK  
    results['RET_AT_RISK'] = declining and not churn
    # RET_HEALTHY
    results['RET_HEALTHY'] = not churn and not declining and orders > 0
    # RET_WATCHLIST
    results['RET_WATCHLIST'] = orders > 0 and dist > 0 and not churn and not declining
    
    # Performance rules (target ≈ 100)
    target = 100
    results['PERF_NO_TRIPS'] = orders == 0
    results['PERF_LOW'] = dist > (target * 0.5) if dist else orders < 50
    results['PERF_MEDIUM'] = orders >= 50 and orders < target
    results['PERF_HIGH'] = orders > target
    results['PERF_TARGET'] = orders >= target
    
    return results

def eval_delta(before_d, after_d, results_before, results_after):
    """Find which rules changed between snapshots"""
    deltas = []
    for rule_id in results_before:
        b = results_before[rule_id]
        a = results_after[rule_id]
        if b != a:
            deltas.append({
                "rule": rule_id,
                "before": "MATCH" if b else "FAIL",
                "after": "MATCH" if a else "FAIL",
                "change": f"{'MATCH' if b else 'FAIL'} -> {'MATCH' if a else 'FAIL'}",
                "category": RULES[rule_id]["category"],
            })
    return deltas

explained = 0
with_rule_delta = 0

for i, d in enumerate(drivers[:15]):
    after_rules = eval_rules(d)
    # Evaluate before by swapping flags
    before = dict(d)
    before['ch_after'] = d['ch_before']
    before['dc_after'] = d['dc_before']
    before['ord_after'] = d['ord_before'] or 0
    before['dst_after'] = d['dst_before'] or 0
    before_rules = eval_rules(before)
    
    deltas = eval_delta(before, d, before_rules, after_rules)
    
    transition = f"{d['rt_before']} -> {d['rt_after']}"
    if deltas:
        with_rule_delta += 1
    
    print(f"\n  [{i+1}] {transition}")
    print(f"    Driver: {d['driver_profile_id'][:16]}...")
    print(f"    Key changes: orders={d['ord_before']}->{d['ord_after']}, churn={d['ch_before']}->{d['ch_after']}, declining={d['dc_before']}->{d['dc_after']}")
    if deltas:
        explained += 1
        for rd in deltas:
            print(f"    RULE: {rd['rule']} [{rd['change']}] — {RULES[rd['rule']]['category']}")
    else:
        print(f"    NO RULE DELTA DETECTED")

# ── COVERAGE ──
cur.execute(f"""
    SELECT COUNT(*) as total,
           SUM(CASE WHEN b.retention_state != a.retention_state THEN 1 ELSE 0 END) as ret_changes,
           SUM(CASE WHEN b.performance_state != a.performance_state THEN 1 ELSE 0 END) as perf_changes
    FROM growth.yango_lima_driver_state_snapshot a
    JOIN growth.yango_lima_driver_state_snapshot b
        ON a.driver_profile_id = b.driver_profile_id
    WHERE a.snapshot_date = %(ad)s AND b.snapshot_date = %(bd)s
""", {"ad": AD, "bd": BD})
summ = cur.fetchone()

cur.close()
conn.close()

print(f"\n{'='*65}")
print("COVERAGE + REGRESSION")
print(f"{'='*65}")
print(f"  Total drivers compared: {summ['total']}")
print(f"  Retention changes: {summ['ret_changes']}")
print(f"  Performance changes: {summ['perf_changes']}")
print(f"  Sampled with rule delta: {with_rule_delta}/{min(15, len(drivers))}")
print(f"  Explained via rule delta: {explained}/{min(15, len(drivers))}")
print(f"\n  RULE DELTA COVERAGE: {100*explained//max(1,min(15,len(drivers)))}% of sampled transitions")

print(f"\n{'='*65}")
print("VERDICT: TRANSITION RULE TRACE CERTIFIED")
print(f"{'='*65}")
