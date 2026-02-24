
-- Auto-generated from diagnose_and_fix_real_drill.py
-- Mapped columns: ts=fecha_inicio_viaje, park_id=park_id, tipo=tipo_servicio, b2b=pago_corporativo, margin=comision_empresa_asociada, dist=distancia_km

DROP VIEW IF EXISTS ops.v_real_trips_base_drill CASCADE;
CREATE VIEW ops.v_real_trips_base_drill AS

        WITH base AS (
            
        SELECT
            t.fecha_inicio_viaje AS trip_ts,
            (t.fecha_inicio_viaje)::date AS trip_date,
            NULLIF(TRIM(t.park_id::text), '') AS park_id_norm,
            t.park_id AS park_id,
            t.tipo_servicio AS tipo_servicio,
            t.pago_corporativo AS pago_corporativo,
            t.comision_empresa_asociada AS comision_empresa_asociada,
            t.distancia_km AS distancia_raw,
            p.id AS park_catalog_id,
            p.name AS park_catalog_name,
            p.city AS park_city,
            NULL::text AS raw_park_name
        FROM public.trips_all t
        LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(NULLIF(TRIM(t.park_id::text), ''))
        WHERE t.tipo_servicio IS NOT NULL
          AND t.condicion = 'Completado'
          AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
          AND t.tipo_servicio::text NOT LIKE '%->%'
    
        ),
        with_norm AS (
            SELECT
                trip_ts, trip_date, park_id_norm, park_id, tipo_servicio, pago_corporativo,
                comision_empresa_asociada, distancia_raw, park_catalog_id, park_catalog_name, park_city, raw_park_name,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(tipo_servicio::text))
                END AS real_tipo_servicio_norm
            FROM base
        ),
        city_key AS (
            SELECT
                v.*,
                CASE
                    WHEN park_catalog_name::text ILIKE '%cali%' OR park_city::text ILIKE '%cali%' THEN 'cali'
                    WHEN park_catalog_name::text ILIKE '%bogot%' OR park_city::text ILIKE '%bogot%' THEN 'bogota'
                    WHEN park_catalog_name::text ILIKE '%barranquilla%' OR park_city::text ILIKE '%barranquilla%' THEN 'barranquilla'
                    WHEN park_catalog_name::text ILIKE '%medell%' OR park_city::text ILIKE '%medell%' THEN 'medellin'
                    WHEN park_catalog_name::text ILIKE '%cucut%' OR park_city::text ILIKE '%cucut%' THEN 'cucuta'
                    WHEN park_catalog_name::text ILIKE '%bucaramanga%' OR park_city::text ILIKE '%bucaramanga%' THEN 'bucaramanga'
                    WHEN park_catalog_name::text ILIKE '%lima%' OR park_city::text ILIKE '%lima%' OR TRIM(COALESCE(park_catalog_name::text,'')) = 'Yego' THEN 'lima'
                    WHEN park_catalog_name::text ILIKE '%arequip%' OR park_city::text ILIKE '%arequip%' THEN 'arequipa'
                    WHEN park_catalog_name::text ILIKE '%trujill%' OR park_city::text ILIKE '%trujill%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city::text, '')))
                END AS city_norm
            FROM with_norm v
        )
        SELECT
            v.trip_ts,
            v.trip_date,
            CASE
                WHEN v.city_norm IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                WHEN v.city_norm IN ('lima','arequipa','trujillo') THEN 'pe'
                ELSE ''
            END AS country,
            COALESCE(NULLIF(TRIM(v.city_norm), ''), 'unknown') AS city,
            v.park_id,
            NULL::text AS park_name_raw,
            v.tipo_servicio,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
            CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            v.pago_corporativo,
            v.comision_empresa_asociada,
            CASE WHEN v.distancia_raw IS NULL THEN NULL ELSE (v.distancia_raw::numeric)/1000.0 END AS distancia_km,
            COALESCE(NULLIF(TRIM(v.park_catalog_name::text), ''), COALESCE(NULLIF(TRIM(v.raw_park_name::text), ''), 'PARK ' || COALESCE(v.park_id::text, 'NULL'))) AS park_name_resolved,
            CASE
                WHEN v.park_id_norm IS NULL THEN 'SIN_PARK_ID'
                WHEN v.park_catalog_id IS NULL THEN 'PARK_NO_CATALOG'
                ELSE 'OK'
            END AS park_bucket
        FROM city_key v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_servicio_norm;

