"""
175 — YEGO Lima Growth: Data Freshness Governance (Fase 4B E2E)

Creates:
- growth.yango_lima_data_freshness
- growth.yango_lima_hourly_snapshot

Additive. No DROP.

down_revision: 174_yego_lima_productivity_governance
"""

from alembic import op

revision = "175_yego_lima_data_freshness_governance"
down_revision = "174_yego_lima_productivity_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_data_freshness (
            source_name             text PRIMARY KEY,
            last_successful_sync_at timestamptz,
            max_data_timestamp      timestamptz,
            rows_last_sync          integer NOT NULL DEFAULT 0,
            sync_duration_seconds   numeric(10,2) NOT NULL DEFAULT 0,
            status                  text NOT NULL DEFAULT 'initializing',
            error_message           text,
            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        INSERT INTO growth.yango_lima_data_freshness (source_name, status) VALUES
            ('orders_api', 'initializing'),
            ('supply_api', 'initializing'),
            ('driver360', 'initializing'),
            ('productivity_daily', 'initializing'),
            ('productivity_weekly', 'initializing'),
            ('productivity_monthly', 'initializing')
        ON CONFLICT (source_name) DO NOTHING;
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_hourly_snapshot (
            hour_start              timestamptz PRIMARY KEY,
            hour_end                timestamptz NOT NULL,

            completed_orders        integer NOT NULL DEFAULT 0,
            active_drivers          integer NOT NULL DEFAULT 0,
            supply_drivers          integer NOT NULL DEFAULT 0,
            supply_hours            numeric(18,4) NOT NULL DEFAULT 0,

            trips_per_driver        numeric(18,4) NULL,
            trips_per_supply_hour   numeric(18,4) NULL,

            created_at              timestamptz NOT NULL DEFAULT now()
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_hourly_created ON growth.yango_lima_hourly_snapshot (created_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_freshness_status ON growth.yango_lima_data_freshness (status);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_hourly_snapshot;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_data_freshness;")
