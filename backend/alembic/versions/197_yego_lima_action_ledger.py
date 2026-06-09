"""
197 — LG-OEF-1.0A: Action Ledger

Creates:
- growth.yego_lima_action_ledger

Records actions taken on drivers (calls, messages, visits).
Append-only. Links to drivers and campaigns.

down_revision: 196_yego_lima_diagnostic_trace
"""

from alembic import op

revision = "197_yego_lima_action_ledger"
down_revision = "196_yego_lima_diagnostic_trace"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_action_ledger (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            driver_profile_id   text NOT NULL,
            action_type         text NOT NULL DEFAULT 'OTHER'
                CHECK (action_type IN ('CALL', 'WHATSAPP', 'SMS', 'MANUAL_REVIEW', 'FIELD_VISIT', 'OTHER')),
            channel             text,
            agent               text,
            action_timestamp    timestamptz NOT NULL DEFAULT now(),
            result              text,
            notes               text,
            campaign_id_external text,
            queue_id            uuid,
            program_code        text,
            created_at          timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_al_driver ON growth.yego_lima_action_ledger (driver_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_al_timestamp ON growth.yego_lima_action_ledger (action_timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_al_campaign ON growth.yego_lima_action_ledger (campaign_id_external)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_action_ledger")
