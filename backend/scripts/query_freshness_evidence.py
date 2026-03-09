"""Solo ejecuta las 3 consultas de evidencia SQL (sin correr el audit)."""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT COUNT(*) AS n FROM ops.data_freshness_audit")
        n = cur.fetchone()["n"]
        print("SELECT COUNT(*) FROM ops.data_freshness_audit;")
        print(f"  -> {n}\n")

        cur.execute("""
            SELECT id, dataset_name, source_object, derived_object, grain,
                   source_max_date, derived_max_date, expected_latest_date,
                   lag_days, missing_expected_days, status, alert_reason, checked_at
            FROM ops.data_freshness_audit
            ORDER BY checked_at DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        print("SELECT * FROM ops.data_freshness_audit ORDER BY checked_at DESC LIMIT 20;")
        for r in rows:
            print(f"  {r['dataset_name']} | source_max={r['source_max_date']} derived_max={r['derived_max_date']} expected={r['expected_latest_date']} | status={r['status']} | checked_at={r['checked_at']}")

        cur.execute("""
            SELECT dataset_name, MAX(checked_at) AS last_checked
            FROM ops.data_freshness_audit
            GROUP BY 1
            ORDER BY 1
        """)
        rows2 = cur.fetchall()
        print("\nSELECT dataset_name, MAX(checked_at) FROM ops.data_freshness_audit GROUP BY 1;")
        for r in rows2:
            print(f"  {r['dataset_name']} | {r['last_checked']}")
        cur.close()

if __name__ == "__main__":
    main()
