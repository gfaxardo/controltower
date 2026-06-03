"""
171 — YEGO Lima Fleet Growth Tower: Driver 360 Daily Fact

Creates:
- growth.yango_lima_driver_360_daily: daily driver 360 fact table

Additive only. No DROP. No impact on production serving facts.

down_revision: 170_yego_lima_state_based_loyalty_architecture
"""

from alembic import op

revision = "171_yego_lima_driver_360_daily"
down_revision = "170_yego_lima_state_based_loyalty_architecture"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_driver_360_daily (
            driver_profile_id TEXT NOT NULL,
            date DATE NOT NULL,

            work_status TEXT,
            current_status TEXT,
            work_rule_id TEXT,
            employment_type TEXT,

            car_id TEXT,
            car_category TEXT,
            car_status TEXT,
            car_brand TEXT,
            car_model TEXT,
            car_number TEXT,

            completed_orders INTEGER NOT NULL DEFAULT 0,
            gross_revenue NUMERIC(18,4) NOT NULL DEFAULT 0,

            supply_seconds BIGINT NOT NULL DEFAULT 0,
            supply_hours NUMERIC(18,4) NOT NULL DEFAULT 0,
            trips_per_supply_hour NUMERIC(18,4),

            active_flag BOOLEAN NOT NULL DEFAULT FALSE,
            driver_state TEXT NOT NULL,

            source TEXT NOT NULL DEFAULT 'yango_driver_360_daily',
            last_calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            PRIMARY KEY (driver_profile_id, date)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_driver_360_daily_state_date
        ON growth.yango_lima_driver_360_daily (driver_state, date);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_driver_360_daily_date
        ON growth.yango_lima_driver_360_daily (date);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_driver_360_daily_completed_orders
        ON growth.yango_lima_driver_360_daily (completed_orders);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_driver_360_daily_supply_hours
        ON growth.yango_lima_driver_360_daily (supply_hours);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_driver_360_daily_active_flag
        ON growth.yango_lima_driver_360_daily (active_flag);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_driver_360_daily;")
