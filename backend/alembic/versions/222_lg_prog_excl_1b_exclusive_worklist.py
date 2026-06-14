"""
222 — LG-PROG-EXCL-1B: Exclusive Driver Worklist Daily Serving Fact

Creates:
- growth.yango_lima_exclusive_driver_worklist_daily

Daily exclusive driver operational lists.
1 driver = 1 assigned_universe_v1 per generated_date.
Cemetery is not exported to daily Control Loop.

Additive only. No DROP.
down_revision: 221_ov2_d1_serving_registry
"""

from alembic import op

revision = "222_lg_prog_excl_1b_exclusive_worklist"
down_revision = "221_ov2_d1_serving_registry"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_exclusive_driver_worklist_daily (
            generated_date                  date NOT NULL,
            driver_profile_id               text NOT NULL,
            driver_id                       text,
            assigned_universe_v1            text NOT NULL
                CHECK (assigned_universe_v1 IN (
                    'CEMETERY_LONG_CHURNED',
                    'RECOVERY_RECENT_INACTIVE_HIGH_VALUE',
                    'RECOVERY_RECENT_INACTIVE_LOW_VALUE',
                    'NEW_REACTIVATED_0_14_TO_50',
                    'RAMP_UP_15_45_TO_100W',
                    'CONSOLIDATION_46_90_TO_100W',
                    'ACTIVE_GROWTH_90_PLUS_BAND_UP',
                    'PROTECTED_ALREADY_MEETING_GOAL',
                    'NO_DATA_OR_NO_ACTION'
                )),
            assigned_program_v1             text NOT NULL,
            subsegment                      text,
            objective                       text NOT NULL,
            reason_code                     text NOT NULL,
            priority_rank                   integer NOT NULL,
            operational_age_days            integer,
            weekly_trips                    integer,
            activation_window_trips         integer,
            inactivity_days                 integer,
            value_tier                      text,
            productivity_band               text,
            trend                           text,
            target_metric                   text,
            baseline_metric                 text,
            export_to_control_loop          boolean NOT NULL DEFAULT true,
            source_snapshot_date            date,
            source_explorer_target_date     date,
            source_version                  text NOT NULL DEFAULT 'exclusive_lists_v1',
            created_at                      timestamptz NOT NULL DEFAULT now(),
            updated_at                      timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (generated_date, driver_profile_id)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ewd_date
            ON growth.yango_lima_exclusive_driver_worklist_daily (generated_date)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ewd_universe
            ON growth.yango_lima_exclusive_driver_worklist_daily (assigned_universe_v1)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ewd_program
            ON growth.yango_lima_exclusive_driver_worklist_daily (assigned_program_v1)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ewd_export
            ON growth.yango_lima_exclusive_driver_worklist_daily (export_to_control_loop)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ewd_priority
            ON growth.yango_lima_exclusive_driver_worklist_daily (priority_rank)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ewd_driver
            ON growth.yango_lima_exclusive_driver_worklist_daily (driver_profile_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ewd_date_universe
            ON growth.yango_lima_exclusive_driver_worklist_daily (generated_date, assigned_universe_v1)
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_exclusive_driver_worklist_daily")
