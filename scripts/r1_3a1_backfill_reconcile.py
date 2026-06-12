"""
R1.3A.1 — Trace Backfill + Reconciliation
Bulk INSERT with reconciliation audit.
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings
from uuid import uuid4

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=5432,
    dbname='yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

AD, BD = '2026-06-05', '2026-06-04'
RID = 'diag_' + uuid4().hex[:8]
JSON_EMPTY_OBJ = '{}'

print("=" * 60)
print("R1.3A.1 — TRACE BACKFILL + RECONCILIATION")
print("=" * 60)
print("Run: " + RID)
print("Decision: " + AD)
print("Transition: " + BD + " -> " + AD)

# ── TASK 1: Validate tables ──
print("\n1. TABLE VALIDATION")
for table in ['growth.yego_lima_program_decision_trace', 'growth.yego_lima_state_transition_trace']:
    cur.execute("SELECT COUNT(*) FROM " + table)
    cnt = cur.fetchone()[0]
    cur.execute("SELECT indexname FROM pg_indexes WHERE tablename = '" + table.split('.')[1] + "'")
    idxs = [r[0] for r in cur.fetchall()]
    print("   " + table + ": " + str(cnt) + " rows, " + str(len(idxs)) + " indexes")

# ── TASK 2: BACKFILL ──
t0 = time.time()

# Decision traces
print("\n2. BACKFILL: Decision traces...")
sql_dt = """
    INSERT INTO growth.yego_lima_program_decision_trace 
    (run_id, snapshot_date, driver_profile_id, selected_program_code,
     selection_reason, opportunity_score, final_rank, policy_version, evidence_json)
    SELECT %(rid)s, %(d)s, driver_profile_id, selected_program_code,
           CASE 
               WHEN selected_program_code = 'PROGRAM_HIGH_VALUE_RECOVERY' THEN 'POLICY_OVERRIDE'
               ELSE 'HIGHER_PRIORITY'
           END,
           opportunity_score, final_rank, 'v1', %(ev)s::jsonb
    FROM growth.yango_lima_prioritized_opportunity_daily
    WHERE opportunity_date = %(d)s
    ON CONFLICT (run_id, driver_profile_id, snapshot_date) DO NOTHING
"""
cur.execute(sql_dt, {"rid": RID, "d": AD, "ev": JSON_EMPTY_OBJ})
dt_inserted = cur.rowcount
dt_time = time.time() - t0
print("   Inserted: " + str(dt_inserted) + " in " + str(round(dt_time, 1)) + "s")

# Transition traces
t1 = time.time()
print("   Backfill: Transition traces...")
sql_tt = """
    INSERT INTO growth.yego_lima_state_transition_trace
    (run_id, snapshot_before, snapshot_after, driver_profile_id,
     transition_type, trigger_reason, policy_version, evidence_json)
    SELECT %(rid)s, %(bd)s, %(ad)s, a.driver_profile_id,
           CASE 
               WHEN b.retention_state != a.retention_state 
               THEN 'RETENTION:' || b.retention_state || '->' || a.retention_state
               ELSE 'PERFORMANCE:' || b.performance_state || '->' || a.performance_state
           END,
           CASE
               WHEN b.churn_risk_flag != a.churn_risk_flag THEN 'churn_risk_flag'
               WHEN b.declining_flag != a.declining_flag THEN 'declining_flag'
               ELSE 'data_delta'
           END,
           'v1', %(ev)s::jsonb
    FROM growth.yango_lima_driver_state_snapshot a
    JOIN growth.yango_lima_driver_state_snapshot b
        ON a.driver_profile_id = b.driver_profile_id
    WHERE a.snapshot_date = %(ad)s AND b.snapshot_date = %(bd)s
      AND (b.retention_state != a.retention_state OR b.performance_state != a.performance_state)
    ON CONFLICT (run_id, driver_profile_id, snapshot_before, snapshot_after) DO NOTHING
