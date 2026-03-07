"""
Real LOB Drill: uso de tipo_servicio_norm para desglose por tipo de servicio.
- Solo DDL: no-op. La tabla real_drill_dim_fact ya existe (064) y tiene dimension_key.
- El dato con tipo_servicio_norm (en vez de service_type_norm/unknown) se carga vía
  scripts/backfill_real_drill_service_type.py o scripts/backfill_real_lob_mvs.py.
"""
from alembic import op

revision = "069_real_drill_service_type_tipo_norm"
down_revision = "068_real_drill_service_by_park_mv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: estructura ya soportada en 064. Backfill fuera de Alembic.
    pass


def downgrade() -> None:
    # No-op: no revertir datos; los antiguos con 'unknown' no se restauran.
    pass
