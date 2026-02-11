"""Corregir regex en v_real_universe_by_park_for_hunt (paréntesis/encoding)."""
from alembic import op
from sqlalchemy import text

revision = "027_fix_real_hunt_regex"
down_revision = "026_real_plan_hunt_parks"
branch_labels = None
depends_on = None


def _use_yego_integral_parks(conn):
    r = conn.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'yego_integral' AND table_name = 'parks'
        )
    """))
    row = r.fetchone()
    return row[0] if row else False


def upgrade() -> None:
    conn = op.get_bind()
    use_integral = _use_yego_integral_parks(conn)

    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    if use_integral:
        op.execute("""
            CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
            SELECT
              p.id AS park_id,
              COALESCE(p.name, p.id, '') AS park_name,
              LOWER(TRIM(COALESCE(p.country, ''))) AS country,
              LOWER(TRIM(COALESCE(p.city, ''))) AS city,
              LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
              COUNT(*) AS real_trips,
              MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
              MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
            FROM public.trips_all t
            JOIN yego_integral.parks p ON p.id = t.park_id
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) <= 40
              AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
              AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
            GROUP BY p.id, p.name, p.country, p.city, LOWER(TRIM(t.tipo_servicio))
        """)
    else:
        op.execute("""
            CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
            SELECT
              p.park_id,
              COALESCE(p.park_name, p.park_id, '') AS park_name,
              LOWER(TRIM(COALESCE(p.country, ''))) AS country,
              LOWER(TRIM(COALESCE(p.city, ''))) AS city,
              LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
              COUNT(*) AS real_trips,
              MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
              MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
            FROM public.trips_all t
            JOIN dim.dim_park p ON p.park_id = t.park_id
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) <= 40
              AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
              AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
            GROUP BY p.park_id, p.park_name, p.country, p.city, LOWER(TRIM(t.tipo_servicio))
        """)


def downgrade() -> None:
    pass  # 026 ya tiene la misma definición corregida
