"""
174 — YEGO Lima Growth: Productivity Governance Tables

Creates:
- growth.yango_lima_productivity_daily
- growth.yango_lima_productivity_weekly
- growth.yango_lima_productivity_monthly

Additive. No DROP.

down_revision: 173_yego_lima_driver_360_stabilization
"""

from alembic import op

revision = "174_yego_lima_productivity_governance"
down_revision = "173_yego_lima_driver_360_stabilization"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    # ── Daily ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_productivity_daily (
            date                date PRIMARY KEY,
            iso_year            integer NOT NULL,
            iso_week            integer NOT NULL,
            iso_week_key        text NOT NULL,
            iso_day_of_week     integer NOT NULL,
            iso_day_name        text NOT NULL,

            supply_drivers      integer NOT NULL DEFAULT 0,
            supply_hours        numeric(18,4) NOT NULL DEFAULT 0,

            active_drivers      integer NOT NULL DEFAULT 0,
            completed_orders    integer NOT NULL DEFAULT 0,
            gross_revenue       numeric(18,4) NULL,

            supply_to_active_driver_rate numeric(18,4) NULL,

            trips_per_active_driver    numeric(18,4) NULL,
            trips_per_supply_driver    numeric(18,4) NULL,
            trips_per_supply_hour      numeric(18,4) NULL,

            drivers_0_9         integer NOT NULL DEFAULT 0,
            drivers_10_19       integer NOT NULL DEFAULT 0,
            drivers_20_29       integer NOT NULL DEFAULT 0,
            drivers_30_39       integer NOT NULL DEFAULT 0,
            drivers_40_49       integer NOT NULL DEFAULT 0,
            drivers_50_69       integer NOT NULL DEFAULT 0,
            drivers_70_99       integer NOT NULL DEFAULT 0,
            drivers_100_plus    integer NOT NULL DEFAULT 0,

            last_calculated_at  timestamptz NOT NULL DEFAULT now(),
            source              text NOT NULL DEFAULT 'driver360_daily'
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_prod_daily_iso_week ON growth.yango_lima_productivity_daily (iso_week_key);")

    # ── Weekly ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_productivity_weekly (
            iso_year            integer NOT NULL,
            iso_week            integer NOT NULL,
            iso_week_key        text NOT NULL,
            iso_week_start_date date NOT NULL,
            iso_week_end_date   date NOT NULL,

            supply_drivers      integer NOT NULL DEFAULT 0,
            supply_hours        numeric(18,4) NOT NULL DEFAULT 0,

            active_drivers      integer NOT NULL DEFAULT 0,
            completed_orders    integer NOT NULL DEFAULT 0,
            gross_revenue       numeric(18,4) NULL,

            supply_to_active_driver_rate numeric(18,4) NULL,

            trips_per_active_driver    numeric(18,4) NULL,
            trips_per_supply_driver    numeric(18,4) NULL,
            trips_per_supply_hour      numeric(18,4) NULL,

            drivers_0_9         integer NOT NULL DEFAULT 0,
            drivers_10_19       integer NOT NULL DEFAULT 0,
            drivers_20_29       integer NOT NULL DEFAULT 0,
            drivers_30_39       integer NOT NULL DEFAULT 0,
            drivers_40_49       integer NOT NULL DEFAULT 0,
            drivers_50_69       integer NOT NULL DEFAULT 0,
            drivers_70_99       integer NOT NULL DEFAULT 0,
            drivers_100_plus    integer NOT NULL DEFAULT 0,

            last_calculated_at  timestamptz NOT NULL DEFAULT now(),
            source              text NOT NULL DEFAULT 'productivity_governance',

            PRIMARY KEY (iso_year, iso_week)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_prod_weekly_key ON growth.yango_lima_productivity_weekly (iso_week_key);")

    # ── Monthly ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_productivity_monthly (
            year              integer NOT NULL,
            month             integer NOT NULL,
            month_key         text NOT NULL,

            supply_drivers      integer NOT NULL DEFAULT 0,
            supply_hours        numeric(18,4) NOT NULL DEFAULT 0,

            active_drivers      integer NOT NULL DEFAULT 0,
            completed_orders    integer NOT NULL DEFAULT 0,
            gross_revenue       numeric(18,4) NULL,

            supply_to_active_driver_rate numeric(18,4) NULL,

            trips_per_active_driver    numeric(18,4) NULL,
            trips_per_supply_driver    numeric(18,4) NULL,
            trips_per_supply_hour      numeric(18,4) NULL,

            drivers_0_9         integer NOT NULL DEFAULT 0,
            drivers_10_19       integer NOT NULL DEFAULT 0,
            drivers_20_29       integer NOT NULL DEFAULT 0,
            drivers_30_39       integer NOT NULL DEFAULT 0,
            drivers_40_49       integer NOT NULL DEFAULT 0,
            drivers_50_69       integer NOT NULL DEFAULT 0,
            drivers_70_99       integer NOT NULL DEFAULT 0,
            drivers_100_plus    integer NOT NULL DEFAULT 0,

            last_calculated_at  timestamptz NOT NULL DEFAULT now(),
            source              text NOT NULL DEFAULT 'productivity_governance',

            PRIMARY KEY (year, month)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_prod_monthly_key ON growth.yango_lima_productivity_monthly (month_key);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_productivity_monthly;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_productivity_weekly;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_productivity_daily;")
