"""
PASO 3D E2E — Vista con JOIN B (LOWER+TRIM+REPLACE '-' ) para máximo match parks↔trips_all.
Trazabilidad: misma definición que aplica paso3d_fix_export_vacio_e2e cuando match_B > 0.
"""
from alembic import op

revision = "031_real_universe_join_b"
down_revision = "030_join_parks_robusto"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.city::text AS park_id,
          COALESCE(
            NULLIF(TRIM(p.created_at::text), ''),
            NULLIF(TRIM(p.name::text), ''),
            NULLIF(TRIM(p.id::text), ''),
            p.city::text
          ) AS park_name,
          ''::text AS country,
          LOWER(TRIM(p.id::text)) AS city,
          LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p
          ON REPLACE(LOWER(TRIM(p.city::text)), '-', '') = REPLACE(LOWER(TRIM(t.park_id::text)), '-', '')
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
        GROUP BY 1, 2, 3, 4, 5
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.city::text AS park_id,
          COALESCE(
            NULLIF(TRIM(p.created_at::text), ''),
            NULLIF(TRIM(p.id::text), ''),
            p.city::text
          ) AS park_name,
          ''::text AS country,
          LOWER(TRIM(p.id::text)) AS city,
          LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p
          ON LOWER(TRIM(p.city::text)) = LOWER(TRIM(t.park_id::text))
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
        GROUP BY 1, 2, 3, 4, 5
    """)
