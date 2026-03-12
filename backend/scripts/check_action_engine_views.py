"""
One-off preflight: check that Action Engine and Top Driver Behavior views exist in DB.
Run from backend: python scripts/check_action_engine_views.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

EXPECTED = [
    "ops.v_action_engine_driver_base",
    "ops.v_action_engine_cohorts_weekly",
    "ops.v_action_engine_recommendations_weekly",
    "ops.v_top_driver_behavior_weekly",
    "ops.v_top_driver_behavior_benchmarks",
    "ops.v_top_driver_behavior_patterns",
]

def main():
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT table_schema, table_name FROM information_schema.views
            WHERE table_schema = 'ops' AND (
                table_name LIKE 'v_action_engine%%' OR table_name LIKE 'v_top_driver_behavior%%'
            )
            ORDER BY table_name
        """)
        rows = cur.fetchall()
        cur.close()
    found = {r["table_name"] for r in rows}
    print("View existence check (ops schema):")
    for name in EXPECTED:
        short = name.split(".", 1)[1]
        exists = short in found
        print(f"  {name}: {'exists' if exists else 'MISSING'}")
    all_ok = all(n.split(".", 1)[1] in found for n in EXPECTED)
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
