"""
CT-HOURLY-FIRST-FINAL-UNIFICATION: actualizar data_freshness_expectations para real_lob y real_lob_drill.
Fuente de verdad pasa a ser mv_real_lob_day_v2 (y drill se puebla desde day_v2/week_v3);
el audit de freshness debe comparar contra day_v2, no contra v_trips_real_canon.
"""
from alembic import op

revision = "102_real_lob_freshness_source_day_v2"
down_revision = "101_real_rollup_from_day_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE ops.data_freshness_expectations
        SET source_object = 'ops.mv_real_lob_day_v2', source_date_column = 'trip_date', updated_at = now()
        WHERE dataset_name = 'real_lob'
    """)
    op.execute("""
        UPDATE ops.data_freshness_expectations
        SET source_object = 'ops.mv_real_lob_day_v2', source_date_column = 'trip_date', updated_at = now()
        WHERE dataset_name = 'real_lob_drill'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE ops.data_freshness_expectations
        SET source_object = 'ops.v_trips_real_canon', source_date_column = 'fecha_inicio_viaje', updated_at = now()
        WHERE dataset_name = 'real_lob'
    """)
    op.execute("""
        UPDATE ops.data_freshness_expectations
        SET source_object = 'ops.v_trips_real_canon', source_date_column = 'fecha_inicio_viaje', updated_at = now()
        WHERE dataset_name = 'real_lob_drill'
    """)
