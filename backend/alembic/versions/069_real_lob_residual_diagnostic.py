"""
Tabla de diagnóstico para brecha service_type -> LOB.
- ops.real_lob_residual_diagnostic: (validated_service_type, lob_group, trips) agregado últimos 90 días.
- Se rellena con scripts/populate_real_lob_residual_diagnostic.py (consulta pesada sobre v_real_trips_with_lob_v2).
- El script run_real_lob_gap_diagnosis.py lee esta tabla para B/C cuando existe y tiene datos.
"""
from alembic import op

revision = "069_real_lob_residual_diagnostic"
down_revision = "068_real_drill_service_by_park_mv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.real_lob_residual_diagnostic (
            validated_service_type text,
            lob_group text,
            trips bigint NOT NULL DEFAULT 0,
            PRIMARY KEY (validated_service_type, lob_group)
        )
    """)
    op.execute("COMMENT ON TABLE ops.real_lob_residual_diagnostic IS 'Agregado (validated_service_type, lob_group, trips) últimos 90 días desde v_real_trips_with_lob_v2; para diagnóstico brecha LOB UNCLASSIFIED.'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.real_lob_residual_diagnostic CASCADE")
