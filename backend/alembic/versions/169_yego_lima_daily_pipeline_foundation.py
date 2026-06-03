"""
169 — YEGO Lima Growth: Daily Pipeline Orchestrator Foundation

Creates:
- growth.yango_lima_pipeline_run_log
- growth.yango_lima_pipeline_run_step_log

Additive. No DROP.

down_revision: 168_yego_lima_impact_attribution_engine
"""

from alembic import op

revision = "169_yego_lima_daily_pipeline_foundation"
down_revision = "168_yego_lima_impact_attribution_engine"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_pipeline_run_log (
            run_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_date        date NOT NULL,
            started_at      timestamptz NOT NULL DEFAULT now(),
            finished_at     timestamptz NULL,
            overall_status  text NOT NULL DEFAULT 'running',
            requested_by    text NULL,
            dry_run         boolean NOT NULL DEFAULT false,
            config          jsonb NULL,
            summary         jsonb NULL,
            warnings        jsonb NULL,
            errors          jsonb NULL
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_run_date ON growth.yango_lima_pipeline_run_log (run_date);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_pipeline_run_step_log (
            run_id          uuid NOT NULL REFERENCES growth.yango_lima_pipeline_run_log(run_id),
            step_name       text NOT NULL,
            step_order      integer NOT NULL,
            status          text NOT NULL DEFAULT 'pending',
            started_at      timestamptz NULL,
            finished_at     timestamptz NULL,
            duration_ms     integer NULL,
            summary         jsonb NULL,
            error_message   text NULL,
            PRIMARY KEY (run_id, step_name)
        );
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_pipeline_run_step_log;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_pipeline_run_log;")
