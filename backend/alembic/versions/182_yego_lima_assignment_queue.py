"""
182 — LG-2.5B: Assignment Queue

Creates:
- growth.yego_lima_assignment_queue

Persistent operational queue from worklist.
Regla V1: no duplicados por assignment_date + driver_id + program_code.
queue_status: READY | HELD.
HELD si phone vacio o assigned_channel = UNASSIGNED.

down_revision: 181_raw_yango_landing
"""

from alembic import op

revision = "182_yego_lima_assignment_queue"
down_revision = "181_raw_yango_landing"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_assignment_queue (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            assignment_batch_id     uuid NOT NULL,
            assignment_date         date NOT NULL,

            driver_id               text NOT NULL,
            driver_name             text NULL,
            phone                   text NULL,

            program_code            text NOT NULL,
            program_name            text NULL,
            priority_rank           integer NULL,

            assigned_channel        text NULL,

            opportunity_reason      text NULL,
            last_trip_date          timestamptz NULL,
            recent_trips            integer NULL,

            country                 text NULL,
            city                    text NULL,
            park                    text NULL,

            queue_status            text NOT NULL DEFAULT 'READY',

            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_aq_date
        ON growth.yego_lima_assignment_queue (assignment_date);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_aq_batch
        ON growth.yego_lima_assignment_queue (assignment_batch_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_aq_status
        ON growth.yego_lima_assignment_queue (queue_status);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_aq_program
        ON growth.yego_lima_assignment_queue (program_code);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_aq_channel
        ON growth.yego_lima_assignment_queue (assigned_channel);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_aq_driver
        ON growth.yego_lima_assignment_queue (driver_id);
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_aq_unique_driver_program_date
        ON growth.yego_lima_assignment_queue (assignment_date, driver_id, program_code);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_assignment_queue;")
