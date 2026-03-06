"""
Driver Supply Dynamics: trazabilidad del refresh del pipeline.
- ops.supply_refresh_log: registro de cada corrida (started_at, finished_at, status).
- Permite endpoint de freshness y estado del pipeline.
"""
from alembic import op

revision = "066_supply_refresh_log"
down_revision = "065_driver_segment_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.supply_refresh_log (
            id SERIAL PRIMARY KEY,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            status TEXT NOT NULL DEFAULT 'running',
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        COMMENT ON TABLE ops.supply_refresh_log IS
        'Log de ejecuciones del pipeline ops.refresh_supply_alerting_mvs(). Usado por endpoint /ops/supply/freshness.'
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.supply_refresh_log")
