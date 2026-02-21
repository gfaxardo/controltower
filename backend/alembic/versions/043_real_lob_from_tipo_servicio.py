"""
Real LOB: LOB = trips_all.tipo_servicio normalizado (sin mapping/homologación).
- Vista base desde trips_all con LOB canonical + UNCLASSIFIED.
- Vistas agregadas con is_open, currency; orden mensual ASC, semanal DESC.
- Recrea MVs con la nueva definición.
No modifica Plan vs Real (ops.v_plan_vs_real_realkey_final).
"""
from alembic import op

revision = "043_real_lob_from_tipo_servicio"
down_revision = "042_real_lob_materialized_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Vista agregada mensual: LOB desde tipo_servicio, is_open, currency
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_by_lob_month")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_by_lob_week")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_by_lob_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_by_lob_week CASCADE")

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_trips_by_lob_month AS
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
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
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
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT
                tipo_servicio,
                fecha_inicio_viaje,
                GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE
                    WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_key
        ),
        lob_norm AS (
            SELECT
                country,
                city,
                fecha_inicio_viaje,
                revenue,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IS NULL OR LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','tuk-tuk','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    ELSE 'UNCLASSIFIED'
                END AS lob
            FROM with_country
        ),
        agg AS (
            SELECT
                country,
                city,
                lob,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*) AS trips,
                SUM(revenue) AS revenue,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM lob_norm
            GROUP BY country, city, lob, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        ),
        global_max AS (
            SELECT MAX(fecha_inicio_viaje) AS m FROM lob_norm
        )
        SELECT
            a.country,
            a.city,
            a.lob,
            a.month_start,
            a.trips,
            a.revenue,
            a.max_trip_ts,
            (a.month_start = (DATE_TRUNC('month', g.m)::DATE)) AS is_open,
            CASE WHEN a.country = 'pe' THEN 'PEN' WHEN a.country = 'co' THEN 'COP' ELSE NULL END AS currency
        FROM agg a
        CROSS JOIN global_max g
    """)

    # 2) Vista agregada semanal (misma base LOB, agrupación por semana)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_trips_by_lob_week AS
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
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
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
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT
                tipo_servicio,
                fecha_inicio_viaje,
                GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE
                    WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_key
        ),
        lob_norm AS (
            SELECT
                country,
                city,
                fecha_inicio_viaje,
                revenue,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IS NULL OR LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','tuk-tuk','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    ELSE 'UNCLASSIFIED'
                END AS lob
            FROM with_country
        ),
        agg AS (
            SELECT
                country,
                city,
                lob,
                (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
                COUNT(*) AS trips,
                SUM(revenue) AS revenue,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM lob_norm
            GROUP BY country, city, lob, (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
        ),
        global_max AS (
            SELECT MAX(fecha_inicio_viaje) AS m FROM lob_norm
        )
        SELECT
            a.country,
            a.city,
            a.lob,
            a.week_start,
            a.trips,
            a.revenue,
            a.max_trip_ts,
            (a.week_start = (DATE_TRUNC('week', g.m)::DATE)) AS is_open,
            CASE WHEN a.country = 'pe' THEN 'PEN' WHEN a.country = 'co' THEN 'COP' ELSE NULL END AS currency
        FROM agg a
        CROSS JOIN global_max g
    """)

    # 3) MVs desde las nuevas vistas (WITH NO DATA)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_trips_by_lob_month AS
        SELECT country, city, lob, month_start, trips, revenue, max_trip_ts, is_open, currency
        FROM ops.v_real_trips_by_lob_month
        WITH NO DATA
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_mv_real_lob_month_cclm ON ops.mv_real_trips_by_lob_month (country, city, lob, month_start)
    """)
    op.execute("""
        CREATE INDEX idx_mv_real_lob_month_ccm ON ops.mv_real_trips_by_lob_month (country, city, month_start)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_trips_by_lob_week AS
        SELECT country, city, lob, week_start, trips, revenue, max_trip_ts, is_open, currency
        FROM ops.v_real_trips_by_lob_week
        WITH NO DATA
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_mv_real_lob_week_ccwl ON ops.mv_real_trips_by_lob_week (country, city, lob, week_start)
    """)
    op.execute("""
        CREATE INDEX idx_mv_real_lob_week_ccw ON ops.mv_real_trips_by_lob_week (country, city, week_start)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_by_lob_week")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_by_lob_month")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_by_lob_week")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_by_lob_month")
    # Restore 041/042 views and MVs would require re-running 042; not recreated here.
