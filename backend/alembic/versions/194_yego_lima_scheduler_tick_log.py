"""
194 — LG-INFRA-R1.6: Scheduler Tick Log

Creates:
- growth.yego_lima_scheduler_tick_log

Records every scheduler tick with full traceability.
Tracks duration, steps executed, errors, catch-up attempts.

down_revision: 193_yego_lima_driver_list_history
"""

from alembic import op

revision = "194_yego_lima_scheduler_tick_log"
down_revision = "193_yego_lima_driver_list_history"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_scheduler_tick_log (
            tick_id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            started_at              timestamptz NOT NULL DEFAULT now(),
            finished_at             timestamptz,
            duration_ms             integer,
            tick_status             text NOT NULL DEFAULT 'STARTED'
                CHECK (tick_status IN (
                    'STARTED', 'SUCCESS', 'FAILED', 'PARTIAL', 'SKIPPED'
                )),
            catch_up_attempted      boolean DEFAULT false,
            catch_up_status         text,
            catch_up_dates_processed integer DEFAULT 0,
            signals_built           integer DEFAULT 0,
            signals_new             integer DEFAULT 0,
            signals_updated         integer DEFAULT 0,
            history_snapshot_rows   integer DEFAULT 0,
            governance_checked      boolean DEFAULT false,
            governance_operability  text,
            operational_date        date,
            new_day_detected        boolean DEFAULT false,
            error_message           text,
            error_type              text,
            remediation             text,
            raw_result_json         jsonb DEFAULT '{}'::jsonb,
            created_at              timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tick_status
        ON growth.yego_lima_scheduler_tick_log (tick_status)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tick_started
        ON growth.yego_lima_scheduler_tick_log (started_at)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tick_date
        ON growth.yego_lima_scheduler_tick_log (operational_date)
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_scheduler_tick_log")
