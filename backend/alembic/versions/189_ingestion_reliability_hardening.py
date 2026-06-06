"""
189 — Ingestion Reliability Hardening (OV2-B.6B)

Adds ingestion reliability columns and page checkpoint table.
Columns added to api_ingestion_run:
- heartbeat_at: last heartbeat timestamp
- current_page: current page number being processed
- last_cursor: last pagination cursor seen
- next_cursor: next pagination cursor to fetch
- expected_pages: expected total pages (if known)
- pages_completed: count of completed pages

New table: raw_yango.api_ingestion_page_checkpoint
Tracks per-page progress for reliable resumption.

down_revision: 188_yango_serving_facts_mvs
"""

from alembic import op
import sqlalchemy as sa

revision = "189_ingestion_reliability_hardening"
down_revision = "188_yango_serving_facts_mvs"
branch_labels = None
depends_on = None


def upgrade():
    # ── Add columns to api_ingestion_run ────────────────────
    op.execute("""
        ALTER TABLE raw_yango.api_ingestion_run
        ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS current_page INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS last_cursor TEXT,
        ADD COLUMN IF NOT EXISTS next_cursor TEXT,
        ADD COLUMN IF NOT EXISTS expected_pages INTEGER,
        ADD COLUMN IF NOT EXISTS pages_completed INTEGER DEFAULT 0;
    """)

    # ── Create api_ingestion_page_checkpoint ────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_yango.api_ingestion_page_checkpoint (
            id              SERIAL PRIMARY KEY,
            run_id          TEXT NOT NULL,
            park_id         TEXT NOT NULL,
            endpoint_group  TEXT NOT NULL,
            target_date     DATE NOT NULL,
            partition_key   TEXT,
            page_number     INTEGER NOT NULL,
            cursor_value    TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            records_count   INTEGER DEFAULT 0,
            records_inserted INTEGER DEFAULT 0,
            payload_hash    TEXT,
            started_at      TIMESTAMPTZ,
            finished_at     TIMESTAMPTZ,
            error_message_sanitized TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_page_checkpoint_run_page
        ON raw_yango.api_ingestion_page_checkpoint (run_id, page_number);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_page_checkpoint_status
        ON raw_yango.api_ingestion_page_checkpoint (run_id, status);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS raw_yango.api_ingestion_page_checkpoint;")
    op.execute("""
        ALTER TABLE raw_yango.api_ingestion_run
        DROP COLUMN IF EXISTS heartbeat_at,
        DROP COLUMN IF EXISTS current_page,
        DROP COLUMN IF EXISTS last_cursor,
        DROP COLUMN IF EXISTS next_cursor,
        DROP COLUMN IF EXISTS expected_pages,
        DROP COLUMN IF EXISTS pages_completed;
    """)
