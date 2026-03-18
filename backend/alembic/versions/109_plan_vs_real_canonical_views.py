"""
Plan vs Real — Fuente REAL canónica (mismo grano que legacy).

Crea:
- ops.v_real_universe_by_park_realkey_canon: real agregado (country, city, park_id, real_tipo_servicio, period_date)
  desde ops.v_trips_real_canon, misma lógica city/country que 038, revenue = SUM(ABS(comision_empresa_asociada)).
- ops.v_plan_vs_real_realkey_canonical: mismo FULL OUTER JOIN que v_plan_vs_real_realkey_final pero usando
  la real canónica; resolución de park_name como 040.

No modifica vistas legacy. Servicio usa switch (source=canonical) para leer esta vista.
"""
from alembic import op

revision = "109_plan_vs_real_canonical"
down_revision = "108_real_monthly_canonical_hist_margin_abs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Real por (country, city, park_id, real_tipo_servicio, period_date) desde canónica
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_realkey_canon CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_universe_by_park_realkey_canon AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
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
            SUM(ABS(COALESCE(comision_empresa_asociada, 0))) AS revenue_real
        FROM with_key
        GROUP BY
            park_id,
            park_name,
            city_key,
            LOWER(TRIM(tipo_servicio::text)),
            (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
    """)

    # 2) Plan vs Real final canónico (mismo contrato que v_plan_vs_real_realkey_final, resolución park_name como 040)
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_realkey_canonical CASCADE")
    op.execute("""
        CREATE VIEW ops.v_plan_vs_real_realkey_canonical AS
        WITH base AS (
            SELECT
                COALESCE(p.country, r.country) AS country,
                COALESCE(p.city, r.city) AS city,
                COALESCE(p.park_id, r.park_id) AS park_id,
                r.park_name AS base_park_name,
                COALESCE(p.real_tipo_servicio, r.real_tipo_servicio) AS real_tipo_servicio,
                COALESCE(p.period_date, r.period_date) AS period_date,
                p.trips_plan,
                r.real_trips AS trips_real,
                p.revenue_plan,
                r.revenue_real AS revenue_real,
                (COALESCE(r.real_trips, 0) - COALESCE(p.trips_plan, 0)) AS variance_trips,
                (COALESCE(r.revenue_real, 0) - COALESCE(p.revenue_plan, 0)) AS variance_revenue
            FROM ops.v_plan_universe_by_park_realkey p
            FULL OUTER JOIN ops.v_real_universe_by_park_realkey_canon r
                ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
               AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
               AND TRIM(COALESCE(p.park_id, '')) = TRIM(COALESCE(r.park_id, ''))
               AND LOWER(TRIM(COALESCE(p.real_tipo_servicio, ''))) = LOWER(TRIM(COALESCE(r.real_tipo_servicio, '')))
               AND p.period_date = r.period_date
        )
        SELECT
            base.country,
            base.city,
            base.park_id,
            COALESCE(
                NULLIF(TRIM(base.base_park_name), ''),
                NULLIF(TRIM(p.name::text), ''),
                NULLIF(TRIM(p.city::text), ''),
                base.park_id::text
            ) AS park_name,
            base.real_tipo_servicio,
            base.period_date,
            base.trips_plan,
            base.trips_real,
            base.revenue_plan,
            base.revenue_real,
            base.variance_trips,
            base.variance_revenue
        FROM base
        LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(base.park_id::text))
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_realkey_canonical CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_realkey_canon CASCADE")
