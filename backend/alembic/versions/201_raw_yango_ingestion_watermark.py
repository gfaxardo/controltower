"""
201 — CF-H2C: Raw Yango Ingestion Watermark

Creates:
- raw_yango.ingestion_watermark

Tracks incremental ingestion progress per park + endpoint_group.
Watermark only advances when a run completes successfully.
Supports resume capability for partial/failed runs.

Shadow mode: does NOT modify any existing tables.
down_revision: 200_yego_lima_driver_taxonomy
"""

from alembic import op

revision = "201_raw_yango_ingestion_watermark"
down_revision = "200_yego_lima_driver_taxonomy"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS raw_yango.ingestion_watermark (
            id                  SERIAL PRIMARY KEY,
            park_id             TEXT NOT NULL,
            endpoint_group      TEXT NOT NULL,
            last_source_date    DATE,
            last_run_id         TEXT,
            last_completed_at   TIMESTAMPTZ,
            records_total       BIGINT DEFAULT 0,
            consecutive_failures INT DEFAULT 0,
            status              TEXT NOT NULL DEFAULT 'active',
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (park_id, endpoint_group)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_wm_park
        ON raw_yango.ingestion_watermark (park_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_wm_status
        ON raw_yango.ingestion_watermark (status);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS raw_yango.ingestion_watermark;")
