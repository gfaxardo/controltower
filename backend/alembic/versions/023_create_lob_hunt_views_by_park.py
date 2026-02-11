"""create_lob_hunt_views_by_park

Revision ID: 023_lob_hunt_by_park
Revises: 022_lob_resolution_homologation
Create Date: 2026-01-23 04:00:00.000000

E2E Export para cazar LOB manual: vista REAL por park_id/park_name, PLAN for hunt, índice.
"""

from alembic import op

revision = "023_lob_hunt_by_park"
down_revision = "022_lob_resolution_homologation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Índice opcional (crear manualmente si trips_all es grande, con timeout mayor):
    # CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_park_tipo_fecha
    # ON public.trips_all (park_id, tipo_servicio, (fecha_inicio_viaje::date))
    # WHERE tipo_servicio IS NOT NULL AND condicion = 'Completado';

    # A) Vista REAL agregada por park (para caza con park_id/park_name como filtro 1)
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.park_id,
          COALESCE(p.park_name, p.park_id, '') AS park_name,
          COALESCE(p.country, '') AS country,
          COALESCE(p.city, '') AS city,
          TRIM(LOWER(COALESCE(t.tipo_servicio, ''))) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN(t.fecha_inicio_viaje::date) AS first_seen_date,
          MAX(t.fecha_inicio_viaje::date) AS last_seen_date
        FROM public.trips_all t
        JOIN dim.dim_park p ON p.park_id = t.park_id
        WHERE t.tipo_servicio IS NOT NULL
          AND t.condicion = 'Completado'
        GROUP BY p.park_id, p.park_name, p.country, p.city, TRIM(LOWER(COALESCE(t.tipo_servicio, '')))
    """)

    # B) Vista PLAN "para caza": misma lógica que v_plan_lob_universe_raw (staging); si existe plan_lob_long se puede recrear después
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_universe_for_hunt CASCADE")
    op.execute("""
        CREATE VIEW ops.v_plan_lob_universe_for_hunt AS
        SELECT country, city, plan_lob_name AS plan_lob,
               COALESCE(trips_plan, 0) AS plan_trips, COALESCE(revenue_plan, 0) AS plan_revenue
        FROM ops.v_plan_lob_universe_raw
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_universe_for_hunt")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt")
