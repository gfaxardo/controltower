"""
Calendario completo para drill, metadata de cobertura y fix drill por park.
- ops.v_real_data_coverage: last_trip_date, last_month_with_data, last_week_with_data por país.
- ops.v_real_drill_country_month/week: calendario hasta periodo actual, estado FALTA_DATA/ABIERTO/VACIO/CERRADO.
- ops.v_real_drill_park_month/week: park_name_resolved, park_bucket (SIN_PARK_ID, PARK_NO_CATALOG, OK).
Fuente real: ops.v_real_trips_with_lob_v2 (country, fecha_inicio_viaje). Park desde trips_all + LEFT JOIN parks.
"""
from alembic import op

revision = "049_drill_calendar"
down_revision = "048_drill_margin_distance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Vista de cobertura por país
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_data_coverage AS
        SELECT
            country,
            MAX(fecha_inicio_viaje)::date AS last_trip_date,
            MAX(fecha_inicio_viaje) AS last_trip_ts,
            date_trunc('month', MAX(fecha_inicio_viaje))::date AS last_month_with_data,
            date_trunc('week', MAX(fecha_inicio_viaje))::date AS last_week_with_data
        FROM ops.v_real_trips_with_lob_v2
        WHERE country IS NOT NULL AND TRIM(country) <> ''
        GROUP BY country
    """)

    # 2) Country MONTH con calendario completo y estado
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_month AS
        WITH
        real_month AS (
            SELECT
                country,
                date_trunc('month', fecha_inicio_viaje)::date AS period_start,
                COUNT(*) AS trips,
                SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS last_trip_ts
            FROM ops.v_real_trips_with_lob_v2
            WHERE country IS NOT NULL AND TRIM(country) <> ''
            GROUP BY country, date_trunc('month', fecha_inicio_viaje)::date
        ),
        countries AS (
            SELECT DISTINCT country FROM ops.v_real_trips_with_lob_v2
            WHERE country IS NOT NULL AND TRIM(country) <> ''
        ),
        bounds AS (
            SELECT
                COALESCE(date_trunc('month', MIN(fecha_inicio_viaje))::date, date_trunc('month', CURRENT_DATE)::date) AS min_month,
                date_trunc('month', CURRENT_DATE)::date AS current_month
            FROM ops.v_real_trips_with_lob_v2
        ),
        month_calendar AS (
            SELECT (generate_series(b.min_month, b.current_month, '1 month'::interval))::date AS period_start
            FROM bounds b
        ),
        country_months AS (
            SELECT c.country, m.period_start
            FROM countries c
            CROSS JOIN month_calendar m
        ),
        combined AS (
            SELECT
                cm.country,
                cm.period_start,
                COALESCE(r.trips, 0) AS trips,
                COALESCE(r.b2b_trips, 0) AS b2b_trips,
                r.margin_total,
                r.distance_total_km,
                r.last_trip_ts,
                (cm.period_start = (SELECT current_month FROM bounds LIMIT 1)) AS period_is_current,
                (cm.period_start < (SELECT current_month FROM bounds LIMIT 1)) AS period_closed,
                LEAST(CURRENT_DATE - 1, (cm.period_start + interval '1 month' - interval '1 day')::date) AS expected_last_date
            FROM country_months cm
            LEFT JOIN real_month r ON r.country = cm.country AND r.period_start = cm.period_start
        )
        SELECT
            'monthly'::text AS period_type,
            'country'::text AS level,
            c.country,
            NULL::text AS city,
            NULL::text AS park_id,
            NULL::text AS park_name,
            NULL::text AS lob_group,
            c.period_start,
            c.trips,
            c.b2b_trips,
            c.margin_total,
            CASE WHEN c.trips > 0 THEN c.margin_total / c.trips ELSE NULL END AS margin_unit_avg,
            c.distance_total_km,
            CASE WHEN c.trips > 0 THEN c.distance_total_km / c.trips ELSE NULL END AS distance_km_avg,
            NULL::numeric AS b2b_margin_total,
            NULL::numeric AS b2b_margin_unit_avg,
            NULL::numeric AS b2b_distance_total_km,
            NULL::numeric AS b2b_distance_km_avg,
            c.last_trip_ts,
            c.period_is_current,
            c.period_closed,
            (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) AS falta_data,
            CASE
                WHEN c.period_is_current AND (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) THEN 'FALTA_DATA'
                WHEN c.period_is_current THEN 'ABIERTO'
                WHEN c.period_closed AND c.trips = 0 THEN 'VACIO'
                ELSE 'CERRADO'
            END AS estado
        FROM combined c
    """)

    # 3) Country WEEK con calendario completo y estado (semana ISO = lunes)
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_week AS
        WITH
        real_week AS (
            SELECT
                country,
                date_trunc('week', fecha_inicio_viaje)::date AS period_start,
                COUNT(*) AS trips,
                SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS last_trip_ts
            FROM ops.v_real_trips_with_lob_v2
            WHERE country IS NOT NULL AND TRIM(country) <> ''
            GROUP BY country, date_trunc('week', fecha_inicio_viaje)::date
        ),
        countries AS (
            SELECT DISTINCT country FROM ops.v_real_trips_with_lob_v2
            WHERE country IS NOT NULL AND TRIM(country) <> ''
        ),
        bounds AS (
            SELECT
                COALESCE(date_trunc('week', MIN(fecha_inicio_viaje))::date, date_trunc('week', CURRENT_DATE)::date) AS min_week,
                date_trunc('week', CURRENT_DATE)::date AS current_week
            FROM ops.v_real_trips_with_lob_v2
        ),
        week_calendar AS (
            SELECT (generate_series(b.min_week, b.current_week, '1 week'::interval))::date AS period_start
            FROM bounds b
        ),
        country_weeks AS (
            SELECT c.country, w.period_start
            FROM countries c
            CROSS JOIN week_calendar w
        ),
        combined AS (
            SELECT
                cw.country,
                cw.period_start,
                COALESCE(r.trips, 0) AS trips,
                COALESCE(r.b2b_trips, 0) AS b2b_trips,
                r.margin_total,
                r.distance_total_km,
                r.last_trip_ts,
                (cw.period_start = (SELECT current_week FROM bounds LIMIT 1)) AS period_is_current,
                (cw.period_start < (SELECT current_week FROM bounds LIMIT 1)) AS period_closed,
                LEAST(CURRENT_DATE - 1, cw.period_start + 6) AS expected_last_date
            FROM country_weeks cw
            LEFT JOIN real_week r ON r.country = cw.country AND r.period_start = cw.period_start
        )
        SELECT
            'weekly'::text AS period_type,
            'country'::text AS level,
            c.country,
            NULL::text AS city,
            NULL::text AS park_id,
            NULL::text AS park_name,
            NULL::text AS lob_group,
            c.period_start,
            c.trips,
            c.b2b_trips,
            c.margin_total,
            CASE WHEN c.trips > 0 THEN c.margin_total / c.trips ELSE NULL END AS margin_unit_avg,
            c.distance_total_km,
            CASE WHEN c.trips > 0 THEN c.distance_total_km / c.trips ELSE NULL END AS distance_km_avg,
            NULL::numeric AS b2b_margin_total,
            NULL::numeric AS b2b_margin_unit_avg,
            NULL::numeric AS b2b_distance_total_km,
            NULL::numeric AS b2b_distance_km_avg,
            c.last_trip_ts,
            c.period_is_current,
            c.period_closed,
            (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) AS falta_data,
            CASE
                WHEN c.period_is_current AND (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) THEN 'FALTA_DATA'
                WHEN c.period_is_current THEN 'ABIERTO'
                WHEN c.period_closed AND c.trips = 0 THEN 'VACIO'
                ELSE 'CERRADO'
            END AS estado
        FROM combined c
    """)

    # 4) Park MONTH: desde MV agregada por park (mantenemos lectura desde MV para margen/distancia)
    #    pero necesitamos vista que incluya park_name_resolved y park_bucket.
    #    La MV actual agrupa por park_id, park_name (de la vista). Creamos vista intermedia que
    #    lee de la MV y añade bucket; o recreamos desde base con LEFT JOIN parks.
    #    Especificación: agrupar por country, city, park_id, period_start (NO park_name);
    #    park_name_resolved = COALESCE(parks.name, ...); park_bucket = SIN_PARK_ID | PARK_NO_CATALOG | OK.
    #    Para no duplicar lógica de agregación, creamos vista que usa la misma fuente que la MV
    #    pero con LEFT JOIN parks y bucket. Fuente: v_real_trips_with_lob_v2 ya hace JOIN parks,
    #    así que no tenemos filas sin park. Necesitamos una base que sea trips_all LEFT JOIN parks
    #    para tener SIN_PARK_ID y PARK_NO_CATALOG. Crear CTE en la migración que agrega desde
    #    trips_all LEFT JOIN parks con resolución de country/city (reducida).
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_month AS
        WITH
        base AS (
            SELECT
                t.park_id,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                t.pago_corporativo,
                t.distancia_km,
                t.tipo_servicio,
                t.condicion,
                p.id AS park_catalog_id,
                p.name AS park_catalog_name,
                p.city AS park_city
            FROM public.trips_all t
            LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
        ),
        with_country AS (
            SELECT
                park_id,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                park_catalog_id,
                COALESCE(NULLIF(TRIM(park_catalog_name::text), ''), 'PARK ' || COALESCE(park_id::text, 'NULL')) AS park_name_resolved,
                CASE
                    WHEN park_id IS NULL THEN 'SIN_PARK_ID'
                    WHEN park_catalog_id IS NULL THEN 'PARK_NO_CATALOG'
                    ELSE 'OK'
                END AS park_bucket,
                CASE
                    WHEN park_city::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_city::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_city::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_city::text ILIKE '%%lima%%' THEN 'lima'
                    ELSE LOWER(TRIM(COALESCE(park_city::text, '')))
                END AS city_key
            FROM base
        ),
        with_country_final AS (
            SELECT
                park_id,
                date_trunc('month', fecha_inicio_viaje)::date AS period_start,
                park_name_resolved,
                park_bucket,
                CASE WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                     WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe' ELSE '' END AS country,
                COALESCE(NULLIF(city_key, ''), 'unknown') AS city,
                COUNT(*) AS trips,
                SUM(CASE WHEN pago_corporativo IS NOT NULL THEN 1 ELSE 0 END) AS b2b_trips,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS last_trip_ts
            FROM with_country
            GROUP BY park_id, date_trunc('month', fecha_inicio_viaje)::date, park_name_resolved, park_bucket, city_key
        )
        SELECT
            'monthly'::text AS period_type,
            'park'::text AS level,
            country,
            city,
            park_id::text AS park_id,
            park_name_resolved AS park_name,
            NULL::text AS lob_group,
            period_start,
            trips,
            b2b_trips,
            margin_total,
            CASE WHEN trips > 0 THEN margin_total / trips ELSE NULL END AS margin_unit_avg,
            distance_total_km,
            CASE WHEN trips > 0 THEN distance_total_km / trips ELSE NULL END AS distance_km_avg,
            NULL::numeric AS b2b_margin_total,
            NULL::numeric AS b2b_margin_unit_avg,
            NULL::numeric AS b2b_distance_total_km,
            NULL::numeric AS b2b_distance_km_avg,
            last_trip_ts,
            park_bucket,
            CASE
                WHEN period_start = date_trunc('month', CURRENT_DATE)::date THEN
                    CASE WHEN (LEAST(CURRENT_DATE - 1, (period_start + interval '1 month' - interval '1 day')::date) IS NOT NULL AND (last_trip_ts IS NULL OR last_trip_ts::date < LEAST(CURRENT_DATE - 1, (period_start + interval '1 month' - interval '1 day')::date))) THEN 'FALTA_DATA' ELSE 'ABIERTO' END
                WHEN period_start < date_trunc('month', CURRENT_DATE)::date AND trips = 0 THEN 'VACIO'
                ELSE 'CERRADO'
            END AS estado
        FROM with_country_final
        WHERE country IS NOT NULL AND TRIM(country) <> ''
    """)

    # 5) Park WEEK
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_week AS
        WITH
        base AS (
            SELECT
                t.park_id,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                t.pago_corporativo,
                t.distancia_km,
                p.id AS park_catalog_id,
                p.name AS park_catalog_name,
                p.city AS park_city
            FROM public.trips_all t
            LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
        ),
        with_country AS (
            SELECT
                park_id,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                park_catalog_id,
                COALESCE(NULLIF(TRIM(park_catalog_name::text), ''), 'PARK ' || COALESCE(park_id::text, 'NULL')) AS park_name_resolved,
                CASE
                    WHEN park_id IS NULL THEN 'SIN_PARK_ID'
                    WHEN park_catalog_id IS NULL THEN 'PARK_NO_CATALOG'
                    ELSE 'OK'
                END AS park_bucket,
                CASE
                    WHEN park_city::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_city::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_city::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_city::text ILIKE '%%lima%%' THEN 'lima'
                    ELSE LOWER(TRIM(COALESCE(park_city::text, '')))
                END AS city_key
            FROM base
        ),
        with_country_final AS (
            SELECT
                park_id,
                date_trunc('week', fecha_inicio_viaje)::date AS period_start,
                park_name_resolved,
                park_bucket,
                CASE WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                     WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe' ELSE '' END AS country,
                COALESCE(NULLIF(city_key, ''), 'unknown') AS city,
                COUNT(*) AS trips,
                SUM(CASE WHEN pago_corporativo IS NOT NULL THEN 1 ELSE 0 END) AS b2b_trips,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS last_trip_ts
            FROM with_country
            GROUP BY park_id, date_trunc('week', fecha_inicio_viaje)::date, park_name_resolved, park_bucket, city_key
        )
        SELECT
            'weekly'::text AS period_type,
            'park'::text AS level,
            country,
            city,
            park_id::text AS park_id,
            park_name_resolved AS park_name,
            NULL::text AS lob_group,
            period_start,
            trips,
            b2b_trips,
            margin_total,
            CASE WHEN trips > 0 THEN margin_total / trips ELSE NULL END AS margin_unit_avg,
            distance_total_km,
            CASE WHEN trips > 0 THEN distance_total_km / trips ELSE NULL END AS distance_km_avg,
            NULL::numeric AS b2b_margin_total,
            NULL::numeric AS b2b_margin_unit_avg,
            NULL::numeric AS b2b_distance_total_km,
            NULL::numeric AS b2b_distance_km_avg,
            last_trip_ts,
            park_bucket,
            CASE
                WHEN period_start = date_trunc('week', CURRENT_DATE)::date THEN
                    CASE WHEN (LEAST(CURRENT_DATE - 1, period_start + 6) IS NOT NULL AND (last_trip_ts IS NULL OR last_trip_ts::date < LEAST(CURRENT_DATE - 1, period_start + 6))) THEN 'FALTA_DATA' ELSE 'ABIERTO' END
                WHEN period_start < date_trunc('week', CURRENT_DATE)::date AND trips = 0 THEN 'VACIO'
                ELSE 'CERRADO'
            END AS estado
        FROM with_country_final
        WHERE country IS NOT NULL AND TRIM(country) <> ''
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_week CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_week CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    # Restore 048 views would require re-running 048 upgrade; not done here
