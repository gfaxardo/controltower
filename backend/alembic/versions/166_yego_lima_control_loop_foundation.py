"""
166 — YEGO Lima Growth: Control Loop Foundation

Creates:
- growth.yango_lima_actionable_list_daily: daily actionable driver lists
- growth.yango_lima_driver_action_registry: agent action registry
- growth.yango_lima_driver_action_daily_impact: daily impact tracking

Additive. No DROP.

down_revision: 165_yego_lima_driver_segment_snapshot
"""

from alembic import op

revision = "166_yego_lima_control_loop_foundation"
down_revision = "165_yego_lima_driver_segment_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    # Table 1: Actionable List Daily
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_actionable_list_daily (
            list_date          date NOT NULL,
            driver_profile_id  text NOT NULL,
            list_type          text NOT NULL,

            segment_level_1    text NULL,
            segment_level_2    text NULL,
            segment_level_3    text NULL,
            priority           integer NULL,
            action_reason      text NULL,

            current_week_orders integer NULL,
            distance_to_target  integer NULL,
            supply_hours        numeric(18,4) NULL,
            productivity_band   text NULL,
            driver_state        text NULL,

            management_status   text NOT NULL DEFAULT 'PENDING_ACTION',
            assigned_agent      text NULL,
            action_id           uuid NULL,

            generated_at        timestamptz NOT NULL DEFAULT now(),
            closed_at           timestamptz NULL,

            PRIMARY KEY (list_date, driver_profile_id, list_type)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_actionable_list_status ON growth.yango_lima_actionable_list_daily (management_status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_actionable_list_type ON growth.yango_lima_actionable_list_daily (list_type);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_actionable_list_agent ON growth.yango_lima_actionable_list_daily (assigned_agent);")

    # Table 2: Action Registry
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_driver_action_registry (
            action_id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            action_date                 date NOT NULL,
            driver_profile_id           text NOT NULL,
            list_date                   date NULL,
            list_type                   text NULL,
            source_segment_snapshot_date date NOT NULL,

            segment_level_1             text NULL,
            segment_level_2             text NULL,
            segment_level_3             text NULL,

            action_type                 text NOT NULL,
            action_channel              text NULL,
            action_owner                text NULL,
            action_status               text NOT NULL DEFAULT 'attempted',
            action_confirmed            boolean NOT NULL DEFAULT false,
            confirmation_source         text NULL,
            confirmation_at             timestamptz NULL,
            action_reason               text NULL,
            campaign_code               text NULL,
            notes                       text NULL,

            created_at                  timestamptz NOT NULL DEFAULT now(),
            updated_at                  timestamptz NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_registry_driver ON growth.yango_lima_driver_action_registry (driver_profile_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_registry_date ON growth.yango_lima_driver_action_registry (action_date);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_registry_owner ON growth.yango_lima_driver_action_registry (action_owner);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_action_registry_status ON growth.yango_lima_driver_action_registry (action_status);")

    # Table 3: Daily Impact
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_driver_action_daily_impact (
            action_id                   uuid NOT NULL,
            impact_date                 date NOT NULL,
            driver_profile_id           text NOT NULL,
            days_since_action           integer NOT NULL,

            completed_orders_day        integer NOT NULL DEFAULT 0,
            supply_hours_day            numeric(18,4) NOT NULL DEFAULT 0,
            trips_per_supply_hour_day   numeric(18,4) NULL,

            segment_level_1             text NULL,
            segment_level_2             text NULL,
            segment_level_3             text NULL,
            driver_state                text NULL,
            productivity_band           text NULL,

            baseline_completed_orders_7d numeric(18,4) NULL,
            baseline_supply_hours_7d    numeric(18,4) NULL,
            delta_orders_vs_baseline    numeric(18,4) NULL,
            delta_supply_vs_baseline    numeric(18,4) NULL,

            moved_segment_flag          boolean NOT NULL DEFAULT false,
            improved_orders_flag        boolean NOT NULL DEFAULT false,
            improved_supply_flag        boolean NOT NULL DEFAULT false,
            reactivated_flag            boolean NOT NULL DEFAULT false,
            reached_target_flag         boolean NOT NULL DEFAULT false,

            calculated_at               timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (action_id, impact_date)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_daily_impact_driver ON growth.yango_lima_driver_action_daily_impact (driver_profile_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_daily_impact_date ON growth.yango_lima_driver_action_daily_impact (impact_date);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_driver_action_daily_impact;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_driver_action_registry;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_actionable_list_daily;")