"""
cur.execute(sql_tt, {"rid": RID, "ad": AD, "bd": BD, "ev": JSON_EMPTY_OBJ})
tt_inserted = cur.rowcount
tt_time = time.time() - t1
print("   Inserted: " + str(tt_inserted) + " in " + str(round(tt_time, 1)) + "s")

# ── TASK 3-4: RECONCILIATION ──
print("\n3. RECONCILIATION")
cur.execute("SELECT COUNT(*) FROM growth.yango_lima_prioritized_opportunity_daily WHERE opportunity_date = %(d)s", {"d": AD})
dt_expected = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id = %(r)s", {"r": RID})
dt_actual = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) FROM growth.yango_lima_driver_state_snapshot a
    JOIN growth.yango_lima_driver_state_snapshot b ON a.driver_profile_id = b.driver_profile_id
    WHERE a.snapshot_date = %(ad)s AND b.snapshot_date = %(bd)s
      AND (b.retention_state != a.retention_state OR b.performance_state != a.performance_state)
""", {"ad": AD, "bd": BD})
tt_expected = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM growth.yego_lima_state_transition_trace WHERE run_id = %(r)s", {"r": RID})
tt_actual = cur.fetchone()[0]

print("   Decision: " + str(dt_actual) + "/" + str(dt_expected) + " (" + str(100*dt_actual//max(1,dt_expected)) + "%)")
print("   Transition: " + str(tt_actual) + "/" + str(tt_expected) + " (" + str(100*tt_actual//max(1,tt_expected)) + "%)")

# ── TASK 5: IDEMPOTENCY ──
print("\n4. IDEMPOTENCY")
cur.execute(sql_dt, {"rid": RID, "d": AD, "ev": JSON_EMPTY_OBJ})
dt_rerun = cur.rowcount
cur.execute(sql_tt, {"rid": RID, "ad": AD, "bd": BD, "ev": JSON_EMPTY_OBJ})
tt_rerun = cur.rowcount
print("   Decision re-run: " + str(dt_rerun) + " new (should be 0)")
print("   Transition re-run: " + str(tt_rerun) + " new (should be 0)")

# ── TASK 6: NULL AUDIT ──
print("\n5. NULL AUDIT")
checks = [
    ("selected_program NULL", "SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id = %(r)s AND selected_program_code IS NULL"),
    ("selection_reason NULL", "SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id = %(r)s AND selection_reason IS NULL"),
    ("policy_version NULL", "SELECT COUNT(*) FROM growth.yego_lima_program_decision_trace WHERE run_id = %(r)s AND policy_version IS NULL"),
    ("trigger_reason NULL", "SELECT COUNT(*) FROM growth.yego_lima_state_transition_trace WHERE run_id = %(r)s AND trigger_reason IS NULL"),
]
for label, sql in checks:
    cur.execute(sql, {"r": RID})
    print("   " + label + ": " + str(cur.fetchone()[0]))

# ── TASK 7: ORPHAN AUDIT ──
print("\n6. ORPHAN AUDIT")
cur.execute("""
    SELECT COUNT(*) FROM growth.yango_lima_prioritized_opportunity_daily p
    WHERE p.opportunity_date = %(d)s
    AND NOT EXISTS (SELECT 1 FROM growth.yego_lima_program_decision_trace t
        WHERE t.driver_profile_id = p.driver_profile_id AND t.run_id = %(r)s)
""", {"d": AD, "r": RID})
orphan_dt = cur.fetchone()[0]
print("   Prioritized without decision trace: " + str(orphan_dt))

# ── SUMMARY ──
total_time = time.time() - t0
print("\n" + "=" * 60)
print("VERDICT")
print("=" * 60)
print("   Decision traces: " + str(dt_actual) + "/" + str(dt_expected))
print("   Transition traces: " + str(tt_actual) + "/" + str(tt_expected))
print("   Idempotent: " + ("YES" if dt_rerun == 0 and tt_rerun == 0 else "NO"))
print("   Orphans: " + str(orphan_dt))
print("   Total time: " + str(round(total_time, 1)) + "s")
all_pass = dt_actual > 0 and tt_actual > 0 and dt_rerun == 0 and orphan_dt == 0
print("   TRACE BACKFILL: " + ("CERTIFIED" if all_pass else "NEEDS REVIEW"))
print("=" * 60)

cur.close()
conn.close()
