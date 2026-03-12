"""
Tabla ops.audit_query_performance: métricas de cada ejecución de check del audit engine.
Permite observar degradación y detectar timeouts por check_name.
"""
from alembic import op

revision = "076_audit_query_performance"
down_revision = "075_control_tower_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.audit_query_performance (
            id serial PRIMARY KEY,
            check_name text NOT NULL,
            execution_time_ms integer,
            executed_at timestamptz NOT NULL DEFAULT now(),
            status text NOT NULL
        )
    """)
    op.execute("""
        COMMENT ON TABLE ops.audit_query_performance IS
        'Métricas por ejecución de cada check del audit_control_tower: duración, status (OK, TIMEOUT, ERROR).'
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_query_performance_executed_at ON ops.audit_query_performance (executed_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_query_performance_check_name ON ops.audit_query_performance (check_name, executed_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.audit_query_performance CASCADE")
