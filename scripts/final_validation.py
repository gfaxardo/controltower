"""Phase 5+8: Final row count validation + governance check + scheduler status"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2, json
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

DATES = ['2026-06-03', '2026-06-04', '2026-06-05']

print("=" * 60)
print("FINAL ROW COUNT VALIDATION")
print("=" * 60)

checks = [
    ("eligible_universe", "growth.yango_lima_eligible_universe_daily", "date"),
    ("driver_360_daily", "growth.yango_lima_driver_360_daily", "date"),
    ("driver_state_snapshot", "growth.yango_lima_driver_state_snapshot", "snapshot_date"),
    ("program_eligibility", "growth.yango_lima_program_eligibility_daily", "eligibility_date"),
    ("daily_opportunity_list", "growth.yango_lima_daily_opportunity_list", "opportunity_date"),
    ("prioritized_opportunity", "growth.yango_lima_prioritized_opportunity_daily", "opportunity_date"),
]

all_ok = True
for label, table, col in checks:
    print(f"\n{label}:")
    for d in DATES:
        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = %(d)s", {"d": d})
        cnt = cur.fetchone()[0]
        status = "OK" if cnt > 0 else "WARN"
        if cnt == 0: all_ok = False
        print(f"  {d}: {cnt:>6} [{status}]")

# SERVING FACTS
print("\n--- Serving Facts ---")
cur.execute("""
    SELECT fact_date, fact_type, freshness_status, generated_at
    FROM growth.yego_lima_serving_fact
    WHERE fact_date IN ('2026-06-03','2026-06-04','2026-06-05')
    ORDER BY fact_date, fact_type
""")
rows = cur.fetchall()
by_date = {}
for r in rows:
    d = str(r[0])
    by_date.setdefault(d, []).append(r[1])

for d in DATES:
    types = by_date.get(d, [])
    print(f"  {d}: {len(types)}/8 facts - {types[:4]}...")

# SCHEDULER STATUS
print("\n--- Scheduler Status ---")
cur.execute("SELECT * FROM growth.yego_lima_scheduler_status WHERE scheduler_name = 'lima_growth_refresh'")
row = cur.fetchone()
if row:
    print(f"  enabled={row[1]}, interval={row[2]}min, last_tick={row[3]}, next_tick={row[4]}, status={row[6]}, ticks={row[8]}, success={row[9]}, fail={row[10]}")

# REFRESH RUN LOG (latest)
print("\n--- Latest Refresh Runs ---")
cur.execute("""
    SELECT operational_data_date, status, started_at
    FROM growth.yego_lima_refresh_run_log
    ORDER BY started_at DESC LIMIT 3
""")
for r in cur.fetchall():
    print(f"  date={r[0]}, status={r[1]}, started={r[2]}")

# ASSIGNMENT QUEUE
print("\n--- Assignment Queue ---")
cur.execute("""
    SELECT assignment_date, queue_status, COUNT(*)
    FROM growth.yego_lima_assignment_queue
    WHERE assignment_date IN ('2026-06-03','2026-06-04','2026-06-05')
    GROUP BY assignment_date, queue_status
    ORDER BY assignment_date, queue_status
""")
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]}: {r[2]}")

# INTRADAY SIGNALS
print("\n--- Intraday Signals ---")
for d in DATES:
    cur.execute("SELECT COUNT(*) FROM growth.yego_lima_intraday_driver_signal WHERE signal_date = %(d)s", {"d": d})
    print(f"  {d}: {cur.fetchone()[0]} signals")

cur.close()
conn.close()

print(f"\n{'='*60}")
print(f"ALL_ESSENTIAL_ROWS_OK: {all_ok}")
print(f"{'='*60}")
