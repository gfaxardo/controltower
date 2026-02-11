"""
PASO 3D — park_name humano desde public.parks (sin yego_integral.parks).

public.parks en esta BD tiene semántica: city = park_id (UUID), created_at = nombre,
id = ciudad. Join por p.city = t.park_id; park_name = COALESCE(created_at, id, city).
"""
from alembic import op
from sqlalchemy import text

revision = "029_public_parks_park_name"
down_revision = "028_yego_integral_parks_fallback"
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
    use_integral = _table_exists(conn, "yego_integral", "parks")
    use_public = _table_exists(conn, "public", "parks")

    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")

    if use_integral:
        # yego_integral.parks: columnas estándar (id, name, city, country)
        op.execute("""
            CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
            SELECT
              p.id AS park_id,
              COALESCE(NULLIF(TRIM(p.name), ''), p.id::text, '') AS park_name,
              LOWER(TRIM(COALESCE(p.country, ''))) AS country,
              LOWER(TRIM(COALESCE(p.city, ''))) AS city,
              LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
              COUNT(*) AS real_trips,
              MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
              MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
            FROM public.trips_all t
            JOIN yego_integral.parks p ON p.id = t.park_id
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) <= 40
              AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
              AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
            GROUP BY p.id, p.name, p.country, p.city, LOWER(TRIM(t.tipo_servicio))
        """)
    elif use_public:
        # public.parks: city = park_id (UUID), created_at = nombre legible, id = ciudad
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
    else:
        op.execute("""
            CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
            SELECT
              p.park_id,
              COALESCE(NULLIF(TRIM(p.park_name), ''), p.park_id::text, '') AS park_name,
              LOWER(TRIM(COALESCE(p.country, ''))) AS country,
              LOWER(TRIM(COALESCE(p.city, ''))) AS city,
              LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
              COUNT(*) AS real_trips,
              MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
              MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
            FROM public.trips_all t
            JOIN dim.dim_park p ON p.park_id = t.park_id
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) <= 40
              AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
              AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
            GROUP BY p.park_id, p.park_name, p.country, p.city, LOWER(TRIM(t.tipo_servicio))
        """)


def downgrade() -> None:
    # Restaurar lógica 028 (public.parks con p.id = t.park_id, p.name)
    conn = op.get_bind()
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    if _table_exists(conn, "public", "parks"):
        op.execute("""
            CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
            SELECT p.id AS park_id, COALESCE(p.name, p.id, '') AS park_name,
              '' AS country, LOWER(TRIM(COALESCE(p.city, ''))) AS city,
              LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio, COUNT(*) AS real_trips,
              MIN((t.fecha_inicio_viaje)::date) AS first_seen_date, MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
            FROM public.trips_all t JOIN public.parks p ON p.id = t.park_id
            WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) <= 40
              AND TRIM(t.tipo_servicio) !~* 'municipio|calle|carrera|avenida|comuna|jiron|malecon|block|etapa|->'
              AND TRIM(t.tipo_servicio) !~* '^[0-9][0-9.\\-]*\\)$'
            GROUP BY p.id, p.name, p.city, LOWER(TRIM(t.tipo_servicio))
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
