"""
180 — LG-2.2B: Daily Capacity Config Persistent

Creates:
- growth.yego_lima_capacity_config

Additive. No DROP.
No borrar historico.
Reglas:
- config_date NULL = default global.
- Si existe config para fecha especifica, overridea default.

down_revision: 179_yego_lima_loopcontrol_export_job
"""

from alembic import op

revision = "180_yego_lima_capacity_config"
down_revision = "179_yego_lima_loopcontrol_export_job"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_capacity_config (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            config_date         date NULL,
            channel             text NOT NULL,
            agents              integer NOT NULL,
            capacity_per_agent  integer NOT NULL,
            is_active           boolean NOT NULL DEFAULT true,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_capacity_config_date
        ON growth.yego_lima_capacity_config (config_date);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_capacity_config_active
        ON growth.yego_lima_capacity_config (is_active)
        WHERE is_active = true;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_capacity_config_channel
        ON growth.yego_lima_capacity_config (channel);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_capacity_config;")
