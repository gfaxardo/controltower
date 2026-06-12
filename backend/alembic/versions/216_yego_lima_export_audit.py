"""
216 — LG-EXP-1A: Export Audit Log

Creates:
- growth.yego_lima_export_audit

down_revision: 215_yego_lima_program_v2
"""

from alembic import op

revision = "216_yego_lima_export_audit"
down_revision = "215_yego_lima_program_v2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_export_audit (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            export_id           text NOT NULL UNIQUE,
            source              text NOT NULL,
            filters_json        jsonb DEFAULT '{}'::jsonb,
            selected_columns_json jsonb DEFAULT '[]'::jsonb,
            rows_count          integer DEFAULT 0,
            generated_at        timestamptz NOT NULL DEFAULT now(),
            generated_by        text,
            status              text NOT NULL DEFAULT 'COMPLETED',
            warnings_json       jsonb DEFAULT '[]'::jsonb,
            file_size_bytes     bigint
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_export_audit_source
        ON growth.yego_lima_export_audit (source);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_export_audit_generated_at
        ON growth.yego_lima_export_audit (generated_at DESC);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_export_audit;")
