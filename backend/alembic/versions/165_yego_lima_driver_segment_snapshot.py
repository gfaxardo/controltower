"""
165 — YEGO Lima Growth: Unified Driver Segmentation Snapshot

Creates:
- growth.yango_lima_driver_segment_snapshot

3-level segmentation:
  L1 = LIFECYCLE (NEW, REACTIVATED, ACTIVE, DECLINING, CHURN_RISK, CHURNED, RECOVERED, UNKNOWN)
  L2 = LOYALTY PROGRAM (LOYALTY_14_90, LOYALTY_ACTIVE_GROWTH, LOYALTY_CHURN_PREVENTION, NONE)
  L3 = ACTIONABLE COHORT

Additive. No DROP.

down_revision: 164_yego_lima_loyalty_sub50_canonical_columns
"""

from alembic import op

revision = "165_yego_lima_driver_segment_snapshot"
down_revision = "164_yego_lima_loyalty_sub50_canonical_columns"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_driver_segment_snapshot (
            snapshot_date          date NOT NULL,
            driver_profile_id      text NOT NULL,

            segment_level_1        text NOT NULL,
            segment_level_2        text NOT NULL,
            segment_level_3        text NOT NULL,

            current_week_orders    integer NOT NULL DEFAULT 0,
            current_week_supply_hours numeric(18,4) NOT NULL DEFAULT 0,
            distance_to_target     integer NULL,

            avg_orders_4w          numeric(18,4) NULL,
            avg_orders_12w         numeric(18,4) NULL,
            best_week_12w          integer NULL,

            driver_state           text NULL,
            productivity_band      text NULL,
            historical_band        text NULL,

            recoverable_flag       boolean NOT NULL DEFAULT false,
            growth_priority        integer NULL,

            last_calculated_at     timestamptz NOT NULL DEFAULT now(),
            source                 text NOT NULL DEFAULT 'driver_segment_snapshot',

            PRIMARY KEY (snapshot_date, driver_profile_id)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_segment_snapshot_l1
        ON growth.yango_lima_driver_segment_snapshot (segment_level_1);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_segment_snapshot_l2
        ON growth.yango_lima_driver_segment_snapshot (segment_level_2);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_segment_snapshot_l3
        ON growth.yango_lima_driver_segment_snapshot (segment_level_3);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_segment_snapshot_priority
        ON growth.yango_lima_driver_segment_snapshot (growth_priority);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_segment_snapshot_recoverable
        ON growth.yango_lima_driver_segment_snapshot (recoverable_flag);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_driver_segment_snapshot;")
