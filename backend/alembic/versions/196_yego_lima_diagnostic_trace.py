"""
196 — LG-DIAG-R1.3A: Diagnostic Trace Persistence

Creates:
- growth.yego_lima_program_decision_trace
- growth.yego_lima_state_transition_trace

Persists decision traces and transition rule deltas.
Append-only. Idempotent by run_id + driver.

down_revision: 195_yego_lima_queue_build_log
"""

from alembic import op

revision = "196_yego_lima_diagnostic_trace"
down_revision = "195_yego_lima_queue_build_log"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_decision_trace (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id                  text NOT NULL,
            snapshot_date           date NOT NULL,
            driver_profile_id       text NOT NULL,
            eligible_programs_json  jsonb DEFAULT '[]'::jsonb,
            selected_program_code   text,
            selection_reason        text,
            opportunity_score       numeric(12,4),
            final_rank              integer,
            policy_version          text DEFAULT 'v1',
            evidence_json           jsonb DEFAULT '{}'::jsonb,
            created_at              timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_dt_driver_snap UNIQUE (run_id, driver_profile_id, snapshot_date)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_state_transition_trace (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id                  text NOT NULL,
            snapshot_before         date NOT NULL,
            snapshot_after          date NOT NULL,
            driver_profile_id       text NOT NULL,
            state_before_json       jsonb DEFAULT '{}'::jsonb,
            state_after_json        jsonb DEFAULT '{}'::jsonb,
            transition_type         text,
            rule_delta_json         jsonb DEFAULT '[]'::jsonb,
            trigger_reason          text,
            evidence_json           jsonb DEFAULT '{}'::jsonb,
            policy_version          text DEFAULT 'v1',
            created_at              timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_tt_driver_snaps UNIQUE (run_id, driver_profile_id, snapshot_before, snapshot_after)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_dt_snapshot ON growth.yego_lima_program_decision_trace (snapshot_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_dt_driver ON growth.yego_lima_program_decision_trace (driver_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tt_snapshots ON growth.yego_lima_state_transition_trace (snapshot_before, snapshot_after)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tt_driver ON growth.yego_lima_state_transition_trace (driver_profile_id)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_decision_trace")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_state_transition_trace")
