"""
051_real_drill_mv_rollup: MV rollup diaria + dim_city_country + vistas MV-based.
- ops.dim_city_country: city_norm -> country (CO/PE)
- ops.mv_real_rollup_day: agregado diario desde trips_all (rápido, sin fullscan en cada request)
- Vistas drill desde MV: coverage, country_month/week, lob_month/week, park_month/week
"""
from alembic import op

revision = "051_real_drill_mv_rollup"
down_revision = "050_drill_calendar_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Tabla dim_city_country (city_norm -> country)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.dim_city_country (
            city_norm TEXT PRIMARY KEY,
            country TEXT NOT NULL CHECK (country IN ('co','pe','unk')),
            city_label TEXT
        )
    """)
    op.execute("COMMENT ON TABLE ops.dim_city_country IS 'Mapping city -> country para Real Drill. city_norm = lower(trim(city)).'")

    # Seed desde ciudades conocidas en parks
    op.execute("""
        INSERT INTO ops.dim_city_country (city_norm, country, city_label) VALUES
        ('cali', 'co', 'Cali'),
        ('medellin', 'co', 'Medellín'),
        ('bogota', 'co', 'Bogotá'),
        ('barranquilla', 'co', 'Barranquilla'),
        ('cucuta', 'co', 'Cúcuta'),
        ('bucaramanga', 'co', 'Bucaramanga'),
        ('lima', 'pe', 'Lima'),
        ('trujillo', 'pe', 'Trujillo'),
        ('arequipa', 'pe', 'Arequipa')
        ON CONFLICT (city_norm) DO UPDATE SET country = EXCLUDED.country, city_label = EXCLUDED.city_label
    """)

    # 2) MV rollup diaria (deshabilitar timeout: trips_all puede ser grande)
    op.execute("SET statement_timeout = '0'")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_rollup_day CASCADE")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_rollup_day AS
        WITH base AS (
            SELECT
                (t.fecha_inicio_viaje)::date AS trip_day,
                t.fecha_inicio_viaje AS trip_ts,
                t.park_id,
                t.tipo_servicio,
                t.pago_corporativo,
                t.comision_empresa_asociada,
                t.distancia_km,
                p.id AS park_catalog_id,
                p.name AS park_name,
                p.city AS park_city,
                LOWER(TRIM(COALESCE(p.city,'')::text)) AS city_norm
            FROM public.trips_all t
            LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_country AS (
            SELECT
                b.*,
                COALESCE(d.country, 'unk') AS country,
                COALESCE(NULLIF(TRIM(b.park_city::text), ''), '(sin_city)') AS city,
                COALESCE(NULLIF(TRIM(b.park_name::text), ''), CASE WHEN b.park_id IS NOT NULL THEN 'PARK '||b.park_id::text ELSE 'SIN_PARK_ID' END) AS park_name_resolved,
                CASE
                    WHEN b.park_id IS NULL OR TRIM(b.park_id::text) = '' THEN 'SIN_PARK_ID'
                    WHEN b.park_catalog_id IS NULL THEN 'PARK_NO_CATALOG'
                    ELSE 'OK'
                END AS park_bucket,
                CASE
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(b.tipo_servicio::text))
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(b.tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(b.tipo_servicio::text))
                END AS real_tipo_norm
            FROM base b
            LEFT JOIN ops.dim_city_country d ON d.city_norm = b.city_norm
        )
        SELECT
            v.trip_day,
            v.country,
            v.city,
            v.park_id,
            v.park_name_resolved,
            v.park_bucket,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
            CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            COUNT(*) AS trips,
            SUM(CASE WHEN v.pago_corporativo IS NOT NULL THEN 1 ELSE 0 END) AS b2b_trips,
            SUM(v.comision_empresa_asociada) AS margin_total,
            SUM(COALESCE(v.distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
            MAX(v.trip_ts) AS last_trip_ts
        FROM with_country v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_norm
        GROUP BY v.trip_day, v.country, v.city, v.park_id, v.park_name_resolved, v.park_bucket,
                 COALESCE(m.lob_group, 'UNCLASSIFIED'),
                 CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END
    """)

    # Unique index para REFRESH CONCURRENTLY
    op.execute("""
        CREATE UNIQUE INDEX uq_mv_real_rollup_day
        ON ops.mv_real_rollup_day (trip_day, country, COALESCE(city,''), COALESCE(park_id::text,''), lob_group, segment_tag)
    """)
    op.execute("CREATE INDEX idx_mv_real_rollup_country_day ON ops.mv_real_rollup_day (country, trip_day)")
    op.execute("CREATE INDEX idx_mv_real_rollup_country_city_day ON ops.mv_real_rollup_day (country, city, trip_day)")
    op.execute("CREATE INDEX idx_mv_real_rollup_country_park_day ON ops.mv_real_rollup_day (country, park_id, trip_day)")

    # 3) Coverage desde MV
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_data_coverage AS
        SELECT
            country,
            MIN(trip_day) AS min_trip_date,
            MAX(trip_day) AS last_trip_date,
            MAX(last_trip_ts) AS last_trip_ts,
            date_trunc('month', MIN(trip_day))::date AS min_month,
            date_trunc('week', MIN(trip_day))::date AS min_week,
            date_trunc('month', MAX(trip_day))::date AS last_month_with_data,
            date_trunc('week', MAX(trip_day))::date AS last_week_with_data
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe')
        GROUP BY country
    """)

    # 4) Country MONTH desde MV (calendario completo)
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_month AS
        WITH
        countries AS (SELECT unnest(ARRAY['co','pe']) AS country),
        cov AS (
            SELECT MIN(min_month) AS min_month, MAX(last_month_with_data) AS max_month
            FROM ops.v_real_data_coverage
        ),
        bounds AS (
            SELECT
                COALESCE((SELECT min_month FROM cov), date_trunc('month', CURRENT_DATE)::date) AS min_month,
                date_trunc('month', CURRENT_DATE)::date AS current_month
        ),
        month_cal AS (
            SELECT (generate_series(b.min_month, b.current_month, '1 month'::interval))::date AS period_start
            FROM bounds b
        ),
        country_months AS (
            SELECT c.country, m.period_start
            FROM countries c
            CROSS JOIN month_cal m
        ),
        agg AS (
            SELECT
                country,
                date_trunc('month', trip_day)::date AS period_start,
                SUM(trips) AS trips,
                SUM(b2b_trips) AS b2b_trips,
                SUM(margin_total) AS margin_total,
                SUM(distance_total_km) AS distance_total_km,
                MAX(last_trip_ts) AS last_trip_ts
            FROM ops.mv_real_rollup_day
            WHERE country IN ('co','pe')
            GROUP BY country, date_trunc('month', trip_day)::date
        ),
        combined AS (
            SELECT
                cm.country,
                cm.period_start,
                COALESCE(a.trips, 0) AS trips,
                COALESCE(a.b2b_trips, 0) AS b2b_trips,
                a.margin_total,
                a.distance_total_km,
                a.last_trip_ts,
                (cm.period_start = (SELECT current_month FROM bounds)) AS period_is_current,
                (cm.period_start < (SELECT current_month FROM bounds)) AS period_closed,
                LEAST(CURRENT_DATE - 1, (cm.period_start + interval '1 month' - interval '1 day')::date) AS expected_last_date
            FROM country_months cm
            LEFT JOIN agg a ON a.country = cm.country AND a.period_start = cm.period_start
        )
        SELECT
            c.country,
            c.period_start,
            c.trips,
            c.b2b_trips,
            c.margin_total,
            CASE WHEN c.trips > 0 AND c.margin_total IS NOT NULL THEN c.margin_total / c.trips ELSE NULL END AS margin_unit_avg,
            c.distance_total_km,
            CASE WHEN c.trips > 0 AND c.distance_total_km IS NOT NULL THEN c.distance_total_km / c.trips ELSE NULL END AS distance_km_avg,
            CASE WHEN c.trips > 0 THEN c.b2b_trips::numeric / c.trips ELSE 0 END AS b2b_pct,
            c.last_trip_ts,
            c.expected_last_date,
            (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) AS falta_data,
            CASE
                WHEN c.period_is_current AND (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) THEN 'FALTA_DATA'
                WHEN c.period_is_current THEN 'ABIERTO'
                WHEN c.period_closed AND c.trips = 0 THEN 'VACIO'
                ELSE 'CERRADO'
            END AS estado
        FROM combined c
    """)

    # 5) Country WEEK desde MV
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_week AS
        WITH
        countries AS (SELECT unnest(ARRAY['co','pe']) AS country),
        bounds AS (
            SELECT
                COALESCE((SELECT MIN(date_trunc('week', trip_day)::date) FROM ops.mv_real_rollup_day WHERE country IN ('co','pe')), date_trunc('week', CURRENT_DATE)::date) AS min_week,
                date_trunc('week', CURRENT_DATE)::date AS current_week
        ),
        week_cal AS (
            SELECT (generate_series(b.min_week, b.current_week, '1 week'::interval))::date AS period_start
            FROM bounds b
        ),
        country_weeks AS (
            SELECT c.country, w.period_start
            FROM countries c
            CROSS JOIN week_cal w
        ),
        agg AS (
            SELECT
                country,
                date_trunc('week', trip_day)::date AS period_start,
                SUM(trips) AS trips,
                SUM(b2b_trips) AS b2b_trips,
                SUM(margin_total) AS margin_total,
                SUM(distance_total_km) AS distance_total_km,
                MAX(last_trip_ts) AS last_trip_ts
            FROM ops.mv_real_rollup_day
            WHERE country IN ('co','pe')
            GROUP BY country, date_trunc('week', trip_day)::date
        ),
        combined AS (
            SELECT
                cw.country,
                cw.period_start,
                COALESCE(a.trips, 0) AS trips,
                COALESCE(a.b2b_trips, 0) AS b2b_trips,
                a.margin_total,
                a.distance_total_km,
                a.last_trip_ts,
                (cw.period_start = (SELECT current_week FROM bounds)) AS period_is_current,
                (cw.period_start < (SELECT current_week FROM bounds)) AS period_closed,
                LEAST(CURRENT_DATE - 1, cw.period_start + 6) AS expected_last_date
            FROM country_weeks cw
            LEFT JOIN agg a ON a.country = cw.country AND a.period_start = cw.period_start
        )
        SELECT
            c.country,
            c.period_start,
            c.trips,
            c.b2b_trips,
            c.margin_total,
            CASE WHEN c.trips > 0 AND c.margin_total IS NOT NULL THEN c.margin_total / c.trips ELSE NULL END AS margin_unit_avg,
            c.distance_total_km,
            CASE WHEN c.trips > 0 AND c.distance_total_km IS NOT NULL THEN c.distance_total_km / c.trips ELSE NULL END AS distance_km_avg,
            CASE WHEN c.trips > 0 THEN c.b2b_trips::numeric / c.trips ELSE 0 END AS b2b_pct,
            c.last_trip_ts,
            c.expected_last_date,
            (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) AS falta_data,
            CASE
                WHEN c.period_is_current AND (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) THEN 'FALTA_DATA'
                WHEN c.period_is_current THEN 'ABIERTO'
                WHEN c.period_closed AND c.trips = 0 THEN 'VACIO'
                ELSE 'CERRADO'
            END AS estado
        FROM combined c
    """)

    # 6) LOB MONTH desde MV
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_lob_month AS
        SELECT
            country,
            lob_group,
            date_trunc('month', trip_day)::date AS period_start,
            SUM(trips) AS trips,
            SUM(b2b_trips) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            CASE WHEN SUM(trips) > 0 AND SUM(margin_total) IS NOT NULL THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS distance_km_avg,
            MAX(last_trip_ts) AS last_trip_ts,
            'Todos'::text AS segment_tag
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe') AND lob_group IS NOT NULL
        GROUP BY country, lob_group, date_trunc('month', trip_day)::date
    """)

    # 7) LOB WEEK desde MV
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_lob_week AS
        SELECT
            country,
            lob_group,
            date_trunc('week', trip_day)::date AS period_start,
            SUM(trips) AS trips,
            SUM(b2b_trips) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            CASE WHEN SUM(trips) > 0 AND SUM(margin_total) IS NOT NULL THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS distance_km_avg,
            MAX(last_trip_ts) AS last_trip_ts,
            'Todos'::text AS segment_tag
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe') AND lob_group IS NOT NULL
        GROUP BY country, lob_group, date_trunc('week', trip_day)::date
    """)

    # 8) Park MONTH desde MV
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_month AS
        SELECT
            country,
            city,
            park_id,
            park_name_resolved,
            park_bucket,
            date_trunc('month', trip_day)::date AS period_start,
            SUM(trips) AS trips,
            SUM(b2b_trips) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            CASE WHEN SUM(trips) > 0 AND SUM(margin_total) IS NOT NULL THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS distance_km_avg,
            MAX(last_trip_ts) AS last_trip_ts
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe')
        GROUP BY country, city, park_id, park_name_resolved, park_bucket, date_trunc('month', trip_day)::date
    """)

    # 9) Park WEEK desde MV
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_week AS
        SELECT
            country,
            city,
            park_id,
            park_name_resolved,
            park_bucket,
            date_trunc('week', trip_day)::date AS period_start,
            SUM(trips) AS trips,
            SUM(b2b_trips) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            CASE WHEN SUM(trips) > 0 AND SUM(margin_total) IS NOT NULL THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS distance_km_avg,
            MAX(last_trip_ts) AS last_trip_ts
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe')
        GROUP BY country, city, park_id, park_name_resolved, park_bucket, date_trunc('week', trip_day)::date
    """)

    # Poblar MV (primera vez)
    op.execute("REFRESH MATERIALIZED VIEW ops.mv_real_rollup_day")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_week CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob_week CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_week CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_rollup_day CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.dim_city_country CASCADE")
    # 050 recrea vistas desde v_real_trips_base_drill (ejecutar downgrade 050 si se quiere restaurar)
