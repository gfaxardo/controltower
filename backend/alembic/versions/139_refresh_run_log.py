"""
139 — Refresh Run Log: trazabilidad de refrescos con advisory locks.

Crea tabla ops.refresh_run_log para registrar cada ejecución de refresh
(pipeline, script, job programado) con metadata de lock, scope, periodo y resultado.

También crea la vista ops.v_refresh_latest_status para consulta rápida
del último estado por refresh_name/pipeline_name/step_name.

Fase 1B — Refresh Hardening: Advisory Locks + Ledger.
"""

from alembic import op

revision = "139_refresh_run_log"
down_revision = "138_plan_versions_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.refresh_run_log (
            id                  BIGSERIAL PRIMARY KEY,
            refresh_name        TEXT NOT NULL,
            pipeline_name       TEXT,
            step_name           TEXT,
            trigger_source      TEXT NOT NULL DEFAULT 'unknown',
            environment         TEXT,
            host_name           TEXT,
            process_id          INTEGER,
            lock_key            BIGINT,
            lock_acquired       BOOLEAN DEFAULT false,
            grain               TEXT DEFAULT 'unknown',
            scope               JSONB,
            period_start        DATE,
            period_end          DATE,
            period_status       TEXT NOT NULL DEFAULT 'unknown',
            status              TEXT NOT NULL DEFAULT 'running',
            started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at         TIMESTAMPTZ,
            duration_seconds    NUMERIC,
            rows_affected       BIGINT,
            source_min_date     DATE,
            source_max_date     DATE,
            error_message       TEXT,
            warning_message     TEXT,
            code_version        TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        COMMENT ON TABLE ops.refresh_run_log IS
        'Registro de trazabilidad de ejecuciones de refresh. Cada corrida (pipeline, script, job) deja una fila con metadata de lock, scope, periodo y resultado.'
    """)

    op.execute("COMMENT ON COLUMN ops.refresh_run_log.trigger_source IS 'manual, cron, deploy, api, startup, scheduler, unknown'")
    op.execute("COMMENT ON COLUMN ops.refresh_run_log.grain IS 'hourly, daily, weekly, monthly, ytd, mixed, unknown'")
    op.execute("COMMENT ON COLUMN ops.refresh_run_log.period_status IS 'open, closed, mixed, backfill, unknown'")
    op.execute("COMMENT ON COLUMN ops.refresh_run_log.status IS 'running, success, failed, skipped, blocked'")

    # Indices
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_refresh_run_log_started_at
        ON ops.refresh_run_log (started_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_refresh_run_log_refresh_name_started_at
        ON ops.refresh_run_log (refresh_name, started_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_refresh_run_log_status_started_at
        ON ops.refresh_run_log (status, started_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_refresh_run_log_pipeline_step_started_at
        ON ops.refresh_run_log (pipeline_name, step_name, started_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_refresh_run_log_scope_gin
        ON ops.refresh_run_log USING GIN (scope)
    """)

    # Vista de último estado
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_refresh_latest_status AS
        SELECT DISTINCT ON (COALESCE(refresh_name, ''), COALESCE(pipeline_name, ''), COALESCE(step_name, ''))
            refresh_name,
            pipeline_name,
            step_name,
            status,
            started_at,
            finished_at,
            duration_seconds,
            source_max_date,
            period_start,
            period_end,
            period_status,
            warning_message,
            error_message,
            lock_acquired,
            trigger_source,
            grain,
            rows_affected,
            environment,
            host_name
        FROM ops.refresh_run_log
        ORDER BY
            COALESCE(refresh_name, ''),
            COALESCE(pipeline_name, ''),
            COALESCE(step_name, ''),
            started_at DESC
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_refresh_latest_status")
    op.execute("DROP TABLE IF EXISTS ops.refresh_run_log")
