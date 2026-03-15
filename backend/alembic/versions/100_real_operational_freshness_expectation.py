"""
Añade expectativa de freshness para REAL operacional (hourly-first).
Vista Hoy/Ayer/Semana usa ops.mv_real_lob_day_v2; el banner debe poder reflejar su cobertura.
"""
from alembic import op

revision = "100_real_operational_freshness"
down_revision = "099_real_hourly_first_arch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO ops.data_freshness_expectations
        (dataset_name, grain, expected_delay_days, source_object, source_date_column,
         derived_object, derived_date_column, active, owner, alert_threshold_days)
        VALUES
        ('real_operational', 'day', 1, 'ops.v_trips_real_canon_120d', 'fecha_inicio_viaje',
         'ops.mv_real_lob_day_v2', 'trip_date', true, 'ops', 2)
        ON CONFLICT (dataset_name) DO UPDATE SET
            grain = EXCLUDED.grain,
            expected_delay_days = EXCLUDED.expected_delay_days,
            source_object = EXCLUDED.source_object,
            source_date_column = EXCLUDED.source_date_column,
            derived_object = EXCLUDED.derived_object,
            derived_date_column = EXCLUDED.derived_date_column,
            active = EXCLUDED.active,
            alert_threshold_days = EXCLUDED.alert_threshold_days,
            updated_at = now()
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM ops.data_freshness_expectations WHERE dataset_name = 'real_operational'
    """)
