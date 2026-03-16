"""
Añadir cancelled_trips a real_drill_dim_fact para exponer cancelaciones en drill REAL.
Poblado por scripts.populate_real_drill_from_hourly_chain desde day_v2/week_v3 (SUM(cancelled_trips)).
"""
from alembic import op

revision = "103_real_drill_dim_fact_cancelled"
down_revision = "102_real_lob_freshness_source_day_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ops.real_drill_dim_fact
        ADD COLUMN IF NOT EXISTS cancelled_trips bigint
    """)
    op.execute("COMMENT ON COLUMN ops.real_drill_dim_fact.cancelled_trips IS 'Viajes cancelados (hourly-first: desde mv_real_lob_day_v2/week_v3)'")


def downgrade() -> None:
    op.execute("ALTER TABLE ops.real_drill_dim_fact DROP COLUMN IF EXISTS cancelled_trips")