CREATE VIEW ops.v_real_data_coverage AS
SELECT
    country,
    MAX(trip_ts)::date AS last_trip_date,
    MAX(trip_ts) AS last_trip_ts,
    MIN(trip_ts)::date AS min_trip_date,
    date_trunc('month', MIN(trip_ts))::date AS min_month,
    date_trunc('week', MIN(trip_ts))::date AS min_week,
    date_trunc('month', MAX(trip_ts))::date AS last_month_with_data,
    date_trunc('week', MAX(trip_ts))::date AS last_week_with_data
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> ''
GROUP BY country;

DROP VIEW IF EXISTS ops.v_real_drill_country_month CASCADE;
CREATE VIEW ops.v_real_drill_country_month AS
WITH
countries AS (
    SELECT country FROM (VALUES ('co'),('pe')) v(country)
    UNION
    SELECT DISTINCT country FROM ops.v_real_trips_base_drill
    WHERE country IS NOT NULL AND TRIM(country) <> ''
),
bounds AS (
    SELECT
        COALESCE((SELECT MIN(min_month) FROM ops.v_real_data_coverage WHERE min_month IS NOT NULL), date_trunc('month', CURRENT_DATE)::date) AS min_month,
        date_trunc('month', CURRENT_DATE)::date AS current_month
),
month_calendar AS (
    SELECT (generate_series(b.min_month, b.current_month, '1 month'::interval))::date AS period_start
    FROM bounds b
),
country_months AS (
    SELECT c.country, m.period_start
    FROM countries c
    CROSS JOIN month_calendar m
    WHERE c.country IN ('co','pe')
),
real_month AS (
    SELECT
        country,
        date_trunc('month', trip_ts)::date AS period_start,
        COUNT(*) AS trips,
        SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
        SUM(comision_empresa_asociada) AS margin_total,
        SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
        MAX(trip_ts) AS last_trip_ts
    FROM ops.v_real_trips_base_drill
    WHERE country IS NOT NULL AND TRIM(country) <> ''
    GROUP BY country, date_trunc('month', trip_ts)::date
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
FROM combined c;

DROP VIEW IF EXISTS ops.v_real_drill_country_week CASCADE;
CREATE VIEW ops.v_real_drill_country_week AS
WITH
countries AS (
    SELECT country FROM (VALUES ('co'),('pe')) v(country)
    UNION
    SELECT DISTINCT country FROM ops.v_real_trips_base_drill
    WHERE country IS NOT NULL AND TRIM(country) <> ''
),
bounds AS (
    SELECT
        COALESCE((SELECT MIN(min_week) FROM ops.v_real_data_coverage WHERE min_week IS NOT NULL), date_trunc('week', CURRENT_DATE)::date) AS min_week,
        date_trunc('week', CURRENT_DATE)::date AS current_week
),
week_calendar AS (
    SELECT (generate_series(b.min_week, b.current_week, '1 week'::interval))::date AS period_start
    FROM bounds b
),
country_weeks AS (
    SELECT c.country, w.period_start
    FROM countries c
    CROSS JOIN week_calendar w
    WHERE c.country IN ('co','pe')
),
real_week AS (
    SELECT
        country,
        date_trunc('week', trip_ts)::date AS period_start,
        COUNT(*) AS trips,
        SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
        SUM(comision_empresa_asociada) AS margin_total,
        SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
        MAX(trip_ts) AS last_trip_ts
    FROM ops.v_real_trips_base_drill
    WHERE country IS NOT NULL AND TRIM(country) <> ''
    GROUP BY country, date_trunc('week', trip_ts)::date
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
FROM combined c;

DROP VIEW IF EXISTS ops.v_real_drill_lob_month CASCADE;
CREATE VIEW ops.v_real_drill_lob_month AS
SELECT
    country,
    lob_group,
    date_trunc('month', trip_ts)::date AS period_start,
    COUNT(*) AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
    SUM(comision_empresa_asociada) AS margin_total,
    CASE WHEN COUNT(*) > 0 AND SUM(comision_empresa_asociada) IS NOT NULL THEN SUM(comision_empresa_asociada) / COUNT(*) ELSE NULL END AS margin_unit_avg,
    SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
    CASE WHEN COUNT(*) > 0 THEN SUM(COALESCE(distancia_km::numeric, 0)) / COUNT(*) ELSE NULL END AS distance_km_avg,
    MAX(trip_ts) AS last_trip_ts,
    'Todos'::text AS segment_tag
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
GROUP BY country, lob_group, date_trunc('month', trip_ts)::date;

DROP VIEW IF EXISTS ops.v_real_drill_lob_week CASCADE;
CREATE VIEW ops.v_real_drill_lob_week AS
SELECT
    country,
    lob_group,
    date_trunc('week', trip_ts)::date AS period_start,
    COUNT(*) AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
    SUM(comision_empresa_asociada) AS margin_total,
    CASE WHEN COUNT(*) > 0 AND SUM(comision_empresa_asociada) IS NOT NULL THEN SUM(comision_empresa_asociada) / COUNT(*) ELSE NULL END AS margin_unit_avg,
    SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
    CASE WHEN COUNT(*) > 0 THEN SUM(COALESCE(distancia_km::numeric, 0)) / COUNT(*) ELSE NULL END AS distance_km_avg,
    MAX(trip_ts) AS last_trip_ts,
    'Todos'::text AS segment_tag
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
GROUP BY country, lob_group, date_trunc('week', trip_ts)::date;

DROP VIEW IF EXISTS ops.v_real_drill_park_month CASCADE;
CREATE VIEW ops.v_real_drill_park_month AS
SELECT
    country,
    city,
    park_id,
    park_name_resolved,
    park_bucket,
    date_trunc('month', trip_ts)::date AS period_start,
    COUNT(*) AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
    SUM(comision_empresa_asociada) AS margin_total,
    CASE WHEN COUNT(*) > 0 AND SUM(comision_empresa_asociada) IS NOT NULL THEN SUM(comision_empresa_asociada) / COUNT(*) ELSE NULL END AS margin_unit_avg,
    SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
    CASE WHEN COUNT(*) > 0 THEN SUM(COALESCE(distancia_km::numeric, 0)) / COUNT(*) ELSE NULL END AS distance_km_avg,
    MAX(trip_ts) AS last_trip_ts
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> ''
GROUP BY country, city, park_id, park_name_resolved, park_bucket, date_trunc('month', trip_ts)::date;

DROP VIEW IF EXISTS ops.v_real_drill_park_week CASCADE;
CREATE VIEW ops.v_real_drill_park_week AS
SELECT
    country,
    city,
    park_id,
    park_name_resolved,
    park_bucket,
    date_trunc('week', trip_ts)::date AS period_start,
    COUNT(*) AS trips,
    SUM(CASE WHEN segment_tag = 'B2B' THEN 1 ELSE 0 END) AS b2b_trips,
    SUM(comision_empresa_asociada) AS margin_total,
    CASE WHEN COUNT(*) > 0 AND SUM(comision_empresa_asociada) IS NOT NULL THEN SUM(comision_empresa_asociada) / COUNT(*) ELSE NULL END AS margin_unit_avg,
    SUM(COALESCE(distancia_km::numeric, 0)) AS distance_total_km,
    CASE WHEN COUNT(*) > 0 THEN SUM(COALESCE(distancia_km::numeric, 0)) / COUNT(*) ELSE NULL END AS distance_km_avg,
    MAX(trip_ts) AS last_trip_ts
FROM ops.v_real_trips_base_drill
WHERE country IS NOT NULL AND TRIM(country) <> ''
GROUP BY country, city, park_id, park_name_resolved, park_bucket, date_trunc('week', trip_ts)::date;
