"""
168 — YEGO Lima Growth: Impact Attribution Engine

Creates:
- growth.yango_lima_action_attribution_daily

Additive. No DROP.

down_revision: 167_yego_lima_segment_migration_engine
"""

from alembic import op

revision = "168_yego_lima_impact_attribution_engine"
down_revision = "167_yego_lima_segment_migration_engine"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_action_attribution_daily (
            attribution_date    date NOT NULL,
            attribution_scope   text NOT NULL,
            attribution_key     text NOT NULL,

            drivers_assigned    integer NOT NULL DEFAULT 0,
            drivers_contacted   integer NOT NULL DEFAULT 0,
            drivers_attempted   integer NOT NULL DEFAULT 0,
            drivers_confirmed   integer NOT NULL DEFAULT 0,
            drivers_no_action   integer NOT NULL DEFAULT 0,

            drivers_moved       integer NOT NULL DEFAULT 0,
            drivers_improved    integer NOT NULL DEFAULT 0,
            drivers_worsened    integer NOT NULL DEFAULT 0,
            drivers_reactivated integer NOT NULL DEFAULT 0,
            drivers_recovered   integer NOT NULL DEFAULT 0,
            drivers_reached_target integer NOT NULL DEFAULT 0,

            orders_delta_total  numeric(18,4) NULL,
            orders_delta_avg    numeric(18,4) NULL,
            supply_delta_total  numeric(18,4) NULL,
            supply_delta_avg    numeric(18,4) NULL,
            productivity_delta_avg numeric(18,4) NULL,

            contact_rate        numeric(18,4) NULL,
            movement_rate       numeric(18,4) NULL,
            improvement_rate    numeric(18,4) NULL,
            target_reached_rate numeric(18,4) NULL,
            reactivation_rate   numeric(18,4) NULL,

            attribution_window_days integer NOT NULL DEFAULT 7,
            calculated_at       timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (attribution_date, attribution_scope, attribution_key)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_attribution_scope ON growth.yango_lima_action_attribution_daily (attribution_scope);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_attribution_key ON growth.yango_lima_action_attribution_daily (attribution_key);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_attribution_date ON growth.yango_lima_action_attribution_daily (attribution_date);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_action_attribution_daily;")
