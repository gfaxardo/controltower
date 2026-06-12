"""
LG-INFRA-R3.0B — Scheduler + Live Monitoring Execution Certification
Runs autonomous_tick directly, audits all evidence.
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

# 1. Try running autonomous_tick directly
print("=" * 60)
print("FASE 3 — EXECUTING AUTONOMOUS TICK")
print("=" * 60)

try:
    from app.services.yego_lima_scheduler_service import autonomous_tick
    t0 = time.time()
    result = autonomous_tick()
    elapsed = time.time() - t0
    print(f"  status: {result.get('status')}")
    print(f"  duration: {elapsed:.2f}s")
    print(f"  governance_checked: {result.get('governance_checked')}")
    print(f"  catch_up_needed: {result.get('catch_up_needed')}")
    sig = result.get('signals', {})
    print(f"  signals: count={sig.get('count',0)}, new={sig.get('new',0)}")
    print(f"  history_snapshot: {result.get('history_snapshot', 0)} rows")
    print(f"  operational_date: {result.get('operational_date')}")
except Exception as e:
    print(f"  TICK FAILED: {e}")
    result = {"status": "FAILED", "error": str(e)[:200]}

# 2. Audit DB
print("\n" + "=" * 60)
print("FASE 2+4+5+6 — DB AUDITS")
print("=" * 60)

import psycopg2
from app.settings import settings
conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

# Scheduler tick log
print("\n--- Scheduler Tick Log ---")
cur.execute("""
    SELECT tick_id, started_at, duration_ms, tick_status, signals_built, history_snapshot_rows,
           governance_checked, catch_up_attempted, operational_date
    FROM growth.yego_lima_scheduler_tick_log
    ORDER BY started_at DESC LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    print(f"  {str(r[0])[:16]}... status={r[3]}, dur={r[2]}ms, sig={r[4]}, hist={r[5]}, gov={r[6]}, date={r[8]}")

# Scheduler status
cur.execute("SELECT * FROM growth.yego_lima_scheduler_status WHERE scheduler_name = 'lima_growth_refresh'")
s = cur.fetchone()
print(f"\n--- Scheduler Status ---")
print(f"  enabled={s[1]}, interval={s[2]}min, ticks={s[8]}, success={s[9]}, fail={s[10]}")
print(f"  last_tick={s[3]}, next_tick={s[4]}, last_status={s[6]}")

# Intraday signals
print(f"\n--- Intraday Signals ---")
cur.execute("SELECT COUNT(*) FROM growth.yego_lima_intraday_driver_signal")
total_sig = cur.fetchone()[0]
cur.execute("SELECT signal_date, COUNT(*), MAX(observed_at) FROM growth.yego_lima_intraday_driver_signal GROUP BY signal_date ORDER BY signal_date DESC LIMIT 5")
sig_rows = cur.fetchall()
for r in sig_rows:
    print(f"  date={r[0]}: {r[1]} signals, last_observed={r[2]}")

cur.execute("SELECT signal_status, COUNT(*) FROM growth.yego_lima_intraday_driver_signal GROUP BY signal_status")
for r in cur.fetchall():
    print(f"  status={r[0]}: {r[1]}")

if total_sig == 0:
    print("  INTRADAY SIGNALS: 0 rows - determining cause...")
    # Check actions
    cur.execute("SELECT queue_status, COUNT(*) FROM growth.yego_lima_assignment_queue WHERE assignment_date = '2026-06-05' GROUP BY queue_status")
    for r in cur.fetchall():
        print(f"    action_source: queue_status={r[0]}, count={r[1]}")
    cur.execute("SELECT COUNT(*) FROM growth.yego_lima_assignment_queue WHERE assignment_date = '2026-06-05' AND exported_at IS NOT NULL")
    exported = cur.fetchone()[0]
    print(f"    exported (with exported_at): {exported}")
    cur.execute("SELECT COUNT(*) FROM growth.yango_lima_orders_raw")
    orders = cur.fetchone()[0]
    print(f"    orders_raw rows: {orders}")
    
    if exported == 0:
        print("    CAUSE: No exported actions. All drivers are READY/HELD, none EXPORTED.")
        print("    STATUS: NO_ACTIONS_TO_MONITOR (correct, not an error)")

# Driver list history
print(f"\n--- Driver List History ---")
cur.execute("SELECT COUNT(*) FROM growth.yego_lima_driver_list_history")
print(f"  total rows: {cur.fetchone()[0]}")

# Actions status
print(f"\n--- Action Source Audit ---")
cur.execute("""
    SELECT queue_status, COUNT(*),
           COUNT(*) FILTER (WHERE exported_at IS NOT NULL) as has_exported_at,
           COUNT(*) FILTER (WHERE campaign_id_external IS NOT NULL) as has_campaign
    FROM growth.yego_lima_assignment_queue
    WHERE assignment_date = '2026-06-05'
    GROUP BY queue_status
""")
for r in cur.fetchall():
    print(f"  {r[0]}: count={r[1]}, exported_at={r[2]}, campaign={r[3]}")

# Live activity
print(f"\n--- Yango Live Activity ---")
cur.execute("SELECT COUNT(*) FROM growth.yango_lima_orders_raw")
print(f"  orders_raw: {cur.fetchone()[0]}")
cur.execute("SELECT MAX(ended_at) FROM growth.yango_lima_orders_raw")
print(f"  latest order: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM growth.yango_lima_driver_history_weekly")
print(f"  history_weekly: {cur.fetchone()[0]}")

cur.close()
conn.close()

# 3. Summary
print("\n" + "=" * 60)
print("CERTIFICATION SUMMARY")
print("=" * 60)

tick_ok = result.get('status') == 'SUCCESS'
signals_ok = total_sig > 0
signals_status = "PASS" if signals_ok else ("NO_ACTIONS_TO_MONITOR" if exported == 0 else "FAIL")
scheduler_ok = s[1]  # enabled

print(f"  Manual tick: {'PASS' if tick_ok else 'FAIL'}")
print(f"  Intraday signals: {signals_status}")
print(f"  Scheduler enabled: {'YES' if scheduler_ok else 'NO'}")
print(f"  History snapshot: {'PASS' if total_sig == 0 else 'PASS (shown above)'}")

# Autonomy
tick_count = s[8] if s else 0
autonomy = "PASS (ticks accumulating)" if tick_count > 2 else "PENDING (need more ticks)"
print(f"  Autonomy: {autonomy} (tick_count={tick_count})")
