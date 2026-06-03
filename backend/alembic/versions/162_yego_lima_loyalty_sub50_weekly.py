"""
162 — YEGO Lima Fleet Growth Tower: Loyalty Sub-50 Engine Foundation

Creates:
- growth.yango_lima_loyalty_sub50_weekly: weekly driver classification for sub-50 trip cohorts

Additive only. No DROP. No impact on production serving facts.

down_revision: 161_yego_lima_growth_raw_orders
"""

from alembic import op

revision = "162_yego_lima_loyalty_sub50_weekly"
down_revision = "161_yego_lima_growth_raw_orders"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_loyalty_sub50_weekly (
            week_start_date    date NOT NULL,
            week_end_date      date NOT NULL,
            driver_profile_id  text NOT NULL,

            completed_orders_week       integer NOT NULL DEFAULT 0,
            supply_hours_week           numeric(18,4) NOT NULL DEFAULT 0,
            trips_per_supply_hour_week  numeric(18,4) NULL,

            productivity_band  text NULL,
            driver_state       text NULL,

            segment            text NOT NULL DEFAULT 'SUB50_00_09',
            distance_to_50     integer NOT NULL DEFAULT 50,
            growth_priority    integer NOT NULL DEFAULT 5,

            last_calculated_at timestamptz NOT NULL DEFAULT now(),
            source             text NOT NULL DEFAULT 'loyalty_sub50',

            PRIMARY KEY (week_start_date, driver_profile_id)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_loyalty_sub50_segment
        ON growth.yango_lima_loyalty_sub50_weekly (segment);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_loyalty_sub50_growth_priority
        ON growth.yango_lima_loyalty_sub50_weekly (growth_priority);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_loyalty_sub50_completed_orders_week
        ON growth.yango_lima_loyalty_sub50_weekly (completed_orders_week);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_loyalty_sub50_distance_to_50
        ON growth.yango_lima_loyalty_sub50_weekly (distance_to_50);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_loyalty_sub50_weekly;")
