"""
195 — LG-UX-R2.5: Queue Build Log

Creates:
- growth.yego_lima_queue_build_log

Records every queue build decision with mode, limits, overrides.
Traces operational decisions without touching individual queue rows.

down_revision: 194_yego_lima_scheduler_tick_log
"""

from alembic import op

revision = "195_yego_lima_queue_build_log"
down_revision = "194_yego_lima_scheduler_tick_log"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_queue_build_log (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            assignment_batch_id     uuid NOT NULL,
            assignment_date         date NOT NULL,
            mode                    text NOT NULL DEFAULT 'CAPACITY_LIMITED'
                CHECK (mode IN ('CAPACITY_LIMITED', 'TAKE_ALL', 'PROGRAM_LIMITED', 'CHANNEL_LIMITED')),
            program_limits_json     jsonb DEFAULT '{}'::jsonb,
            channel_limits_json     jsonb DEFAULT '{}'::jsonb,
            filters_json            jsonb DEFAULT '{}'::jsonb,
            override_reason         text,
            requested_by            text DEFAULT 'system',
            created_count           integer DEFAULT 0,
            ready_count             integer DEFAULT 0,
            held_count              integer DEFAULT 0,
            skipped_count           integer DEFAULT 0,
            exported_count          integer DEFAULT 0,
            warnings_json           jsonb DEFAULT '[]'::jsonb,
            created_at              timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_qbl_date
        ON growth.yego_lima_queue_build_log (assignment_date)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_qbl_batch
        ON growth.yego_lima_queue_build_log (assignment_batch_id)
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_queue_build_log")
