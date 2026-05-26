"""153 — Yango Loyalty Operating Layer — Fase 3A.1.

Agrega:
  - updated_by a goals y manual_results
  - Columnas freshness a kpi_registry
"""
from alembic import op

revision = "153_yango_loyalty_operating_layer"
down_revision = "152_yango_loyalty_reachability_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ops.yango_loyalty_monthly_goals
        ADD COLUMN IF NOT EXISTS updated_by TEXT
    """)
    op.execute("""
        ALTER TABLE ops.yango_loyalty_manual_results
        ADD COLUMN IF NOT EXISTS updated_by TEXT
    """)
    op.execute("""
        ALTER TABLE ops.yango_loyalty_kpi_registry
        ADD COLUMN IF NOT EXISTS updated_by TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE ops.yango_loyalty_monthly_goals DROP COLUMN IF EXISTS updated_by")
    op.execute("ALTER TABLE ops.yango_loyalty_manual_results DROP COLUMN IF EXISTS updated_by")
    op.execute("ALTER TABLE ops.yango_loyalty_kpi_registry DROP COLUMN IF EXISTS updated_by")
