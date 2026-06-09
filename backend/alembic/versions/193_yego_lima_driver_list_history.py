"""
193 — LG-INFRA-R1.5: Driver List History

Creates:
- growth.yego_lima_driver_list_history

Immutable historical trace of every driver's presence in operational lists.
Never delete rows. Never overwrite exported records.

down_revision: 192_yego_lima_intraday_driver_signal
"""

from alembic import op

revision = "193_yego_lima_driver_list_history"
down_revision = "192_yego_lima_intraday_driver_signal"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_driver_list_history (
            history_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            action_date             date NOT NULL,
            operational_data_date   date,
            driver_profile_id       text NOT NULL,
            program_code            text,
            program_name            text,
            priority_rank           integer,
            queue_status            text NOT NULL DEFAULT 'READY',
            assigned_channel        text,
            queue_id                uuid,
            campaign_id_external    text,
            export_batch_id         uuid,
            assignment_batch_id     uuid,
            exported_at             timestamptz,
            action_status           text,
            source_run_id           uuid,
            policy_id               uuid,
            policy_version          integer,
            snapshot_date           date,
            evidence_json           jsonb DEFAULT '{}'::jsonb,
            created_at              timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_dlh_driver_date_queue
                UNIQUE (action_date, driver_profile_id, queue_id)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dlh_date
        ON growth.yego_lima_driver_list_history (action_date)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dlh_driver
        ON growth.yego_lima_driver_list_history (driver_profile_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dlh_queue
        ON growth.yego_lima_driver_list_history (queue_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dlh_campaign
        ON growth.yego_lima_driver_list_history (campaign_id_external)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dlh_program
        ON growth.yego_lima_driver_list_history (program_code)
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_driver_list_history")
