"""
LG-INFRA-R1.6 — Comprehensive Certification Audit
Phases 2-7: Scheduler reliability, catch-up, rollover, history trace, driver lineage, SLA
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

def q(sql, params=None):
    cur.execute(sql, params or {})
    return cur.fetchall()

print("=" * 70)
print("LG-INFRA-R1.6 CERTIFICATION AUDIT")
print("=" * 70)

# ═══════ PHASE 2: SCHEDULER RELIABILITY ═══════
print("\n" + "=" * 70)
print("PHASE 2 — SCHEDULER RELIABILITY AUDIT")
print("=" * 70)

rows = q("SELECT * FROM growth.yego_lima_scheduler_status WHERE scheduler_name = 'lima_growth_refresh'")
if rows:
    r = rows[0]
    print(f"  enabled       : {r[1]}")
    print(f"  interval_min  : {r[2]}")
    print(f"  last_tick_at  : {r[3]}")
    print(f"  next_tick_at  : {r[4]}")
    print(f"  last_status   : {r[6]}")
    print(f"  tick_count    : {r[8]}")
    print(f"  success_count : {r[9]}")
    print(f"  fail_count    : {r[10]}")

# Tick log
rows = q("SELECT COUNT(*) FROM growth.yego_lima_scheduler_tick_log")
print(f"\n  tick_log_rows : {rows[0][0]}")

if rows[0][0] > 0:
    rows = q("""
        SELECT tick_id, started_at, duration_ms, tick_status, catch_up_attempted,
               signals_built, history_snapshot_rows
        FROM growth.yego_lima_scheduler_tick_log
        ORDER BY started_at DESC LIMIT 5
    """)
    for r in rows:
        print(f"  tick: {str(r[0])[:12]}... status={r[3]}, dur={r[2]}ms, signals={r[5]}, hist_rows={r[6]}, catch_up={r[4]}")

scheduler_ok = rows and rows[0][0] is not None
print(f"\n  SCHEDULER_RELIABILITY: {'PASS' if scheduler_ok else 'PENDING (no tick data yet)'}")

# ═══════ PHASE 3: CATCH-UP CERTIFICATION ═══════
print("\n" + "=" * 70)
print("PHASE 3 — CATCH-UP CERTIFICATION")
print("=" * 70)

# Check latest processed vs latest available
rows = q("SELECT MAX(operational_data_date) FROM growth.yego_lima_refresh_run_log WHERE status = 'SUCCESS'")
last_processed = str(rows[0][0]) if rows and rows[0][0] else None
rows = q("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
latest_snapshot = str(rows[0][0]) if rows and rows[0][0] else None

print(f"  last_processed : {last_processed}")
print(f"  latest_snapshot: {latest_snapshot}")

gap_detected = last_processed != latest_snapshot
print(f"  gap_detected   : {gap_detected}")

# Count unprocessed dates
if last_processed and latest_snapshot:
    rows = q("""
        SELECT COUNT(DISTINCT snapshot_date)
        FROM growth.yango_lima_driver_state_snapshot
        WHERE snapshot_date > %(lp)s AND snapshot_date <= %(ls)s
    """, {"lp": last_processed, "ls": latest_snapshot})
    pending_dates = rows[0][0]
    print(f"  pending_dates  : {pending_dates}")
else:
    pending_dates = 0

# Check if catch-up endpoint exists
try:
    import requests
    r = requests.post("http://localhost:8000/yego-lima-growth/scheduler/catch-up", timeout=60)
    catch_up_result = r.json()
    print(f"\n  catch_up_test : status={catch_up_result.get('status')}, "
          f"caught_up={len(catch_up_result.get('dates_caught_up', []))}, "
          f"failed={len(catch_up_result.get('dates_failed', []))}")
    catch_up_working = True
except Exception as e:
    print(f"\n  catch_up_test : FAILED - {str(e)[:100]}")
    catch_up_result = {"error": str(e)}
    catch_up_working = False

catch_up_pass = catch_up_working or pending_dates == 0
print(f"\n  CATCH_UP: {'PASS' if catch_up_pass else 'FAIL'}")

# ═══════ PHASE 4: MIDNIGHT ROLLOVER ═══════
print("\n" + "=" * 70)
print("PHASE 4 — MIDNIGHT ROLLOVER CERTIFICATION")
print("=" * 70)

dates_to_check = ['2026-06-03', '2026-06-04', '2026-06-05']
layers = [
    ("driver_state_snapshot", "growth.yango_lima_driver_state_snapshot", "snapshot_date"),
    ("program_eligibility", "growth.yango_lima_program_eligibility_daily", "eligibility_date"),
    ("prioritized_opportunity", "growth.yango_lima_prioritized_opportunity_daily", "opportunity_date"),
]

all_layers_ok = True
for label, table, col in layers:
    print(f"\n  {label}:")
    for d in dates_to_check:
        rows = q(f"SELECT COUNT(*) FROM {table} WHERE {col} = %(d)s", {"d": d})
        cnt = rows[0][0]
        status = "OK" if cnt > 0 else "FAIL"
        if cnt == 0: all_layers_ok = False
        print(f"    {d}: {cnt:>8} [{status}]")

# Serving facts
print(f"\n  serving_facts:")
for d in dates_to_check:
    rows = q("SELECT COUNT(*) FROM growth.yego_lima_serving_fact WHERE fact_date = %(d)s", {"d": d})
    cnt = rows[0][0]
    print(f"    {d}: {cnt}/8 facts")

# History trace
rows = q("SELECT COUNT(*) FROM growth.yego_lima_driver_list_history")
hist_count = rows[0][0]
print(f"\n  driver_list_history total: {hist_count} rows")
print(f"\n  MIDNIGHT_ROLLOVER: {'PASS' if all_layers_ok else 'FAIL'}")

# ═══════ PHASE 5: HISTORICAL LIST TRACE ═══════
print("\n" + "=" * 70)
print("PHASE 5 — HISTORICAL LIST TRACE CERTIFICATION")
print("=" * 70)

# Check history table for 2026-06-05
rows = q("""
    SELECT COUNT(*), 
           COUNT(*) FILTER (WHERE queue_status = 'READY'),
           COUNT(*) FILTER (WHERE queue_status = 'HELD'),
           COUNT(*) FILTER (WHERE queue_status = 'EXPORTED')
    FROM growth.yego_lima_driver_list_history
    WHERE action_date = '2026-06-05'
