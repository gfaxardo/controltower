"""
PASO 3D E2E — Panel de caza REAL vs PLAN usando yego_integral.parks (o dim.dim_park).

- REAL: universo por park desde yego_integral.parks (id, name, city, country) si existe,
  si no desde dim.dim_park. Filtros anti-basura en tipo_servicio.
- PLAN: v_plan_lob_universe_for_hunt desde plan.plan_lob_long.
"""

from alembic import op
from sqlalchemy import text

revision = "026_real_plan_hunt_parks"
down_revision = "025_filter_lob_hunt_address"
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
        # yego_integral.parks: id, name, city, country (mapping usuario)
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
        # Fallback: dim.dim_park (park_id, park_name, city, country)
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

    # D) PLAN para caza desde plan.plan_lob_long
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_universe_for_hunt CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_lob_universe_for_hunt AS
        SELECT
          LOWER(TRIM(country)) AS country,
          LOWER(TRIM(city)) AS city,
          LOWER(TRIM(plan_lob_base)) AS plan_lob,
          SUM(trips_plan) AS plan_trips,
          SUM(revenue_plan) AS plan_revenue
        FROM plan.plan_lob_long
        GROUP BY 1, 2, 3
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_universe_for_hunt CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    # Restaurar definiciones de 025 (v_real) y 023 (v_plan)
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
    op.execute("""
        CREATE VIEW ops.v_plan_lob_universe_for_hunt AS
        SELECT country, city, plan_lob_name AS plan_lob,
               COALESCE(trips_plan, 0) AS plan_trips, COALESCE(revenue_plan, 0) AS plan_revenue
        FROM ops.v_plan_lob_universe_raw
    """)
