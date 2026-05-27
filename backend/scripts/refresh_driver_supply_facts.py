"""
Refresh Driver Supply Facts — SH2/SH3
Refreshes all 5 materialized views sequentially.
"""
import time, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db

FACTS = [
    "ops.driver_weekly_segment_fact",
    "ops.driver_segment_migration_fact",
    "ops.driver_operational_priority_fact",
    "ops.driver_supply_overview_weekly_fact",
    "ops.driver_serving_freshness_fact",
]

def run_refresh():
    print("=" * 70)
    print("DRIVERS SERVING FACTS REFRESH")
    print("=" * 70)
    t_total = time.time()

    try:
        with get_db() as conn:
            cur = conn.cursor()
            for fact in FACTS:
                t0 = time.time()
                try:
                    cur.execute("SET LOCAL statement_timeout = '120000'")
                    cur.execute(f"REFRESH MATERIALIZED VIEW {fact}")
                    cur.execute(f"SELECT COUNT(*) FROM {fact}")
                    cnt = cur.fetchone()[0]
                    dur = round(time.time() - t0, 2)
                    print(f"  {fact:<45} rows={cnt:>8,}  {dur}s")
                except Exception as e:
                    print(f"  {fact:<45} FAILED: {str(e)[:120]}")
            conn.commit()

        print("-" * 70)
        print(f"Total: {round(time.time() - t_total, 2)}s")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_refresh()