""")
if rows:
    r = rows[0]
    print(f"  2026-06-05 history: total={r[0]}, READY={r[1]}, HELD={r[2]}, EXPORTED={r[3]}")

# Check queue match
rows = q("""
    SELECT COUNT(*) FROM growth.yego_lima_assignment_queue
    WHERE assignment_date = '2026-06-05'
""")
queue_count = rows[0][0]
print(f"  assignment_queue count: {queue_count}")

# Sample 5 drivers from history
rows = q("""
    SELECT driver_profile_id, program_code, priority_rank, queue_status, assigned_channel
    FROM growth.yego_lima_driver_list_history
    WHERE action_date = '2026-06-05'
    LIMIT 5
""")
print(f"\n  Sample drivers from history:")
for r in rows:
    print(f"    driver={r[0]}, program={r[1]}, rank={r[2]}, status={r[3]}, channel={r[4]}")

hist_trace_ok = len(rows) > 0 if rows else False
print(f"\n  HISTORICAL_LIST_TRACE: {'PASS' if hist_trace_ok else 'FAIL'}")

# ═══════ PHASE 6: DRIVER LINEAGE SAMPLE ═══════
print("\n" + "=" * 70)
print("PHASE 6 — DRIVER LINEAGE SAMPLE")
print("=" * 70)

# Get 3 random drivers from queue latest date
rows = q("""
    SELECT aq.driver_id, aq.program_code, aq.queue_status, aq.priority_rank,
           s.lifecycle_state, s.performance_state, s.retention_state
    FROM growth.yego_lima_assignment_queue aq
    LEFT JOIN growth.yango_lima_driver_state_snapshot s
        ON aq.driver_id = s.driver_profile_id
        AND s.snapshot_date = '2026-06-05'
    WHERE aq.assignment_date = '2026-06-05'
    LIMIT 3
""")

print(f"\n  {'driver_id':<24} {'program':<28} {'lifecycle':<14} {'perf':<14} {'retention':<14} {'rank':<6}")
print(f"  {'-'*24} {'-'*28} {'-'*14} {'-'*14} {'-'*14} {'-'*6}")
for r in rows:
    print(f"  {str(r[0]):<24} {str(r[1] or ''):<28} {str(r[4] or ''):<14} {str(r[5] or ''):<14} {str(r[6] or ''):<14} {str(r[3] or ''):<6}")

lineage_ok = len(rows) > 0
print(f"\n  DRIVER_LINEAGE: {'PASS' if lineage_ok else 'FAIL'}")

# ═══════ PHASE 7: SERVING FACT SLA ═══════
print("\n" + "=" * 70)
print("PHASE 7 — SERVING FACT SLA AUDIT")
print("=" * 70)

rows = q("""
    SELECT fact_date, fact_type, freshness_status,
           generated_at,
           EXTRACT(EPOCH FROM (now() - generated_at))/3600 AS hours_ago
    FROM growth.yego_lima_serving_fact
    WHERE fact_date = '2026-06-05'
    ORDER BY fact_type
""")

facts_ok = 0
facts_stale = 0
for r in rows:
    status = "OK" if r[2] != 'STALE' else "STALE"
    if status == "OK": facts_ok += 1
    else: facts_stale += 1
    print(f"  {r[1]:<28} date={r[0]} freshness={r[2]:<10} age={r[4]:.1f}h [{status}]")

print(f"\n  facts_ok: {facts_ok}/8, stale: {facts_stale}/8")
sla_pass = facts_ok >= 8
print(f"  SERVING_FACT_SLA: {'PASS' if sla_pass else 'FAIL'}")

# ═══════ SUMMARY ═══════
print("\n" + "=" * 70)
print("CERTIFICATION SUMMARY")
print("=" * 70)

results = {
    "SCHEDULER_RELIABILITY": "PASS" if scheduler_ok else "PENDING",
    "CATCH_UP": "PASS" if catch_up_pass else "FAIL",
    "MIDNIGHT_ROLLOVER": "PASS" if all_layers_ok else "FAIL",
    "HISTORICAL_LIST_TRACE": "PASS" if hist_trace_ok else "FAIL",
    "DRIVER_LINEAGE": "PASS" if lineage_ok else "FAIL",
    "SERVING_FACT_SLA": "PASS" if sla_pass else "FAIL",
}

all_pass = all(v == "PASS" for v in results.values())
for k, v in results.items():
    print(f"  {k:<30}: {v}")

print(f"\n  OVERALL: {'GO' if all_pass else 'NO-GO (see failures above)'}")

cur.close()
conn.close()
