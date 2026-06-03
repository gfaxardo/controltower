"""
164 — YEGO Lima Growth: Loyalty Sub-50 canonical columns + recoverable flag

Creates or alters growth.yango_lima_loyalty_sub50_weekly with all columns including:
- target_weekly_trips, historical metrics, recoverable_flag, canonical_source, source_version

Additive. No DROP.

down_revision: 163_yego_lima_growth_history_bootstrap
"""

from alembic import op

revision = "164_yego_lima_loyalty_sub50_canonical_columns"
down_revision = "163_yego_lima_growth_history_bootstrap"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'growth' AND table_name = 'yango_lima_loyalty_sub50_weekly'
            ) THEN
                CREATE TABLE growth.yango_lima_loyalty_sub50_weekly (
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

                    target_weekly_trips integer NOT NULL DEFAULT 50,
                    avg_orders_4w     numeric(18,4) NULL,
                    avg_orders_8w     numeric(18,4) NULL,
                    avg_orders_12w    numeric(18,4) NULL,
                    best_week_12w     integer NULL,
                    historical_band   text NULL,
                    recoverable_flag  boolean NOT NULL DEFAULT false,
                    canonical_source  text NOT NULL DEFAULT 'driver360_history_weekly',
                    source_version    text NULL,

                    last_calculated_at timestamptz NOT NULL DEFAULT now(),
                    source             text NOT NULL DEFAULT 'loyalty_sub50',

                    PRIMARY KEY (week_start_date, driver_profile_id)
                );

                CREATE INDEX idx_loyalty_sub50_segment
                    ON growth.yango_lima_loyalty_sub50_weekly (segment);
                CREATE INDEX idx_loyalty_sub50_growth_priority
                    ON growth.yango_lima_loyalty_sub50_weekly (growth_priority);
                CREATE INDEX idx_loyalty_sub50_completed_orders_week
                    ON growth.yango_lima_loyalty_sub50_weekly (completed_orders_week);
                CREATE INDEX idx_loyalty_sub50_distance_to_50
                    ON growth.yango_lima_loyalty_sub50_weekly (distance_to_50);
                CREATE INDEX idx_loyalty_sub50_recoverable
                    ON growth.yango_lima_loyalty_sub50_weekly (recoverable_flag);
            ELSE
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS target_weekly_trips integer NOT NULL DEFAULT 50;
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS avg_orders_4w numeric(18,4) NULL;
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS avg_orders_8w numeric(18,4) NULL;
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS avg_orders_12w numeric(18,4) NULL;
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS best_week_12w integer NULL;
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS historical_band text NULL;
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS recoverable_flag boolean NOT NULL DEFAULT false;
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS canonical_source text NOT NULL DEFAULT 'driver360_history_weekly';
                ALTER TABLE growth.yango_lima_loyalty_sub50_weekly
                    ADD COLUMN IF NOT EXISTS source_version text NULL;
            END IF;
        END $$;
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_loyalty_sub50_weekly;")
