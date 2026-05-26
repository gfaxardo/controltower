"""
154 — Projection Upload: Ownership Compatibility (Fase 0.0)

Agrega columnas nullable a staging.control_loop_plan_metric_long para
soportar los nuevos campos de la plantilla versionada:

  - jefe_producto  TEXT   (Jefe Producto)
  - producto       TEXT   (Producto)
  - estado         TEXT   (estado)

NO modifica:
  - ops.plan_trips_monthly (canónica)
  - MVs de serving
  - Omniview
  - Plan vs Real
  - v_plan_projection_control_loop

Estrategia: persistencia controlada mínima en staging SIN afectar serving layer.
Los campos son nullable y NO requeridos para mantener backward compatibility.

down_revision: 153_yango_loyalty_operating_layer
"""

from alembic import op

revision = "154_projection_ownership_compatibility"
down_revision = "153_yango_loyalty_operating_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE staging.control_loop_plan_metric_long
        ADD COLUMN IF NOT EXISTS jefe_producto TEXT
    """)
    op.execute("""
        ALTER TABLE staging.control_loop_plan_metric_long
        ADD COLUMN IF NOT EXISTS producto TEXT
    """)
    op.execute("""
        ALTER TABLE staging.control_loop_plan_metric_long
        ADD COLUMN IF NOT EXISTS estado TEXT
    """)

    op.execute("""
        COMMENT ON COLUMN staging.control_loop_plan_metric_long.jefe_producto IS
        'Fase 0.0 — Ownership: nombre del Jefe Producto responsable de la línea (nullable, metadata futura)'
    """)
    op.execute("""
        COMMENT ON COLUMN staging.control_loop_plan_metric_long.producto IS
        'Fase 0.0 — Ownership: nombre del Producto/agrupación (nullable, metadata futura)'
    """)
    op.execute("""
        COMMENT ON COLUMN staging.control_loop_plan_metric_long.estado IS
        'Fase 0.0 — Ownership: estado de validación del plan (nullable, metadata futura)'
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE staging.control_loop_plan_metric_long
        DROP COLUMN IF EXISTS jefe_producto
    """)
    op.execute("""
        ALTER TABLE staging.control_loop_plan_metric_long
        DROP COLUMN IF EXISTS producto
    """)
    op.execute("""
        ALTER TABLE staging.control_loop_plan_metric_long
        DROP COLUMN IF EXISTS estado
    """)
