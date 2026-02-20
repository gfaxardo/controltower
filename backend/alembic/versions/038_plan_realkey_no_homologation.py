"""
E2E PASO A — Plan vs Real SIN homologación LOB.
Llave única: (country, city, park_id, real_tipo_servicio, period_date).
- Tabla staging.plan_projection_realkey_raw
- Vistas: v_plan_universe_by_park_realkey, v_real_universe_by_park_realkey,
  v_plan_vs_real_realkey_final, v_plan_vs_real_city_month
- Índices para performance.
Real mensual: MODO 1 desde trips_all con period_date = date_trunc('month', fecha_inicio_viaje)::date.
Índice opcional para performance (ejecutar manualmente si trips_all es grande):
  CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_realkey_month
  ON public.trips_all (park_id, tipo_servicio, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE));
"""
from alembic import op

revision = "038_plan_realkey_no_homologation"
down_revision = "037_join_park_real_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Tabla staging plan por llave real
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")
    op.execute("""
        CREATE TABLE IF NOT EXISTS staging.plan_projection_realkey_raw (
            plan_realkey_id SERIAL PRIMARY KEY,
            country TEXT,
            city TEXT,
            park_id VARCHAR(255),
            real_tipo_servicio TEXT,
            year SMALLINT,
            month SMALLINT,
            period_date DATE,
            trips_plan NUMERIC,
            active_drivers_plan NUMERIC,
            avg_ticket_plan NUMERIC,
            revenue_plan NUMERIC,
            trips_per_driver_plan NUMERIC,
            loaded_at TIMESTAMP DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_plan_realkey_raw_period_keys
        ON staging.plan_projection_realkey_raw(period_date, country, city, park_id, real_tipo_servicio)
    """)

    # 2) Vista plan agregada por (country, city, park_id, real_tipo_servicio, period_date)
    op.execute("DROP VIEW IF EXISTS ops.v_plan_universe_by_park_realkey CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_universe_by_park_realkey AS
        SELECT
            LOWER(TRIM(COALESCE(country, ''))) AS country,
            LOWER(TRIM(COALESCE(city, ''))) AS city,
            TRIM(COALESCE(park_id, '')) AS park_id,
            LOWER(TRIM(COALESCE(real_tipo_servicio, ''))) AS real_tipo_servicio,
            period_date,
            SUM(trips_plan) AS trips_plan,
            SUM(active_drivers_plan) AS active_drivers_plan,
            SUM(revenue_plan) AS revenue_plan,
            COUNT(*) AS raw_rows
        FROM staging.plan_projection_realkey_raw
        WHERE period_date IS NOT NULL
        GROUP BY
            LOWER(TRIM(COALESCE(country, ''))),
            LOWER(TRIM(COALESCE(city, ''))),
            TRIM(COALESCE(park_id, '')),
            LOWER(TRIM(COALESCE(real_tipo_servicio, ''))),
            period_date
    """)

    # 3) Vista real por (country, city, park_id, real_tipo_servicio, period_date)
    # MODO 1: desde trips_all con period_date = date_trunc('month', fecha_inicio_viaje)::date
    # Misma lógica city/country que v_real_universe_by_park_for_hunt (035)
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_realkey CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_realkey AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM public.trips_all t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) < 100
              AND t.tipo_servicio NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                park_id_raw,
                COALESCE(
                    NULLIF(TRIM(park_name_raw::text), ''),
                    NULLIF(TRIM(park_city_raw::text), ''),
                    park_id_raw::text
                ) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                LOWER(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                        'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')
                ) AS city_key
            FROM with_city
        )
        SELECT
            park_id::text AS park_id,
            park_name,
            COALESCE(NULLIF(city_key, ''), '') AS city,
            CASE
                WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                ELSE ''
            END AS country,
            LOWER(TRIM(tipo_servicio::text)) AS real_tipo_servicio,
            (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS period_date,
            COUNT(*) AS real_trips,
            SUM(COALESCE(comision_empresa_asociada, 0)) AS revenue_real
        FROM with_key
        GROUP BY
            park_id,
            park_name,
            city_key,
            LOWER(TRIM(tipo_servicio::text)),
            (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
    """)

    # 4) Vista final Plan vs Real (FULL OUTER JOIN por llave real)
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_realkey_final CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_realkey_final AS
        SELECT
            COALESCE(p.country, r.country) AS country,
            COALESCE(p.city, r.city) AS city,
            COALESCE(p.park_id, r.park_id) AS park_id,
            r.park_name,
            COALESCE(p.real_tipo_servicio, r.real_tipo_servicio) AS real_tipo_servicio,
            COALESCE(p.period_date, r.period_date) AS period_date,
            p.trips_plan,
            r.real_trips AS trips_real,
            p.revenue_plan,
            r.revenue_real AS revenue_real,
            (COALESCE(r.real_trips, 0) - COALESCE(p.trips_plan, 0)) AS variance_trips,
            (COALESCE(r.revenue_real, 0) - COALESCE(p.revenue_plan, 0)) AS variance_revenue
        FROM ops.v_plan_universe_by_park_realkey p
        FULL OUTER JOIN ops.v_real_universe_by_park_realkey r
            ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
           AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
           AND TRIM(COALESCE(p.park_id, '')) = TRIM(COALESCE(r.park_id, ''))
           AND LOWER(TRIM(COALESCE(p.real_tipo_servicio, ''))) = LOWER(TRIM(COALESCE(r.real_tipo_servicio, '')))
           AND p.period_date = r.period_date
    """)

    # 5) Vista agregada por (country, city, period_date) para panel ejecutivo
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_city_month CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_city_month AS
        SELECT
            country,
            city,
            period_date,
            SUM(trips_plan) AS trips_plan,
            SUM(trips_real) AS trips_real,
            SUM(revenue_plan) AS revenue_plan,
            SUM(revenue_real) AS revenue_real,
            SUM(variance_trips) AS variance_trips,
            SUM(variance_revenue) AS variance_revenue
        FROM ops.v_plan_vs_real_realkey_final
        GROUP BY country, city, period_date
        ORDER BY country, city, period_date
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_city_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_realkey_final CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_realkey CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_universe_by_park_realkey CASCADE")
    op.execute("DROP TABLE IF EXISTS staging.plan_projection_realkey_raw")
