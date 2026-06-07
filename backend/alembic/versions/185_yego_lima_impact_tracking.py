"""
185 — IF-1: Impact Foundation Tracking

Creates:
- growth.yego_lima_impact_tracking

Tracks whether contacted drivers returned to operate after contact.
NO revenue. NO ROI. NO attribution.

down_revision: 184_yego_lima_loopcontrol_result_sync
"""

from alembic import op

revision = "185_yego_lima_impact_tracking"
down_revision = "184_yego_lima_loopcontrol_result_sync"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_impact_tracking (
            id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),

            driver_id                   TEXT NOT NULL,
            assignment_queue_id         uuid NULL,
            campaign_id_external        TEXT NULL,

            contact_status              TEXT NULL,
            disposition                 TEXT NULL,
            contact_date                DATE NULL,

            baseline_trips              INTEGER NULL DEFAULT 0,
            baseline_last_trip_at       TIMESTAMPTZ NULL,

            post_contact_trips          INTEGER NULL DEFAULT 0,
            post_contact_last_trip_at   TIMESTAMPTZ NULL,

            impact_status               TEXT NOT NULL DEFAULT 'PENDING_WINDOW',

            measured_at                 TIMESTAMPTZ NULL,
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_impact_driver
        ON growth.yego_lima_impact_tracking (driver_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_impact_campaign
        ON growth.yego_lima_impact_tracking (campaign_id_external);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_impact_status
        ON growth.yego_lima_impact_tracking (impact_status);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_impact_contact_date
        ON growth.yego_lima_impact_tracking (contact_date);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_impact_aq_id
        ON growth.yego_lima_impact_tracking (assignment_queue_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_impact_tracking;")
