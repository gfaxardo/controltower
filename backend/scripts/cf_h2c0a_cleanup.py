"""CF-H2C.0A: Clean zombie ingestion runs and prepare for re-ingestion."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db

with get_db() as conn:
    cur = conn.cursor()

    cur.execute("""
        SELECT run_id, park_id, endpoint_group, status, started_at
        FROM raw_yango.api_ingestion_run
        WHERE status = 'running'
          AND started_at < NOW() - INTERVAL '1 hour'
        ORDER BY started_at
    """)
    zombies = cur.fetchall()
    print(f"Zombie runs found: {len(zombies)}")
    for z in zombies:
        print(f"  run={z[0][:16]} park={z[1][:8]} endpoint={z[2]} started={z[4]}")

    cur.execute("""
        UPDATE raw_yango.api_ingestion_run
        SET status = 'failed',
            notes = COALESCE(notes, '') || ' [zombie cleanup CF-H2C.0A]'
        WHERE status = 'running'
          AND started_at < NOW() - INTERVAL '1 hour'
    """)
    cleaned = cur.rowcount
    conn.commit()
    print(f"Cleaned: {cleaned} zombie runs marked as failed")

    # Verify
    cur.execute("SELECT COUNT(*) FROM raw_yango.api_ingestion_run WHERE status = 'running'")
    remaining = cur.fetchone()[0]
    print(f"Remaining running runs: {remaining}")

    cur.close()
