"""
LG-DIAG-R1.3A — Backfill: Generate + Persist diagnostic traces for certified snapshots
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from psycopg2.extras import RealDictCursor
from app.settings import settings
from uuid import uuid4

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=5432,
    dbname='yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor(cursor_factory=RealDictCursor)

AD, BD = '2026-06-05', '2026-06-04'
RUN_ID = f"diag_backfill_{uuid4().hex[:8]}"

print("=" * 60)
print("LG-DIAG-R1.3A — DIAGNOSTIC TRACE BACKFILL")
print("=" * 60)
print(f"Run: {RUN_ID}")
print(f"Decision: {AD}")
print(f"Transition: {BD} -> {AD}")

# ── DECISION TRACES ──
print("\n1. Building decision traces...")
cur.execute(f"""
    SELECT p.driver_profile_id, p.selected_program_code, p.opportunity_score,
           p.final_rank,
           array_agg(DISTINCT e.program_code) FILTER (WHERE e.eligible_flag) as eligible
    FROM growth.yango_lima_prioritized_opportunity_daily p
    LEFT JOIN growth.yango_lima_program_eligibility_daily e
        ON p.driver_profile_id = e.driver_profile_id AND e.eligibility_date = %(d)s
    WHERE p.opportunity_date = %(d)s
    GROUP BY 1,2,3,4
""", {"d": AD})
decisions = cur.fetchall()

dt_traces = []
for d in decisions:
    elig = d['eligible'] or []
    sel = d['selected_program_code']
    elig_count = len([e for e in elig if e])
    reason = "SINGLE_PROGRAM" if elig_count <= 1 else "HIGHER_PRIORITY"
    if sel == 'PROGRAM_HIGH_VALUE_RECOVERY':
        reason = "POLICY_OVERRIDE"
    
    dt_traces.append({
        "driver_id": d['driver_profile_id'],
        "eligible_programs": [e for e in elig if e],
        "selected_program": sel,
        "selection_reason": reason,
        "selection_score": float(d['opportunity_score']) if d['opportunity_score'] else 0,
        "selection_priority": d['final_rank'],
        "policy_version": "v1",
    })

print(f"   Generated {len(dt_traces)} decision traces")

# Write decision traces
from app.services.yego_lima_diagnostic_trace_writer import write_decision_traces
dt_result = write_decision_traces(RUN_ID, AD, dt_traces)
print(f"   Persisted: {dt_result['inserted']}")

# ── TRANSITION TRACES ──
print("\n2. Building transition traces...")
cur.execute(f"""
    SELECT a.driver_profile_id,
           b.retention_state as rt_before, a.retention_state as rt_after,
           b.performance_state as pf_before, a.performance_state as pf_after,
           b.lifecycle_state as lc_before, a.lifecycle_state as lc_after,
           b.churn_risk_flag as ch_before, a.churn_risk_flag as ch_after,
           b.declining_flag as dc_before, a.declining_flag as dc_after,
           b.completed_orders_week as ord_before, a.completed_orders_week as ord_after,
           b.avg_orders_4w as avg_before, a.avg_orders_4w as avg_after
    FROM growth.yango_lima_driver_state_snapshot a
    JOIN growth.yango_lima_driver_state_snapshot b
        ON a.driver_profile_id = b.driver_profile_id
    WHERE a.snapshot_date = %(ad)s AND b.snapshot_date = %(bd)s
      AND (b.retention_state != a.retention_state OR b.performance_state != a.performance_state)
""", {"ad": AD, "bd": BD})
transitions = cur.fetchall()

tt_traces = []
for t in transitions:
    deltas = []
    if t['ch_before'] != t['ch_after']:
        deltas.append({"rule": "RET_CHURN_RISK", "before": "MATCH" if t['ch_before'] else "FAIL", "after": "MATCH" if t['ch_after'] else "FAIL"})
    if t['dc_before'] != t['dc_after']:
        deltas.append({"rule": "RET_AT_RISK", "before": "MATCH" if t['dc_before'] else "FAIL", "after": "MATCH" if t['dc_after'] else "FAIL"})
    
    rt_change = t['rt_before'] != t['rt_after']
    pf_change = t['pf_before'] != t['pf_after']
    tt_type = f"RETENTION: {t['rt_before']}->{t['rt_after']}" if rt_change else f"PERFORMANCE: {t['pf_before']}->{t['pf_after']}"
    
    trigger = "; ".join([f"{rd['rule']}:{rd['before']}->{rd['after']}" for rd in deltas]) if deltas else "minor_changes"
    
    tt_traces.append({
        "driver_id": t['driver_profile_id'],
        "state_before": {"lifecycle": t['lc_before'], "retention": t['rt_before'], "performance": t['pf_before']},
        "state_after": {"lifecycle": t['lc_after'], "retention": t['rt_after'], "performance": t['pf_after']},
        "transition_type": tt_type,
        "rule_deltas": deltas,
        "trigger_reason": trigger,
        "policy_version": "v1",
    })

print(f"   Generated {len(tt_traces)} transition traces")

from app.services.yego_lima_diagnostic_trace_writer import write_transition_traces
tt_result = write_transition_traces(RUN_ID, BD, AD, tt_traces)
print(f"   Persisted: {tt_result['inserted']}")

# ── RECONCILIATION ──
print("\n3. Reconciliation...")
cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id = %(r)s", {"r": RUN_ID})
dt_persisted = cur.fetchone()['count']
cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_state_transition_trace WHERE run_id = %(r)s", {"r": RUN_ID})
tt_persisted = cur.fetchone()['count']

print(f"   Decision traces: {len(dt_traces)} generated = {dt_persisted} persisted")
print(f"   Transition traces: {len(tt_traces)} generated = {tt_persisted} persisted")

# Regression
cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id = %(r)s AND selected_program_code IS NULL", {"r": RUN_ID})
null_prog = cur.fetchone()['count']
cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_state_transition_trace WHERE run_id = %(r)s AND rule_delta_json = '[]'::jsonb", {"r": RUN_ID})
empty_rules = cur.fetchone()['count']

print(f"\n4. Regression:")
print(f"   Null selected_program: {null_prog}")
print(f"   Empty rule_delta: {empty_rules}")

cur.close()
conn.close()

print(f"\n{'='*60}")
print(f"VERDICT: {'PASS' if dt_persisted == len(dt_traces) and null_prog == 0 else 'FAIL'}")
print(f"{'='*60}")
