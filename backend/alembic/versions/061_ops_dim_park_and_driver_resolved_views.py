"""
Vistas canónicas para presentación sin IDs en UI.
- ops.v_dim_park_resolved: park_id (uso interno), park_name, city, country. Fuente: dim.dim_park.
- ops.v_dim_driver_resolved: driver_id (uso interno), driver_name. Fuente: trips_unified (conductor_id + MAX(conductor_nombre)). Columna en BD: conductor_nombre.
Regla: el frontend y exports NUNCA muestran park_id/driver_id como texto visible; solo name, city, country / driver_name.
"""
from alembic import op

revision = "061_ops_dim_park_driver_resolved"
down_revision = "060_supply_mvs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vista parques resueltos: dim.dim_park como fuente (park_name, city, country)
    op.execute("DROP VIEW IF EXISTS ops.v_dim_park_resolved CASCADE")
    op.execute("""
        CREATE VIEW ops.v_dim_park_resolved AS
        SELECT
            dp.park_id,
            COALESCE(NULLIF(TRIM(dp.park_name::text), ''), dp.park_id::text) AS park_name,
            NULLIF(TRIM(COALESCE(dp.city, '')), '') AS city,
            NULLIF(TRIM(COALESCE(dp.country, '')), '') AS country
        FROM dim.dim_park dp
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_dim_park_resolved IS
        'Parques con nombres legibles para UI. No exponer park_id en etiquetas; usar solo park_name, city, country.'
    """)

    # Vista conductores: driver_id + driver_name. trips_unified puede no tener columna driver_name.
    # Si en el futuro se añade driver_name a trips_all/trips_unified, crear migración que redefina la vista.
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
    op.execute("""
        COMMENT ON VIEW ops.v_dim_driver_resolved IS
        'Conductores (driver_id para uso interno). driver_name vacío si trips_unified no tiene columna driver_name; redefinir vista cuando exista.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_dim_driver_resolved CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_dim_park_resolved CASCADE")
