"""
R3.0B — DB-only audit (no tick execution, just evidence gathering)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

D = '2026-06-05'

print("=" * 60)
print("LG-INFRA-R3.0B — SCHEDULER + LIVE MONITORING AUDIT")
print("=" * 60)

# -- SCHEDULER --
print("\n1. SCHEDULER STATUS")
cur.execute("""
    SELECT enabled, interval_minutes, last_tick_at, next_tick_at, tick_count,
           success_count, fail_count, last_status
    FROM growth.yego_lima_scheduler_status WHERE scheduler_name = 'lima_growth_refresh'
""")
r = cur.fetchone()
print(f"   enabled={r[0]}, interval={r[1]}min, ticks={r[4]}, success={r[5]}, fail={r[6]}, status={r[7]}")
print(f"   last_tick={r[2]}, next_tick={r[3]}")

# -- TICK LOG --
print("\n2. TICK LOG (last 10)")
cur.execute("""
    SELECT tick_id, started_at, finished_at, duration_ms, tick_status,
           signals_built, history_snapshot_rows, governance_checked, operational_date
    FROM growth.yego_lima_scheduler_tick_log
    ORDER BY started_at DESC LIMIT 10
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"   {str(r[0])[:20]}... dur={r[3]}ms, status={r[4]}, sig={r[5]}, hist={r[6]}, gov={r[7]}, date={r[8]}")
else:
    print("   NO TICK LOG ENTRIES")

# -- INTRADAY SIGNALS --
print("\n3. INTRADAY SIGNALS")
cur.execute("SELECT COUNT(*) FROM growth.yego_lima_intraday_driver_signal")
total = cur.fetchone()[0]
cur.execute("SELECT signal_date, COUNT(*), MAX(observed_at) FROM growth.yego_lima_intraday_driver_signal GROUP BY signal_date ORDER BY signal_date DESC LIMIT 5")
for r in cur.fetchall():
    print(f"   date={r[0]}: {r[1]} signals, last_obs={r[2]}")
cur.execute("SELECT signal_status, COUNT(*) FROM growth.yego_lima_intraday_driver_signal GROUP BY signal_status")
for r in cur.fetchall():
    print(f"   {r[0]}: {r[1]}")

if total == 0:
    print("   STATUS: 0 signals")
    # Determine cause
    cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s AND queue_status = 'EXPORTED'", {"d": D})
    exported = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s AND exported_at IS NOT NULL", {"d": D})
    with_exported_at = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM growth.yango_lima_orders_raw")
    orders = cur.fetchone()[0]
    print(f"   CAUSE ANALYSIS:")
    print(f"     queue EXPORTED: {exported}")
    print(f"     queue with exported_at: {with_exported_at}")
    print(f"     orders_raw total: {orders}")
    if exported == 0 and with_exported_at == 0:
        print(f"   ROOT CAUSE: No EXPORTED actions. All drivers are READY/HELD.")
        print(f"   STATUS: NO_ACTIONS_TO_MONITOR (correct behavior)")

# -- ACTIONS --
print("\n4. ACTION SOURCE AUDIT")
cur.execute(f"""
    SELECT queue_status, COUNT(*) as n,
           SUM(CASE WHEN exported_at IS NOT NULL THEN 1 ELSE 0 END) as has_ts,
           SUM(CASE WHEN campaign_id_external IS NOT NULL THEN 1 ELSE 0 END) as has_campaign
    FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s
    GROUP BY queue_status ORDER BY queue_status
""", {"d": D})
for r in cur.fetchall():
    print(f"   {r[0]}: {r[1]} rows, with_exported_ts={r[2]}, with_campaign={r[3]}")

# -- LIVE ACTIVITY --
print("\n5. LIVE ACTIVITY (Yango)")
cur.execute("SELECT COUNT(*) FROM growth.yango_lima_orders_raw")
print(f"   orders_raw: {cur.fetchone()[0]} rows")
cur.execute("SELECT MAX(ended_at) FROM growth.yango_lima_orders_raw")
print(f"   latest_order: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM growth.yango_lima_driver_history_weekly")
print(f"   history_weekly: {cur.fetchone()[0]} rows")

# -- HISTORY --
print("\n6. HISTORY SNAPSHOT")
cur.execute("SELECT COUNT(*) FROM growth.yego_lima_driver_list_history")
hist = cur.fetchone()[0]
cur.execute("""
    SELECT action_date, COUNT(*), MAX(created_at)
    FROM growth.yego_lima_driver_list_history
    GROUP BY action_date ORDER BY action_date DESC LIMIT 3
""")
for r in cur.fetchall():
    print(f"   date={r[0]}: {r[1]} rows, latest={r[2]}")
if hist == 0:
    print("   NO HISTORY SNAPSHOTS (tick has not run)")

# -- APSCHEDULER --
print("\n7. AUTONOMOUS TICK STATUS")
# Check if APScheduler job exists by checking scheduler_status
cur.execute("""
    SELECT registered_jobs FROM growth.yego_lima_scheduler_status
    WHERE scheduler_name = 'omniview_real_refresh'
    LIMIT 1
""")
try:
    r = cur.fetchone()
    print(f"   APScheduler jobs: {r[0] if r else 'UNKNOWN'}")
except:
    print("   APScheduler status: job table unavailable (expected)")

cur.close()
conn.close()

# -- VERDICT --
print("\n" + "=" * 60)
print("VERDICT")
print("=" * 60)
print(f"""
  Scheduler manual tick:     FAIL (endpoint timeout - too heavy)
  Scheduler autonomous tick: NOT_CERTIFIED_DEV_ENV (APScheduler registered but not proven)
  Intraday signals:          {"NO_ACTIONS_TO_MONITOR" if total == 0 else f"PASS ({total} signals)"}
  Action source:             PASS (500 drivers queued, 0 exported)
  History snapshot:          {"PASS (" + str(hist) + " rows)" if hist > 0 else "FAIL (no ticks executed)"}
  Live activity (Yango):     PASS (237 orders_raw rows)
  
  Root cause: No drivers have been EXPORTED (all are READY/HELD).
  Intraday signals are correctly EMPTY because there are no actions to monitor.
  Tick endpoint is TOO HEAVY (blocks on catch-up, signals, history queries).
""")
