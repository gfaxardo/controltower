"""
Crear schema yego_integral si no existe (parks en la misma BD que trips_all).
Fallback vista REAL: yego_integral.parks -> public.parks -> dim.dim_park.
"""
from alembic import op
from sqlalchemy import text

revision = "028_yego_integral_parks_fallback"
down_revision = "027_fix_real_hunt_regex"
branch_labels = None
depends_on = None


def _table_exists(conn, schema: str, table: str) -> bool:
    r = conn.execute(
        text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = :s AND table_name = :t)"),
        {"s": schema, "t": table},
    )
    row = r.fetchone()
    return row[0] if row else False


def upgrade() -> None:
    conn = op.get_bind()

    # Schema yego_integral (misma BD que trips_all; aquí puede estar parks)
    op.execute("CREATE SCHEMA IF NOT EXISTS yego_integral")

    use_integral = _table_exists(conn, "yego_integral", "parks")
    use_public = _table_exists(conn, "public", "parks")

    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")

    if use_integral:
        # 1) yego_integral.parks (id, name, city, country)
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
    elif use_public:
        # 2) public.parks (id, name, city; sin country en la tabla -> '')
        op.execute("""
            CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
            SELECT
              p.id AS park_id,
              COALESCE(p.name, p.id, '') AS park_name,
              '' AS country,
              LOWER(TRIM(COALESCE(p.city, ''))) AS city,
              LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
              COUNT(*) AS real_trips,
              MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
              MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
            FROM public.trips_all t
            JOIN public.parks p ON p.id = t.park_id
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) <= 40
              AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
              AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
            GROUP BY p.id, p.name, p.city, LOWER(TRIM(t.tipo_servicio))
        """)
    else:
        # 3) dim.dim_park
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
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    # No borramos el schema yego_integral (puede tener datos)
    # Restaurar vista con lógica 027 (yego_integral o dim)
    conn = op.get_bind()
    if _table_exists(conn, "yego_integral", "parks"):
        op.execute("""
            CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
            SELECT p.id AS park_id, COALESCE(p.name, p.id, '') AS park_name,
              LOWER(TRIM(COALESCE(p.country, ''))) AS country, LOWER(TRIM(COALESCE(p.city, ''))) AS city,
              LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio, COUNT(*) AS real_trips,
              MIN((t.fecha_inicio_viaje)::date) AS first_seen_date, MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
            FROM public.trips_all t JOIN yego_integral.parks p ON p.id = t.park_id
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) <= 40
              AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
              AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
            GROUP BY p.id, p.name, p.country, p.city, LOWER(TRIM(t.tipo_servicio))
        """)
    else:
        op.execute("""
            CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
            SELECT p.park_id, COALESCE(p.park_name, p.park_id, '') AS park_name,
              LOWER(TRIM(COALESCE(p.country, ''))) AS country, LOWER(TRIM(COALESCE(p.city, ''))) AS city,
              LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio, COUNT(*) AS real_trips,
              MIN((t.fecha_inicio_viaje)::date) AS first_seen_date, MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
            FROM public.trips_all t JOIN dim.dim_park p ON p.park_id = t.park_id
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) <= 40
              AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
              AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
            GROUP BY p.park_id, p.park_name, p.country, p.city, LOWER(TRIM(t.tipo_servicio))
        """)
