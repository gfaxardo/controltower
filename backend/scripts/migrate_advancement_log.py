"""OV2-G.2 — Create ops.refresh_advancement_log table (outcome-based monitoring)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

SQL = """
CREATE TABLE IF NOT EXISTS ops.refresh_advancement_log (
    id BIGSERIAL PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    layer_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    before_max_period TEXT,
    after_max_period TEXT,
    before_row_count INTEGER,
    after_row_count INTEGER,
    advanced_periods INTEGER DEFAULT 0,
    advanced_rows INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'RUNNING',
    git_hash TEXT,
    runtime_hash TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_adv_log_pipeline ON ops.refresh_advancement_log(pipeline_name, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_adv_log_layer ON ops.refresh_advancement_log(layer_name, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_adv_log_status ON ops.refresh_advancement_log(status, started_at DESC);
"""

with get_db() as conn:
    cur = conn.cursor()
    try:
        cur.execute("CREATE SCHEMA IF NOT EXISTS ops")
        cur.execute(SQL)
        conn.commit()
        print("ops.refresh_advancement_log created")
        cur.execute("SELECT COUNT(*) FROM ops.refresh_advancement_log")
        print(f"Existing rows: {cur.fetchone()[0]}")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
    finally:
        cur.close()
