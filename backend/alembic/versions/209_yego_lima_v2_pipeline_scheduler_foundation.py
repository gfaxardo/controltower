"""
209 — LG-SCH-2A: Lima Growth V2 Daily Pipeline Scheduler Foundation

Creates:
- growth.yego_lima_v2_pipeline_run_log
- growth.yego_lima_v2_pipeline_step_log
- growth.yego_lima_v2_freshness_registry

Additive. No DROP. Shadow mode only — no production impact.

down_revision: 208_merge_cf_h2d_heads
"""

from alembic import op

revision = "209_yego_lima_v2_pipeline_scheduler_foundation"
down_revision = "208_merge_cf_h2d_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_pipeline_run_log (
            run_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            target_date     date NOT NULL,
            status          text NOT NULL DEFAULT 'RUNNING',
            started_at      timestamptz NOT NULL DEFAULT now(),
            finished_at     timestamptz,
            duration_ms     integer,
            triggered_by    text DEFAULT 'manual',
            steps_json      jsonb,
            error_message   text,
            created_at      timestamptz NOT NULL DEFAULT now()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_v2_pipeline_run_target_date "
        "ON growth.yego_lima_v2_pipeline_run_log (target_date);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_v2_pipeline_run_status "
        "ON growth.yego_lima_v2_pipeline_run_log (status);"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_pipeline_step_log (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id          uuid NOT NULL REFERENCES growth.yego_lima_v2_pipeline_run_log(run_id),
            target_date     date NOT NULL,
            step_name       text NOT NULL,
            step_order      integer NOT NULL,
            status          text NOT NULL DEFAULT 'PENDING',
            rows_before     integer,
            rows_after      integer,
            duration_ms     integer,
            error_message   text,
            started_at      timestamptz NOT NULL DEFAULT now(),
            finished_at     timestamptz,
            created_at      timestamptz NOT NULL DEFAULT now()
        );
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_v2_pipeline_step_run_id "
        "ON growth.yego_lima_v2_pipeline_step_log (run_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_v2_pipeline_step_target_date "
        "ON growth.yego_lima_v2_pipeline_step_log (target_date);"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_v2_freshness_registry (
            component           text NOT NULL,
            last_refresh_at     timestamptz,
            freshness_status    text DEFAULT 'UNKNOWN',
            latency_minutes     integer,
            run_id              text,
            max_data_date       date,
            rows_count          integer,
            updated_at          timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (component)
        );
    """)

    op.execute("""
        INSERT INTO growth.yego_lima_v2_freshness_registry (component, freshness_status)
        VALUES
            ('activity_daily', 'UNKNOWN'),
            ('activity_weekly', 'UNKNOWN'),
            ('activity_monthly', 'UNKNOWN'),
            ('lifecycle_daily', 'UNKNOWN'),
            ('taxonomy_v2', 'UNKNOWN'),
            ('program_v2', 'UNKNOWN'),
            ('movement_fact', 'UNKNOWN'),
            ('observability_fact', 'UNKNOWN'),
            ('effectiveness_fact', 'UNKNOWN')
        ON CONFLICT (component) DO NOTHING
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_v2_pipeline_step_log;")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_v2_pipeline_run_log;")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_v2_freshness_registry;")
