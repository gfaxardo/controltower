"""
183 — LC-1.5: Assignment Queue Export Fields

Extends:
- growth.yego_lima_assignment_queue

Adds columns:
- exported_at TIMESTAMP NULL
- campaign_id_external TEXT NULL
- export_batch_id UUID NULL

Adds indexes:
- export_batch_id
- campaign_id_external

queue_status now supports: READY | HELD | EXPORTED | SKIPPED
V1 uses: READY | HELD | EXPORTED. SKIPPED reserved.

down_revision: 182_yego_lima_assignment_queue
"""

from alembic import op

revision = "183_yego_lima_assignment_queue_export"
down_revision = "182_yego_lima_assignment_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE growth.yego_lima_assignment_queue
        ADD COLUMN IF NOT EXISTS exported_at TIMESTAMPTZ NULL;
    """)

    op.execute("""
        ALTER TABLE growth.yego_lima_assignment_queue
        ADD COLUMN IF NOT EXISTS campaign_id_external TEXT NULL;
    """)

    op.execute("""
        ALTER TABLE growth.yego_lima_assignment_queue
        ADD COLUMN IF NOT EXISTS export_batch_id UUID NULL;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_aq_export_batch
        ON growth.yego_lima_assignment_queue (export_batch_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_aq_campaign_ext
        ON growth.yego_lima_assignment_queue (campaign_id_external);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS growth.idx_aq_campaign_ext;")
    op.execute("DROP INDEX IF EXISTS growth.idx_aq_export_batch;")

    op.execute("""
        ALTER TABLE growth.yego_lima_assignment_queue
        DROP COLUMN IF EXISTS export_batch_id;
    """)

    op.execute("""
        ALTER TABLE growth.yego_lima_assignment_queue
        DROP COLUMN IF EXISTS campaign_id_external;
    """)

    op.execute("""
        ALTER TABLE growth.yego_lima_assignment_queue
        DROP COLUMN IF EXISTS exported_at;
    """)
