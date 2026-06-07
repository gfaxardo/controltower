"""
187 — AE-1: Attribution Candidates

Creates:
- growth.yego_lima_attribution_candidates

Stores candidate attribution records linking movements to campaigns/programs/channels.
Deterministic rules. NO ML. NO causalidad.

down_revision: 186_yego_lima_movement_tracking
"""

from alembic import op

revision = "187_yego_lima_attribution_candidates"
down_revision = "186_yego_lima_movement_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_attribution_candidates (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),

            driver_id               TEXT NOT NULL,
            campaign_id_external    TEXT NULL,
            assignment_queue_id     uuid NULL,
            impact_tracking_id      uuid NULL,
            movement_tracking_id    uuid NULL,

            program_code            TEXT NULL,
            assigned_channel        TEXT NULL,

            candidate_status        TEXT NOT NULL DEFAULT 'UNKNOWN',
            candidate_confidence    TEXT NOT NULL DEFAULT 'LOW',
            candidate_reason        TEXT NULL,

            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_attrib_driver
        ON growth.yego_lima_attribution_candidates (driver_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_attrib_campaign
        ON growth.yego_lima_attribution_candidates (campaign_id_external);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_attrib_program
        ON growth.yego_lima_attribution_candidates (program_code);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_attrib_channel
        ON growth.yego_lima_attribution_candidates (assigned_channel);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_attribution_candidates;")
