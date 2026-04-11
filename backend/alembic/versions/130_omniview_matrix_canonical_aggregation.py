"""
130 - Endurece Business Slice facts con componentes canónicos de agregación.

Motivación:
- weekly estaba reconstruyendo ratios y drivers desde day_fact con SUM/AVG inválidos.
- avg_ticket y commission_pct necesitan numeradores/denominadores explícitos.
- la Matrix requiere consistencia matemática entre daily / weekly / monthly.
"""

revision = "130_omniview_matrix_canonical_aggregation"
down_revision = "129_ensure_v_real_data_coverage"
branch_labels = None
depends_on = None

from alembic import op


def upgrade() -> None:
    for table in (
        "ops.real_business_slice_month_fact",
        "ops.real_business_slice_day_fact",
        "ops.real_business_slice_week_fact",
    ):
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN IF NOT EXISTS ticket_sum_completed numeric,
            ADD COLUMN IF NOT EXISTS ticket_count_completed bigint,
            ADD COLUMN IF NOT EXISTS total_fare_completed_positive_sum numeric
            """
        )


def downgrade() -> None:
    for table in (
        "ops.real_business_slice_week_fact",
        "ops.real_business_slice_day_fact",
        "ops.real_business_slice_month_fact",
    ):
        op.execute(
            f"""
            ALTER TABLE {table}
            DROP COLUMN IF EXISTS total_fare_completed_positive_sum,
            DROP COLUMN IF EXISTS ticket_count_completed,
            DROP COLUMN IF EXISTS ticket_sum_completed
            """
        )
