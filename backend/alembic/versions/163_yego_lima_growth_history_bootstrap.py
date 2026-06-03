"""
163 — YEGO Lima Fleet Growth Tower: Historical Bootstrap

Creates:
- growth.yango_lima_driver_history_daily: daily driver trip aggregates from trips bootstrap
- growth.yango_lima_driver_history_weekly: weekly driver aggregates with rolling metrics

Additive only. No DROP. No impact on production serving facts.

down_revision: 162_yego_lima_loyalty_sub50_weekly
"""

from alembic import op

revision = "163_yego_lima_growth_history_bootstrap"
down_revision = "162_yego_lima_loyalty_sub50_weekly"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_driver_history_daily (
            date               date NOT NULL,
            driver_profile_id  text NOT NULL,
            completed_orders   integer NOT NULL DEFAULT 0,
            gross_revenue      numeric(18,4) NULL,
            source             text NOT NULL DEFAULT 'trips_bootstrap',
            last_calculated_at timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (date, driver_profile_id)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_daily_driver
        ON growth.yango_lima_driver_history_daily (driver_profile_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_daily_date
        ON growth.yango_lima_driver_history_daily (date);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_driver_history_weekly (
            week_start_date        date NOT NULL,
            week_end_date          date NOT NULL,
            driver_profile_id      text NOT NULL,

            completed_orders_week  integer NOT NULL DEFAULT 0,
            gross_revenue_week     numeric(18,4) NULL,
            active_days            integer NOT NULL DEFAULT 0,
            avg_orders_per_active_day numeric(18,4) NULL,

            avg_orders_4w          numeric(18,4) NULL,
            avg_orders_8w          numeric(18,4) NULL,
            avg_orders_12w         numeric(18,4) NULL,
            best_week_12w          integer NULL,
            historical_band        text NULL,

            source             text NOT NULL DEFAULT 'trips_bootstrap',
            last_calculated_at timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (week_start_date, driver_profile_id)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_weekly_driver
        ON growth.yango_lima_driver_history_weekly (driver_profile_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_weekly_week
        ON growth.yango_lima_driver_history_weekly (week_start_date);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_weekly_band
        ON growth.yango_lima_driver_history_weekly (historical_band);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_history_weekly_orders
        ON growth.yango_lima_driver_history_weekly (completed_orders_week);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_driver_history_weekly;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_driver_history_daily;")
