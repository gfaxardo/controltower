"""
207 — CF-H2D: Extend ingestion_watermark + Scheduler Run Log

Extends raw_yango.ingestion_watermark with last_event_at column.
Creates ops.yango_shadow_scheduler_run_log for scheduler cycle tracking.

down_revision: 206_merge_cf_h2c1_heads
"""

from alembic import op

revision = "207_cf_h2d_scheduler_watermark"
down_revision = "206_merge_cf_h2c1_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE raw_yango.ingestion_watermark
        ADD COLUMN IF NOT EXISTS last_event_at TIMESTAMPTZ;
    """)

    op.execute("""
        ALTER TABLE raw_yango.ingestion_watermark
        ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMPTZ;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_shadow_scheduler_run_log (
            id                  BIGSERIAL PRIMARY KEY,
            cycle_id            TEXT NOT NULL,
            park_id             TEXT NOT NULL,
            endpoint_group      TEXT NOT NULL,
            cycle_started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            cycle_finished_at   TIMESTAMPTZ,
            runtime_seconds     NUMERIC(10,2),

            -- Incremental window
            watermark_before    TIMESTAMPTZ,
            safety_overlap_min  INT DEFAULT 15,
            query_from          TIMESTAMPTZ,
            query_to            TIMESTAMPTZ,

            -- Results
            pages_fetched       INT DEFAULT 0,
            records_fetched     INT DEFAULT 0,
            records_inserted    INT DEFAULT 0,
            records_skipped     INT DEFAULT 0,
            errors_count        INT DEFAULT 0,

            -- Freshness
            last_event_at       TIMESTAMPTZ,
            freshness_seconds   NUMERIC(10,2),

            -- Status
            status              TEXT NOT NULL DEFAULT 'running',
            error_message       TEXT,
            notes               TEXT,

            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ssrl_cycle
        ON ops.yango_shadow_scheduler_run_log (cycle_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ssrl_park_endpoint
        ON ops.yango_shadow_scheduler_run_log (park_id, endpoint_group, cycle_started_at);
    """)


def downgrade():
    op.execute("ALTER TABLE raw_yango.ingestion_watermark DROP COLUMN IF EXISTS last_event_at;")
    op.execute("ALTER TABLE raw_yango.ingestion_watermark DROP COLUMN IF EXISTS last_run_at;")
    op.execute("DROP TABLE IF EXISTS ops.yango_shadow_scheduler_run_log;")
