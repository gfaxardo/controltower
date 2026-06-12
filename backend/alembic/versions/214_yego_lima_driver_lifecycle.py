"""
214 — LG-ACT-1A: Driver Lifecycle Foundation Tables

Creates:
- growth.yego_lima_driver_activity_event
- growth.yego_lima_driver_activity_daily
- growth.yego_lima_driver_activity_weekly
- growth.yego_lima_driver_activity_monthly
- growth.yego_lima_driver_lifecycle_daily
- growth.yego_lima_driver_lifecycle_event

down_revision: 213_cf_h2e1_multipark_credentials
"""

from alembic import op

revision = "214_yego_lima_driver_lifecycle"
down_revision = "213_cf_h2e1_multipark_credentials"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_driver_activity_event (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            source_system       text NOT NULL DEFAULT 'trips_table',
            source_table        text NOT NULL,
            source_trip_id      text NOT NULL,
            park_id             text NOT NULL,
            driver_profile_id   text NOT NULL,
            event_type          text NOT NULL,
            event_timestamp     timestamptz NOT NULL,
            event_date          date NOT NULL,
            service_type        text,
            cancellation_reason text,
            price_yango_pro     numeric,
            distance_km         numeric,
            raw_status          text,
            created_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE(source_system, source_table, source_trip_id)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_act_event_date ON growth.yego_lima_driver_activity_event (event_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_act_event_driver ON growth.yego_lima_driver_activity_event (driver_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_act_event_park ON growth.yego_lima_driver_activity_event (park_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_act_event_type ON growth.yego_lima_driver_activity_event (event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_act_event_ts ON growth.yego_lima_driver_activity_event (event_timestamp)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_driver_activity_daily (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            activity_date           date NOT NULL,
            park_id                 text NOT NULL,
            driver_profile_id       text NOT NULL,
            completed_orders        integer NOT NULL DEFAULT 0,
            cancelled_orders        integer NOT NULL DEFAULT 0,
            total_orders            integer NOT NULL DEFAULT 0,
            completed_revenue       numeric DEFAULT 0,
            completed_distance_km   numeric DEFAULT 0,
            has_completed_trip      boolean NOT NULL DEFAULT false,
            has_cancelled_trip      boolean NOT NULL DEFAULT false,
            first_completed_at      timestamptz,
            last_completed_at       timestamptz,
            first_event_at          timestamptz,
            last_event_at           timestamptz,
            source_system           text DEFAULT 'trips_table',
            source_quality_status   text DEFAULT 'ok',
            source_quality_flags_json jsonb,
            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now(),
            UNIQUE(activity_date, park_id, driver_profile_id)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_act_daily_date ON growth.yego_lima_driver_activity_daily (activity_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_act_daily_driver ON growth.yego_lima_driver_activity_daily (driver_profile_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_driver_activity_weekly (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            week_start_date         date NOT NULL,
            park_id                 text NOT NULL,
            driver_profile_id       text NOT NULL,
            completed_orders_week   integer NOT NULL DEFAULT 0,
            cancelled_orders_week   integer NOT NULL DEFAULT 0,
            active_days_week        integer NOT NULL DEFAULT 0,
            completed_revenue_week  numeric DEFAULT 0,
            completed_distance_km_week numeric DEFAULT 0,
            first_completed_at_week timestamptz,
            last_completed_at_week  timestamptz,
            source_quality_status   text DEFAULT 'ok',
            created_at              timestamptz NOT NULL DEFAULT now(),
            UNIQUE(week_start_date, park_id, driver_profile_id)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_act_weekly_date ON growth.yego_lima_driver_activity_weekly (week_start_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_act_weekly_driver ON growth.yego_lima_driver_activity_weekly (driver_profile_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_driver_activity_monthly (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            month_start_date        date NOT NULL,
            park_id                 text NOT NULL,
            driver_profile_id       text NOT NULL,
            completed_orders_month  integer NOT NULL DEFAULT 0,
            cancelled_orders_month  integer NOT NULL DEFAULT 0,
            active_days_month       integer NOT NULL DEFAULT 0,
            completed_revenue_month numeric DEFAULT 0,
            completed_distance_km_month numeric DEFAULT 0,
            first_completed_at_month timestamptz,
            last_completed_at_month timestamptz,
            source_quality_status   text DEFAULT 'ok',
            created_at              timestamptz NOT NULL DEFAULT now(),
            UNIQUE(month_start_date, park_id, driver_profile_id)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_act_monthly_date ON growth.yego_lima_driver_activity_monthly (month_start_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_act_monthly_driver ON growth.yego_lima_driver_activity_monthly (driver_profile_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_driver_lifecycle_daily (
            id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date               date NOT NULL,
            park_id                     text NOT NULL,
            driver_profile_id           text NOT NULL,
            hire_date                   date,
            first_completed_trip_date   date,
            last_completed_trip_date    date,
            days_since_hire             integer,
            days_since_first_trip       integer,
            days_since_last_completed_trip integer,
            completed_trips_7d          integer DEFAULT 0,
            completed_trips_14d         integer DEFAULT 0,
            completed_trips_30d         integer DEFAULT 0,
            completed_trips_90d         integer DEFAULT 0,
            completed_trips_since_anchor integer DEFAULT 0,
            lifecycle_status            text NOT NULL,
            current_anchor_date         date,
            anchor_type                 text,
            lifecycle_reason            text,
            lifecycle_version           text DEFAULT 'v1',
            evidence_json               jsonb,
            created_at                  timestamptz NOT NULL DEFAULT now(),
            UNIQUE(snapshot_date, park_id, driver_profile_id)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_lifecycle_date ON growth.yego_lima_driver_lifecycle_daily (snapshot_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lifecycle_driver ON growth.yego_lima_driver_lifecycle_daily (driver_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lifecycle_status ON growth.yego_lima_driver_lifecycle_daily (snapshot_date, lifecycle_status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_driver_lifecycle_event (
            id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            event_date                  date NOT NULL,
            park_id                     text NOT NULL,
            driver_profile_id           text NOT NULL,
            lifecycle_event_type        text NOT NULL,
            previous_lifecycle_status   text,
            new_lifecycle_status        text NOT NULL,
            anchor_date                 date,
            trigger_reason              text,
            evidence_json               jsonb,
            lifecycle_version           text DEFAULT 'v1',
            created_at                  timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_lc_event_date ON growth.yego_lima_driver_lifecycle_event (event_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lc_event_driver ON growth.yego_lima_driver_lifecycle_event (driver_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lc_event_type ON growth.yego_lima_driver_lifecycle_event (lifecycle_event_type)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_driver_lifecycle_event")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_driver_lifecycle_daily")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_driver_activity_monthly")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_driver_activity_weekly")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_driver_activity_daily")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_driver_activity_event")
