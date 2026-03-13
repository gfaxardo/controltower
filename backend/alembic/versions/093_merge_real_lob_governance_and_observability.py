"""
Merge de heads: REAL LOB dimension governance + Observability registry.

Une las ramas:
- 090_real_dimension_governance (dimensiones canónicas REAL: dim_lob_group, dim_lob_real, dim_service_type; vistas)
- 092_observability_registry (registro de artefactos y log de refresh)

Esta migración NO altera schema. Solo resuelve la divergencia de heads para que
'alembic upgrade head' deje un único head y los entornos puedan avanzar de forma lineal.

Motivo: el repo tenía dos líneas desde 079 (080_real_lob_canonical -> 090_real_dimension_governance
vs 080_mv_driver_... -> ... -> 092_observability_registry). Cierre CT-REAL-LOB-CLOSURE.
"""
from alembic import op

revision = "093_merge_real_lob_and_observability"
down_revision = ("090_real_dimension_governance", "092_observability_registry")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge migration: no schema changes.
    pass


def downgrade() -> None:
    # Merge migration: no schema changes.
    pass
