"""
186 — ME-1: Movement Tracking

Creates:
- growth.yego_lima_movement_tracking

Tracks state transitions (lifecycle_state) before and after contact.
NO causalidad. NO ROI. NO attribution.

down_revision: 185_yego_lima_impact_tracking
"""

from alembic import op

revision = "186_yego_lima_movement_tracking"
down_revision = "185_yego_lima_impact_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_movement_tracking (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),

            driver_id               TEXT NOT NULL,
            campaign_id_external    TEXT NULL,
            assignment_queue_id     uuid NULL,
            impact_tracking_id      uuid NULL,

            from_state              TEXT NULL,
            to_state                TEXT NULL,

            movement_type           TEXT NULL,
            movement_direction      TEXT NULL,
            movement_status         TEXT NOT NULL DEFAULT 'PENDING',

            movement_date           DATE NULL,

            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_movement_driver
        ON growth.yego_lima_movement_tracking (driver_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_movement_campaign
        ON growth.yego_lima_movement_tracking (campaign_id_external);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_movement_from
        ON growth.yego_lima_movement_tracking (from_state);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_movement_to
        ON growth.yego_lima_movement_tracking (to_state);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_movement_type
        ON growth.yego_lima_movement_tracking (movement_type);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_movement_date
        ON growth.yego_lima_movement_tracking (movement_date);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_movement_tracking;")
