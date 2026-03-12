"""
Marca trips_base como legacy en expectativas de freshness.
Fuente operativa de viajes: trips_2026 y ops.v_trips_real_canon. trips_all es histórico y puede estar cortada.
"""
from alembic import op

revision = "074_trips_base_legacy"
down_revision = "073_data_freshness_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE ops.data_freshness_expectations
        SET notes = 'Legacy. Fuente histórica (trips_all) cortada; fuente viva: trips_2026. No usar como fuente operativa.'
        WHERE dataset_name = 'trips_base'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE ops.data_freshness_expectations
        SET notes = NULL
        WHERE dataset_name = 'trips_base'
    """)

