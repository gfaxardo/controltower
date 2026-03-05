"""
Fix: ops.v_driver_lifecycle_trips_completed debe leer de public.trips_unified, no trips_all.
Estado: la vista fue sobrescrita (ej. por driver_lifecycle_build.sql) y volvió a trips_all.
Resultado: mv_driver_lifecycle_base freshness se queda en 2026-02-01 aunque trips_2026 llega a 2026-03-03.
"""
from alembic import op

revision = "058_fix_driver_lifecycle_source"
down_revision = "057_merge_plan_driver_lifecycle"
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
