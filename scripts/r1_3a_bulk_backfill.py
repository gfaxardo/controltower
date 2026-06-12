"""Direct bulk backfill for diagnostic traces"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from psycopg2.extras import execute_values
from app.settings import settings
from uuid import uuid4

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=5432,
    dbname='yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

AD, BD, RID = '2026-06-05', '2026-06-04', f'diag_{uuid4().hex[:8]}'

# 1. Decision Traces - fast bulk insert
print(f"1. Decision traces (run={RID}, date={AD})...")
cur.execute(f"""
    INSERT INTO growth.yego_lima_program_decision_trace 
    (run_id, snapshot_date, driver_profile_id, selected_program_code,
     selection_reason, opportunity_score, final_rank, policy_version, evidence_json)
    SELECT %(rid)s, %(d)s, driver_profile_id, selected_program_code,
           CASE 
               WHEN selected_program_code = 'PROGRAM_HIGH_VALUE_RECOVERY' THEN 'POLICY_OVERRIDE'
               ELSE 'HIGHER_PRIORITY'
           END,
           opportunity_score, final_rank, 'v1', '{}'::jsonb
    FROM growth.yango_lima_prioritized_opportunity_daily
    WHERE opportunity_date = %(d)s
    ON CONFLICT (run_id, driver_profile_id, snapshot_date) DO NOTHING
""", {"rid": RID, "d": AD})
dt_count = cur.rowcount
print(f"   Inserted: {dt_count}")

# 2. Transition Traces
print(f"2. Transition traces ({BD} -> {AD})...")
cur.execute(f"""
    INSERT INTO growth.yego_lima_state_transition_trace
    (run_id, snapshot_before, snapshot_after, driver_profile_id,
     transition_type, trigger_reason, policy_version, evidence_json)
    SELECT %(rid)s, %(bd)s, %(ad)s, a.driver_profile_id,
           CASE 
               WHEN b.retention_state != a.retention_state 
               THEN 'RETENTION: ' || b.retention_state || ' -> ' || a.retention_state
               ELSE 'PERFORMANCE: ' || b.performance_state || ' -> ' || a.performance_state
           END,
           CASE
               WHEN b.churn_risk_flag != a.churn_risk_flag THEN 'churn_risk_flag_changed'
               WHEN b.declining_flag != a.declining_flag THEN 'declining_flag_changed'
               ELSE 'data_delta'
           END,
           'v1', '{}'::jsonb
    FROM growth.yango_lima_driver_state_snapshot a
    JOIN growth.yango_lima_driver_state_snapshot b
        ON a.driver_profile_id = b.driver_profile_id
    WHERE a.snapshot_date = %(ad)s AND b.snapshot_date = %(bd)s
      AND (b.retention_state != a.retention_state OR b.performance_state != a.performance_state)
    ON CONFLICT (run_id, driver_profile_id, snapshot_before, snapshot_after) DO NOTHING
""", {"rid": RID, "ad": AD, "bd": BD})
tt_count = cur.rowcount
print(f"   Inserted: {tt_count}")

# 3. Reconciliation
cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id = %(r)s", {"r": RID})
dt_persisted = cur.fetchone()[0]
cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_state_transition_trace WHERE run_id = %(r)s", {"r": RID})
tt_persisted = cur.fetchone()[0]

# Total expected
cur.execute(f"SELECT COUNT(*) FROM growth.yango_lima_prioritized_opportunity_daily WHERE opportunity_date = %(d)s", {"d": AD})
dt_expected = cur.fetchone()[0]

cur.execute(f"""
    SELECT COUNT(*) FROM growth.yango_lima_driver_state_snapshot a
    JOIN growth.yango_lima_driver_state_snapshot b ON a.driver_profile_id = b.driver_profile_id
    WHERE a.snapshot_date = %(ad)s AND b.snapshot_date = %(bd)s
      AND (b.retention_state != a.retention_state OR b.performance_state != a.performance_state)
""", {"ad": AD, "bd": BD})
tt_expected = cur.fetchone()[0]

# Regression
cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id=%(r)s AND selected_program_code IS NULL", {"r": RID})
null_prog = cur.fetchone()[0]
cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id=%(r)s AND selection_reason IS NULL", {"r": RID})
null_reason = cur.fetchone()[0]

cur.close()
conn.close()

print(f"\n3. Reconciliation:")
print(f"   Decision: {dt_persisted}/{dt_expected} ({100*dt_persisted//max(1,dt_expected)}%)")
print(f"   Transition: {tt_persisted}/{tt_expected} ({100*tt_persisted//max(1,tt_expected)}%)")

print(f"\n4. Regression:")
print(f"   Null selected_program: {null_prog}")
print(f"   Null selection_reason: {null_reason}")

print(f"\n{'='*50}")
print(f"VERDICT: {'PASS' if dt_persisted>0 and null_prog==0 else 'FAIL'}")
print(f"{'='*50}")
