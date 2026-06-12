"""Phase 5 Row Count Validation — Correct table names"""
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

DATES = ['2026-06-03', '2026-06-04', '2026-06-05']

print("=" * 60)
print("ROW COUNT VALIDATION (Correct Table Names)")
print("=" * 60)

checks = [
    ("eligible_universe", "growth.yango_lima_eligible_universe_daily", "date"),
    ("driver_360_daily", "growth.yango_lima_driver_360_daily", "date"),
    ("driver_state_snapshot", "growth.yango_lima_driver_state_snapshot", "snapshot_date"),
    ("program_eligibility", "growth.yango_lima_program_eligibility_daily", "eligibility_date"),
    ("daily_opportunity_list", "growth.yango_lima_daily_opportunity_list", "opportunity_date"),
    ("prioritized_opportunity", "growth.yango_lima_prioritized_opportunity_daily", "opportunity_date"),
    ("driver_segments", "growth.yango_lima_driver_segment_snapshot", "snapshot_date"),
]

all_ok = True
for label, table, col in checks:
    print(f"\n{label} ({table}):")
    for d in DATES:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = %(d)s", {"d": d})
            cnt = cur.fetchone()[0]
            status = "OK" if cnt > 0 else "WARN"
            if cnt == 0:
                all_ok = False
            print(f"  {d}: {cnt:>8} [{status}]")
        except Exception as e:
            print(f"  {d}: ERROR - {str(e)[:100]}")
            all_ok = False

print(f"\nAll essential tables have >0 rows: {all_ok}")

# Check serving facts
print("\n--- Serving Facts ---")
cur.execute("SELECT fact_date, fact_type, generated_at FROM growth.yego_lima_serving_fact ORDER BY fact_date DESC, fact_type LIMIT 20")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"  date={r[0]}, type={r[1]}, generated={r[2]}")
else:
    print("  NO SERVING FACTS FOUND for any date")

# Check serving fact table columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'growth' AND table_name = 'yego_lima_serving_fact'")
print(f"  serving_fact columns: {[r[0] for r in cur.fetchall()]}")

# Check latest operational date
cur.execute("SELECT MAX(operational_data_date) FROM growth.yego_lima_refresh_run_log WHERE status = 'SUCCESS'")
latest_refresh = cur.fetchone()[0]
print(f"\nLatest successful refresh run log: {latest_refresh}")

cur.execute("SELECT operational_data_date, status, started_at FROM growth.yego_lima_refresh_run_log ORDER BY started_at DESC LIMIT 5")
for r in cur.fetchall():
    print(f"  date={r[0]}, status={r[1]}, started={r[2]}")

cur.close()
conn.close()
print("\nDone.")
