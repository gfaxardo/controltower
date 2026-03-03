"""
FASE 3: Driver Lifecycle lee de public.trips_unified.
Recrear ops.v_driver_lifecycle_trips_completed para que use trips_unified en lugar de trips_all.
Las MVs (mv_driver_lifecycle_base, mv_driver_weekly_stats, mv_driver_monthly_stats) leen de esa vista;
no se tocan, solo se refrescan después.
"""
from alembic import op

revision = "055_driver_lifecycle_unified"
down_revision = "054_trips_unified_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_driver_lifecycle_trips_completed CASCADE")
    op.execute("""
        CREATE VIEW ops.v_driver_lifecycle_trips_completed AS
        SELECT
          t.conductor_id,
          t.condicion,
          t.fecha_inicio_viaje AS request_ts,
          COALESCE(t.fecha_finalizacion, t.fecha_inicio_viaje) AS completion_ts,
          t.park_id,
          t.tipo_servicio,
          CASE WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b' ELSE 'b2c' END AS segment
        FROM public.trips_unified t
        WHERE t.condicion = 'Completado'
          AND t.conductor_id IS NOT NULL
          AND t.fecha_inicio_viaje IS NOT NULL
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_driver_lifecycle_trips_completed IS
        'Viajes completados para Driver Lifecycle. Fuente: public.trips_unified (trips_all + trips_2026).'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_driver_lifecycle_trips_completed CASCADE")
    op.execute("""
        CREATE VIEW ops.v_driver_lifecycle_trips_completed AS
        SELECT
          t.conductor_id,
          t.condicion,
          t.fecha_inicio_viaje AS request_ts,
          COALESCE(t.fecha_finalizacion, t.fecha_inicio_viaje) AS completion_ts,
          t.park_id,
          t.tipo_servicio,
          CASE WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b' ELSE 'b2c' END AS segment
        FROM public.trips_all t
        WHERE t.condicion = 'Completado'
          AND t.conductor_id IS NOT NULL
          AND t.fecha_inicio_viaje IS NOT NULL
    """)
