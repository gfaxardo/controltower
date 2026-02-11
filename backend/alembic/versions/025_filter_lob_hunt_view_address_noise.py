"""
Filtrar ruido tipo "dirección" en v_real_universe_by_park_for_hunt.

En trips_all.tipo_servicio a veces aparece texto que no es LOB (direcciones, etc.).
Excluimos en la vista valores que parecen direcciones para que el template de
homologación no se llene de filas inútiles.
"""

from alembic import op

revision = "025_filter_lob_hunt_address"
down_revision = "024_lob_homologation_park"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
          AND LENGTH(TRIM(t.tipo_servicio)) <= 60
          AND t.tipo_servicio NOT ILIKE '%%municipio%%'
          AND t.tipo_servicio NOT ILIKE '%%calle%%'
          AND t.tipo_servicio NOT ILIKE '%%carrera%%'
          AND t.tipo_servicio NOT ILIKE '%%avenida%%'
          AND t.tipo_servicio NOT ILIKE '%%comuna%%'
        GROUP BY p.park_id, p.park_name, p.country, p.city, TRIM(LOWER(COALESCE(t.tipo_servicio, '')))
    """)


def downgrade() -> None:
    # Restaurar vista sin filtro de direcciones (igual que en 023)
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
