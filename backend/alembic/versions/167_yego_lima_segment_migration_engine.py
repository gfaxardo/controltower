"""
167 — YEGO Lima Growth: Segment Migration Engine

Creates:
- growth.yango_lima_driver_segment_transition_daily
- growth.yango_lima_actionable_list_outcome_daily

Additive. No DROP.

down_revision: 166_yego_lima_control_loop_foundation
"""

from alembic import op

revision = "167_yego_lima_segment_migration_engine"
down_revision = "166_yego_lima_control_loop_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_driver_segment_transition_daily (
            transition_date         date NOT NULL,
            driver_profile_id       text NOT NULL,

            prev_snapshot_date      date NULL,
            prev_segment_level_1    text NULL,
            prev_segment_level_2    text NULL,
            prev_segment_level_3    text NULL,
            prev_driver_state       text NULL,
            prev_productivity_band  text NULL,
            prev_current_week_orders integer NULL,
            prev_supply_hours       numeric(18,4) NULL,

            current_snapshot_date   date NOT NULL,
            current_segment_level_1 text NULL,
            current_segment_level_2 text NULL,
            current_segment_level_3 text NULL,
            current_driver_state    text NULL,
            current_productivity_band text NULL,
            current_week_orders     integer NULL,
            current_supply_hours    numeric(18,4) NULL,

            segment_changed_flag    boolean NOT NULL DEFAULT false,
            level_1_changed_flag    boolean NOT NULL DEFAULT false,
            level_2_changed_flag    boolean NOT NULL DEFAULT false,
            level_3_changed_flag    boolean NOT NULL DEFAULT false,
            movement_direction      text NOT NULL DEFAULT 'NO_CHANGE',
            movement_type           text NULL,
            orders_delta            numeric(18,4) NULL,
            supply_delta            numeric(18,4) NULL,
            productivity_delta      numeric(18,4) NULL,

            had_action_flag         boolean NOT NULL DEFAULT false,
            had_confirmed_action_flag boolean NOT NULL DEFAULT false,
            action_id               uuid NULL,
            action_type             text NULL,
            action_owner            text NULL,
            campaign_code           text NULL,

            calculated_at           timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (transition_date, driver_profile_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_transition_driver ON growth.yango_lima_driver_segment_transition_daily (driver_profile_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transition_direction ON growth.yango_lima_driver_segment_transition_daily (movement_direction);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_transition_action_owner ON growth.yango_lima_driver_segment_transition_daily (action_owner);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_actionable_list_outcome_daily (
            list_date               date NOT NULL,
            list_type               text NOT NULL,

            generated_count         integer NOT NULL DEFAULT 0,
            pending_count           integer NOT NULL DEFAULT 0,
            action_confirmed_count  integer NOT NULL DEFAULT 0,
            action_attempted_count  integer NOT NULL DEFAULT 0,
            no_action_count         integer NOT NULL DEFAULT 0,
            dismissed_count         integer NOT NULL DEFAULT 0,

            improved_count          integer NOT NULL DEFAULT 0,
            worsened_count          integer NOT NULL DEFAULT 0,
            no_change_count         integer NOT NULL DEFAULT 0,
            moved_segment_count     integer NOT NULL DEFAULT 0,
            reached_target_count    integer NOT NULL DEFAULT 0,
            reactivated_count       integer NOT NULL DEFAULT 0,

            action_confirmation_rate numeric(18,4) NULL,
            movement_rate           numeric(18,4) NULL,
            improvement_rate        numeric(18,4) NULL,
            no_action_rate          numeric(18,4) NULL,

            calculated_at           timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (list_date, list_type)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_list_outcome_date ON growth.yango_lima_actionable_list_outcome_daily (list_date);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_actionable_list_outcome_daily;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_driver_segment_transition_daily;")
