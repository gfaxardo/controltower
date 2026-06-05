"""
178 — YEGO Lima Growth: LoopControl Export Infrastructure (Fase LC-1)

Creates:
- growth.yango_lima_loopcontrol_config
- growth.yango_lima_loopcontrol_campaign_export

down_revision: 177_yego_lima_recency_policy_fields
"""

from alembic import op

revision = "178_yego_lima_loopcontrol_export"
down_revision = "177_yego_lima_recency_policy_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_loopcontrol_config (
            id                          integer PRIMARY KEY DEFAULT 1,
            is_enabled                  boolean NOT NULL DEFAULT false,
            base_url                    text NOT NULL DEFAULT '',
            integration_key_configured  boolean NOT NULL DEFAULT false,
            default_dialer_mode         text NOT NULL DEFAULT 'predictive',
            default_max_attempts        integer NOT NULL DEFAULT 3,
            default_max_concurrent      integer NOT NULL DEFAULT 10,
            default_ring_timeout        integer NOT NULL DEFAULT 30,
            created_at                  timestamptz NOT NULL DEFAULT now(),
            updated_at                  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT single_row CHECK (id = 1)
        );
    """)

    op.execute("""
        INSERT INTO growth.yango_lima_loopcontrol_config (id, is_enabled)
        VALUES (1, false)
        ON CONFLICT (id) DO NOTHING;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_loopcontrol_campaign_export (
            export_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            opportunity_date        date NOT NULL,
            campaign_id_external    text,
            campaign_name           text NOT NULL,
            program_code            text NOT NULL,
            contacts_sent           integer NOT NULL DEFAULT 0,
            contacts_inserted       integer NOT NULL DEFAULT 0,
            contacts_skipped        integer NOT NULL DEFAULT 0,
            export_status           text NOT NULL DEFAULT 'draft',
            error_message           text,
            exported_at             timestamptz NOT NULL DEFAULT now(),
            created_by              text
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_lc_export_date ON growth.yango_lima_loopcontrol_campaign_export (opportunity_date DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lc_export_status ON growth.yango_lima_loopcontrol_campaign_export (export_status);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_loopcontrol_campaign_export;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_loopcontrol_config;")
