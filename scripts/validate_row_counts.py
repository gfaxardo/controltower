"""
Phase 5 — Row Count Validation for pipeline recovery dates
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

import psycopg2
from app.settings import settings

conn = psycopg2.connect(
    host=settings.DB_HOST or "localhost",
    port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or "yego_integral",
    user=settings.DB_USER or "",
    password=settings.DB_PASSWORD or "",
    connect_timeout=30,
)
conn.autocommit = True
cur = conn.cursor()

DATES = ["2026-06-03", "2026-06-04", "2026-06-05"]

print("=" * 80)
print("PHASE 5 — ROW COUNT VALIDATION")
print("=" * 80)

queries = [
    ("eligible_universe", "growth.yango_lima_eligible_universe_daily", "date"),
    ("driver_360", "growth.yango_lima_driver_360_daily", "date"),
    ("driver_state_snapshot", "growth.yango_lima_driver_state_snapshot", "snapshot_date"),
    ("program_eligibility", "growth.yango_lima_program_eligibility_daily", "eligibility_date"),
    ("prioritized_opportunities", "growth.yango_lima_prioritized_opportunity_daily", "opportunity_date"),
    ("driver_segments", "growth.yango_lima_driver_segment_snapshot", "snapshot_date"),
]

for label, table, col in queries:
    print(f"\n--- {label} ({table}) ---")
    for d in DATES:
        try:
            cur.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} = %(d)s",
                {"d": d}
            )
            cnt = cur.fetchone()[0]
            status = "OK" if cnt > 0 else "WARN (0 rows)"
            print(f"  {d}: {cnt} rows [{status}]")
        except Exception as e:
            print(f"  {d}: ERROR - {str(e)[:100]}")

# Check raw_yango data
print(f"\n--- raw_yango orders ---")
cur.execute("SELECT COUNT(*) FROM growth.yango_lima_orders_raw")
print(f"  total orders_raw: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM raw_yango.orders_raw")
print(f"  raw_yango.orders_raw: {cur.fetchone()[0]}")

# Check refresh_run_log for pipeline runs
print(f"\n--- Refresh Run Log (last 5) ---")
cur.execute("""
    SELECT operational_data_date, status, started_at, finished_at
    FROM growth.yego_lima_refresh_run_log
    ORDER BY started_at DESC LIMIT 5
""")
for r in cur.fetchall():
    print(f"  date={r[0]}, status={r[1]}, started={r[2]}, finished={r[3]}")

# Check serving facts
print(f"\n--- Serving Facts ---")
cur.execute("""
    SELECT fact_date, COUNT(*), string_agg(fact_type, ', ') as types
    FROM growth.yango_lima_serving_fact
    WHERE fact_date BETWEEN '2026-06-03' AND '2026-06-05'
    GROUP BY fact_date ORDER BY fact_date
""")
for r in cur.fetchall():
    print(f"  date={r[0]}, count={r[1]}, types={r[2]}")

cur.execute("SELECT MAX(fact_date) FROM growth.yango_lima_serving_fact")
latest = cur.fetchone()[0]
print(f"  latest serving fact date: {latest}")

cur.close()
conn.close()
print("\nValidation complete.")
