"""
Usar conductor_nombre (trips_all/trips_2026) en ops.v_dim_driver_resolved.
En ambas BDs la columna es conductor_nombre, no driver_name.
"""
from alembic import op

revision = "062_conductor_nombre"
down_revision = "061_ops_dim_park_driver_resolved"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_dim_driver_resolved CASCADE")
    op.execute("""
        CREATE VIEW ops.v_dim_driver_resolved AS
        SELECT
            t.conductor_id AS driver_id,
            COALESCE(MAX(NULLIF(TRIM(t.conductor_nombre::text), '')), '') AS driver_name
        FROM public.trips_unified t
        WHERE t.conductor_id IS NOT NULL
        GROUP BY t.conductor_id
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_dim_driver_resolved IS
        'Conductores: driver_id (conductor_id) y driver_name (conductor_nombre). No exponer driver_id en UI.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_dim_driver_resolved CASCADE")
    op.execute("""
        CREATE VIEW ops.v_dim_driver_resolved AS
        SELECT
            t.conductor_id AS driver_id,
            ''::text AS driver_name
        FROM public.trips_unified t
        WHERE t.conductor_id IS NOT NULL
        GROUP BY t.conductor_id
    """)
