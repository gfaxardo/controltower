"""
PASO 3D FIX — JOIN parks robusto: LOWER + TRIM + CAST para evitar fallos por tipo/espacios.
"""
from alembic import op

revision = "030_join_parks_robusto"
down_revision = "029_public_parks_park_name"
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
        WHERE t.tipo_servicio IS NOT NULL
          AND t.condicion = 'Completado'
        GROUP BY 1, 2, 3, 4, 5
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    # Restaurar vista 029 (join simple + filtros anti-basura)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.city AS park_id,
          COALESCE(
            NULLIF(TRIM(p.created_at::text), ''),
            NULLIF(TRIM(p.id::text), ''),
            p.city::text
          ) AS park_name,
          '' AS country,
          LOWER(TRIM(COALESCE(p.id, ''))) AS city,
          LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p ON p.city = t.park_id
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
          AND LENGTH(TRIM(t.tipo_servicio)) <= 40
          AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
          AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
        GROUP BY p.city, p.created_at, p.id, LOWER(TRIM(t.tipo_servicio))
    """)
