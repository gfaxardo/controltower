"""
Plan vs Real — Tablas de auditoría: paridad legacy vs canónico y log de uso de fuente.

- ops.plan_vs_real_parity_audit: resultado de cada ejecución del script de paridad (run_at, scope, diagnosis, data_completeness, details).
- ops.plan_vs_real_source_usage_log: log de uso de fuente (legacy/canonical) por request (opcional, para deprecación futura).
"""
from alembic import op
import sqlalchemy as sa

revision = "110_plan_vs_real_parity_audit"
down_revision = "109_plan_vs_real_canonical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.plan_vs_real_parity_audit (
            id SERIAL PRIMARY KEY,
            run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            scope TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            max_diff_pct NUMERIC(10,4),
            data_completeness TEXT NOT NULL DEFAULT 'FULL',
            details JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_plan_vs_real_parity_audit_run_at
        ON ops.plan_vs_real_parity_audit (run_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_plan_vs_real_parity_audit_scope
        ON ops.plan_vs_real_parity_audit (scope)
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.plan_vs_real_source_usage_log (
            id SERIAL PRIMARY KEY,
            used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            source TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            request_params JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_plan_vs_real_source_usage_log_used_at
        ON ops.plan_vs_real_source_usage_log (used_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_plan_vs_real_source_usage_log_source
        ON ops.plan_vs_real_source_usage_log (source)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.plan_vs_real_source_usage_log")
    op.execute("DROP TABLE IF EXISTS ops.plan_vs_real_parity_audit")
