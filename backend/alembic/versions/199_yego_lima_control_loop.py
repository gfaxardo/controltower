"""
199 — LG-CTRL-1.0A: Control Loop States

Creates:
- growth.yego_lima_control_loop_state

Tracks driver workflow states: READY -> ASSIGNED -> CONTACTED -> DONE
down_revision: 198_yego_lima_program_freshness
"""

from alembic import op

revision = "199_yego_lima_control_loop"
down_revision = "198_yego_lima_program_freshness"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_control_loop_state (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            driver_profile_id   text NOT NULL,
            current_state       text NOT NULL DEFAULT 'READY'
                CHECK (current_state IN (
                    'READY', 'ASSIGNED', 'IN_PROGRESS', 'CONTACTED',
                    'NO_ANSWER', 'NOT_INTERESTED', 'CONVERTED', 'DONE', 'CLOSED'
                )),
            previous_state      text,
            state_changed_at    timestamptz NOT NULL DEFAULT now(),
            agent               text,
            channel             text,
            notes               text,
            campaign_id_external text,
            queue_id            uuid,
            program_code        text,
            days_in_current_state integer DEFAULT 0,
            is_stale            boolean DEFAULT false,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_cls_driver ON growth.yego_lima_control_loop_state (driver_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cls_state ON growth.yego_lima_control_loop_state (current_state)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cls_agent ON growth.yego_lima_control_loop_state (agent)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_control_loop_state")
