"""
224 — LG-TRACE-1B: Exclusive Worklist Transition Daily

Creates:
- growth.yango_lima_exclusive_worklist_transition_daily

Tracks daily movement between exclusive worklists.
Compares consecutive generated_dates to classify 13 transition types.
NOT the full Lifecycle State Machine — V1 operational traceability.

Additive only. No DROP.
down_revision: 223_lg_prog_excl_1e_explainability
"""
from alembic import op

revision = "224_lg_trace_1b_worklist_transition"
down_revision = "223_lg_prog_excl_1e_explainability"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_exclusive_worklist_transition_daily (
            generated_date                      date NOT NULL,
            previous_generated_date             date,
            driver_profile_id                   text NOT NULL,
            driver_id                           text,
            previous_assigned_universe_v1       text,
            previous_productivity_band          text,
            previous_export_to_control_loop     boolean,
            previous_weekly_trips               integer,
            previous_activation_window_trips    integer,
            previous_inactivity_days            integer,
            previous_gap_to_target              integer,
            current_assigned_universe_v1        text,
            current_productivity_band           text,
            current_export_to_control_loop      boolean,
            current_weekly_trips                integer,
            current_activation_window_trips     integer,
            current_inactivity_days             integer,
            current_gap_to_target               integer,
            transition_type                     text NOT NULL
                CHECK (transition_type IN (
                    'ENTERED_LIST', 'STAYED_IN_LIST', 'EXITED_GOAL_MET',
                    'PROTECTED_GOAL_MET', 'MOVED_UP_BAND', 'MOVED_DOWN_BAND',
                    'MOVED_TO_RECOVERY', 'MOVED_TO_CEMETERY',
                    'RECOVERED_TO_ACTIVE', 'EXITED_TO_ACTIVE',
                    'NO_LONGER_EXPORTABLE', 'BECAME_EXPORTABLE', 'NO_DATA'
                )),
            transition_reason                   text NOT NULL,
            goal_met_flag                       boolean NOT NULL DEFAULT false,
            recovered_flag                      boolean NOT NULL DEFAULT false,
            recovered_threshold_days            integer NOT NULL DEFAULT 45,
            inactivity_days_before_return       integer,
            previous_evidence_json              jsonb,
            current_evidence_json               jsonb,
            transition_evidence_json            jsonb,
            source_version                      text NOT NULL DEFAULT 'exclusive_lists_v1',
            writer_version                      text NOT NULL DEFAULT 'transition_v1',
            created_at                          timestamptz NOT NULL DEFAULT now(),
            updated_at                          timestamptz NOT NULL DEFAULT now(),

            PRIMARY KEY (generated_date, driver_profile_id)
        )
    """)

    for idx_name, idx_sql in [
        ("idx_etd_date", "CREATE INDEX IF NOT EXISTS idx_etd_date ON growth.yango_lima_exclusive_worklist_transition_daily (generated_date)"),
        ("idx_etd_type", "CREATE INDEX IF NOT EXISTS idx_etd_type ON growth.yango_lima_exclusive_worklist_transition_daily (transition_type)"),
        ("idx_etd_current", "CREATE INDEX IF NOT EXISTS idx_etd_current ON growth.yango_lima_exclusive_worklist_transition_daily (current_assigned_universe_v1)"),
        ("idx_etd_previous", "CREATE INDEX IF NOT EXISTS idx_etd_previous ON growth.yango_lima_exclusive_worklist_transition_daily (previous_assigned_universe_v1)"),
        ("idx_etd_recovered", "CREATE INDEX IF NOT EXISTS idx_etd_recovered ON growth.yango_lima_exclusive_worklist_transition_daily (recovered_flag)"),
        ("idx_etd_goal_met", "CREATE INDEX IF NOT EXISTS idx_etd_goal_met ON growth.yango_lima_exclusive_worklist_transition_daily (goal_met_flag)"),
        ("idx_etd_driver", "CREATE INDEX IF NOT EXISTS idx_etd_driver ON growth.yango_lima_exclusive_worklist_transition_daily (driver_profile_id)"),
    ]:
        op.execute(idx_sql)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_exclusive_worklist_transition_daily")
