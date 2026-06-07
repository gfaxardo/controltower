"""
184 — LC-2A: LoopControl Result Sync Storage

Creates:
- growth.yego_lima_loopcontrol_result_sync

Stores normalized call results from LoopControl.
Matches back to assignment_queue via campaign_id_external + phone.

down_revision: 183_yego_lima_assignment_queue_export
"""

from alembic import op

revision = "184_yego_lima_loopcontrol_result_sync"
down_revision = "183_yego_lima_assignment_queue_export"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_loopcontrol_result_sync (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),

            campaign_id_external    TEXT NOT NULL,
            contact_id              TEXT NULL,
            phone                   TEXT NULL,

            assignment_queue_id     uuid NULL,
            export_batch_id         uuid NULL,
            driver_id               TEXT NULL,

            attempts                INTEGER NULL,
            status                  TEXT NULL,
            disposition             TEXT NULL,
            last_call_at            TIMESTAMPTZ NULL,
            notes                   TEXT NULL,
            agent                   TEXT NULL,

            raw_payload             JSONB NULL,

            synced_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lcrs_campaign
        ON growth.yego_lima_loopcontrol_result_sync (campaign_id_external);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lcrs_export_batch
        ON growth.yego_lima_loopcontrol_result_sync (export_batch_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lcrs_aq_id
        ON growth.yego_lima_loopcontrol_result_sync (assignment_queue_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lcrs_driver
        ON growth.yego_lima_loopcontrol_result_sync (driver_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lcrs_phone
        ON growth.yego_lima_loopcontrol_result_sync (phone);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lcrs_status
        ON growth.yego_lima_loopcontrol_result_sync (status);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lcrs_disposition
        ON growth.yego_lima_loopcontrol_result_sync (disposition);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lcrs_last_call
        ON growth.yego_lima_loopcontrol_result_sync (last_call_at);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_loopcontrol_result_sync;")
