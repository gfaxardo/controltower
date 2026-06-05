"""
179 — YEGO Lima Growth: LoopControl Export Job Run (Fase LC-1.1)

Creates:
- growth.yango_lima_loopcontrol_export_job_run
- growth.yango_lima_loopcontrol_export_job_program

down_revision: 178_yego_lima_loopcontrol_export
"""

from alembic import op

revision = "179_yego_lima_loopcontrol_export_job"
down_revision = "178_yego_lima_loopcontrol_export"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_loopcontrol_export_job_run (
            job_run_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_date                date NOT NULL,
            started_at              timestamptz NOT NULL DEFAULT now(),
            finished_at             timestamptz NULL,
            status                  text NOT NULL DEFAULT 'running',
            triggered_by            text NOT NULL DEFAULT 'manual',
            dry_run                 boolean NOT NULL DEFAULT false,
            freshness_status        text NULL,
            programs_requested      text[] NULL,
            total_contacts_sent     integer NOT NULL DEFAULT 0,
            total_contacts_inserted integer NOT NULL DEFAULT 0,
            total_contacts_skipped  integer NOT NULL DEFAULT 0,
            exports_created         integer NOT NULL DEFAULT 0,
            warnings                jsonb NULL,
            errors                  jsonb NULL,
            summary                 jsonb NULL
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_loopcontrol_export_job_program (
            job_run_id              uuid NOT NULL,
            program_code            text NOT NULL,
            campaign_name           text NULL,
            export_id               uuid NULL,
            campaign_id_external    text NULL,
            limit_requested         integer NOT NULL DEFAULT 100,
            contacts_sent           integer NOT NULL DEFAULT 0,
            contacts_inserted       integer NOT NULL DEFAULT 0,
            contacts_skipped        integer NOT NULL DEFAULT 0,
            status                  text NOT NULL DEFAULT 'pending',
            error_message           text NULL,
            created_at              timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (job_run_id, program_code)
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_job_run_date ON growth.yango_lima_loopcontrol_export_job_run (run_date DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_job_run_status ON growth.yango_lima_loopcontrol_export_job_run (status);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_loopcontrol_export_job_program;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_loopcontrol_export_job_run;")
