"""
Añade columna notes a ops.data_freshness_expectations.
Status SOURCE_STALE/DERIVED_STALE se usan en aplicación; no requieren cambio de schema.
"""
from alembic import op

revision = "073_data_freshness_notes"
down_revision = "072_data_freshness_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE ops.data_freshness_expectations
        ADD COLUMN IF NOT EXISTS notes text
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE ops.data_freshness_expectations DROP COLUMN IF EXISTS notes")
