"""
REAL LOB Observability: visualización de viajes REAL por LOB (semanal y mensual).
Sin modificar ni depender de ops.v_plan_vs_real_realkey_final.
- canon.dim_lob, canon.map_real_to_lob (mapeo real_tipo_servicio -> LOB)
- ops.v_real_universe_with_lob (real + lob_name = COALESCE(mapped, 'UNCLASSIFIED'))
- ops.v_real_trips_by_lob_month, ops.v_real_trips_by_lob_week
"""
from alembic import op

revision = "041_real_lob_observability"
down_revision = "040_park_name_final_realkey"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Schema canon
    op.execute("CREATE SCHEMA IF NOT EXISTS canon")

    # 2) canon.dim_lob
    op.execute("""
        CREATE TABLE IF NOT EXISTS canon.dim_lob (
            lob_id   SERIAL PRIMARY KEY,
            lob_name TEXT NOT NULL UNIQUE,
            active   BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    op.execute("COMMENT ON TABLE canon.dim_lob IS 'Catálogo canónico de LOB para observabilidad REAL (independiente de Plan vs Real).'")

    # 3) canon.map_real_to_lob (mapeo vigente por valid_from/valid_to)
    op.execute("""
        CREATE TABLE IF NOT EXISTS canon.map_real_to_lob (
            country           TEXT NOT NULL,
            city              TEXT NOT NULL,
            park_id           TEXT NOT NULL,
            real_tipo_servicio TEXT NOT NULL,
            lob_id            INTEGER NOT NULL REFERENCES canon.dim_lob(lob_id),
            valid_from        DATE NOT NULL DEFAULT current_date,
            valid_to          DATE,
            created_at         TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (country, city, park_id, real_tipo_servicio, valid_from),
            CONSTRAINT chk_valid_range CHECK (valid_to IS NULL OR valid_to >= valid_from)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_map_real_to_lob_current
        ON canon.map_real_to_lob (country, city, park_id, real_tipo_servicio)
        WHERE valid_to IS NULL
    """)
    op.execute("COMMENT ON TABLE canon.map_real_to_lob IS 'Mapeo (country, city, park_id, real_tipo_servicio) -> lob_id. valid_to NULL = vigente. Solo para REAL LOB Observability.'")

    # 4) Vista base real con LOB (usa v_real_universe_by_park_realkey, NO toca plan)
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_with_lob CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_with_lob AS
        WITH mapping_current AS (
            SELECT country, city, park_id, real_tipo_servicio, lob_id
            FROM canon.map_real_to_lob
            WHERE valid_to IS NULL
        )
        SELECT
            r.country,
            r.city,
            r.park_id,
            r.park_name,
            r.real_tipo_servicio,
            COALESCE(d.lob_name, 'UNCLASSIFIED') AS lob_name,
            r.period_date,
            r.real_trips AS trips,
            r.revenue_real AS revenue
        FROM ops.v_real_universe_by_park_realkey r
        LEFT JOIN mapping_current m
            ON LOWER(TRIM(r.country)) = LOWER(TRIM(m.country))
           AND LOWER(TRIM(r.city)) = LOWER(TRIM(m.city))
           AND TRIM(r.park_id) = TRIM(m.park_id)
           AND LOWER(TRIM(r.real_tipo_servicio)) = LOWER(TRIM(m.real_tipo_servicio))
        LEFT JOIN canon.dim_lob d ON d.lob_id = m.lob_id AND d.active = true
    """)

    # 5) Agregado mensual por (country, city, lob_name)
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_by_lob_month CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_trips_by_lob_month AS
        SELECT
            country,
            city,
            lob_name,
            period_date AS month_start,
            SUM(trips) AS trips,
            SUM(revenue) AS revenue
        FROM ops.v_real_universe_with_lob
        GROUP BY country, city, lob_name, period_date
        ORDER BY country, city, lob_name, period_date
    """)

    # 6) Base real por semana (misma lógica city/country que realkey, sin tocar plan)
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_week CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_week AS
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
                COALESCE(NULLIF(TRIM(park_name_raw::text), ''), NULLIF(TRIM(park_city_raw::text), ''), park_id_raw::text) AS park_name,
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
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
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
            (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
            COUNT(*) AS trips,
            SUM(COALESCE(comision_empresa_asociada, 0)) AS revenue
        FROM with_key
        GROUP BY park_id, park_name, city_key, LOWER(TRIM(tipo_servicio::text)), (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
    """)

    # 7) Real con LOB por semana
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_with_lob_week CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_with_lob_week AS
        WITH mapping_current AS (
            SELECT country, city, park_id, real_tipo_servicio, lob_id
            FROM canon.map_real_to_lob
            WHERE valid_to IS NULL
        )
        SELECT
            r.country,
            r.city,
            r.park_id,
            r.park_name,
            r.real_tipo_servicio,
            COALESCE(d.lob_name, 'UNCLASSIFIED') AS lob_name,
            r.week_start,
            r.trips,
            r.revenue
        FROM ops.v_real_universe_by_park_week r
        LEFT JOIN mapping_current m
            ON LOWER(TRIM(r.country)) = LOWER(TRIM(m.country))
           AND LOWER(TRIM(r.city)) = LOWER(TRIM(m.city))
           AND TRIM(r.park_id) = TRIM(m.park_id)
           AND LOWER(TRIM(r.real_tipo_servicio)) = LOWER(TRIM(m.real_tipo_servicio))
        LEFT JOIN canon.dim_lob d ON d.lob_id = m.lob_id AND d.active = true
    """)

    # 8) Agregado semanal por (country, city, lob_name)
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_by_lob_week CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_trips_by_lob_week AS
        SELECT
            country,
            city,
            lob_name,
            week_start AS period_date,
            SUM(trips) AS trips,
            SUM(revenue) AS revenue
        FROM ops.v_real_universe_with_lob_week
        GROUP BY country, city, lob_name, week_start
        ORDER BY country, city, lob_name, week_start
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_by_lob_week CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_with_lob_week CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_week CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_by_lob_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_with_lob CASCADE")
    op.execute("DROP TABLE IF EXISTS canon.map_real_to_lob")
    op.execute("DROP TABLE IF EXISTS canon.dim_lob")
    op.execute("DROP SCHEMA IF EXISTS canon CASCADE")
