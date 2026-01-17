-- ============================================================================
-- PASO B: INGESTA DE PLAN DESDE CSV RUTA 27
-- ============================================================================
-- Script para cargar datos de plan desde CSV usando COPY
-- 
-- USO:
--   psql -d yego_integral -v plan_version="'ruta27_v1'" -v csv_path="'/ruta/al/archivo.csv'" -f ingest_plan_trips_monthly.sql
--
-- O desde Python:
--   cursor.execute("SET plan_version = 'ruta27_v1'")
--   cursor.execute("SET csv_path = '/ruta/al/archivo.csv'")
--   cursor.execute(open('ingest_plan_trips_monthly.sql').read())
-- ============================================================================

-- Variables (deben pasarse desde la aplicación):
-- :plan_version - Versión del plan (ej: 'ruta27_v1', 'ruta27_v2')
-- :csv_path - Ruta completa al archivo CSV

-- Validar que se pasen las variables requeridas
DO $$
BEGIN
    IF current_setting('plan_version', true) IS NULL THEN
        RAISE EXCEPTION 'Variable plan_version debe pasarse como parámetro (ej: SET plan_version = ''ruta27_v1'')';
    END IF;
    
    IF current_setting('csv_path', true) IS NULL THEN
        RAISE EXCEPTION 'Variable csv_path debe pasarse como parámetro (ej: SET csv_path = ''/ruta/al/archivo.csv'')';
    END IF;
END $$;

-- Tabla temporal para staging (limpieza automática al finalizar)
DROP TABLE IF EXISTS ops.stg_plan_trips_monthly;

CREATE TEMP TABLE ops.stg_plan_trips_monthly (
    country TEXT,
    city TEXT,
    park_id TEXT,
    lob_base TEXT,
    segment TEXT,
    month TEXT,  -- Se convertirá a DATE después
    projected_trips INTEGER,
    projected_drivers INTEGER,
    projected_ticket NUMERIC
);

-- Cargar CSV usando COPY (FORMAT CSV HEADER asume primera fila con headers)
\copy ops.stg_plan_trips_monthly(country, city, park_id, lob_base, segment, month, projected_trips, projected_drivers, projected_ticket) FROM :csv_path WITH (FORMAT CSV, HEADER true, DELIMITER ',', NULL '')

-- Validar formato de segment
DO $$
DECLARE
    invalid_segment_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO invalid_segment_count
    FROM ops.stg_plan_trips_monthly
    WHERE segment IS NOT NULL 
    AND segment NOT IN ('b2b', 'b2c');
    
    IF invalid_segment_count > 0 THEN
        RAISE WARNING 'Se encontraron % registros con segment inválido (debe ser b2b o b2c)', invalid_segment_count;
    END IF;
END $$;

-- Validar formato de month (debe ser YYYY-MM o similar)
DO $$
DECLARE
    invalid_month_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO invalid_month_count
    FROM ops.stg_plan_trips_monthly
    WHERE month IS NOT NULL 
    AND month::DATE IS NULL;
    
    IF invalid_month_count > 0 THEN
        RAISE EXCEPTION 'Se encontraron % registros con month inválido (debe ser formato fecha válido)', invalid_month_count;
    END IF;
END $$;

-- Insertar en tabla canónica (append-only, NO UPDATE)
INSERT INTO ops.plan_trips_monthly (
    plan_version,
    country,
    city,
    park_id,
    lob_base,
    segment,
    month,
    projected_trips,
    projected_drivers,
    projected_ticket
)
SELECT 
    current_setting('plan_version', true)::TEXT as plan_version,
    NULLIF(TRIM(country), '') as country,
    NULLIF(TRIM(city), '') as city,
    NULLIF(TRIM(park_id), '') as park_id,
    NULLIF(TRIM(lob_base), '') as lob_base,
    CASE 
        WHEN NULLIF(TRIM(segment), '') IN ('b2b', 'b2c') THEN NULLIF(TRIM(segment), '')
        ELSE NULL
    END as segment,
    CASE 
        WHEN month IS NOT NULL AND month::DATE IS NOT NULL THEN month::DATE
        ELSE NULL
    END as month,
    projected_trips,
    projected_drivers,
    projected_ticket
FROM ops.stg_plan_trips_monthly
-- Ignorar duplicados (constraint UNIQUE lo manejará)
ON CONFLICT (plan_version, country, city, park_id, lob_base, segment, month) 
DO NOTHING;

-- Reportar resultados
DO $$
DECLARE
    v_plan_version TEXT := current_setting('plan_version', true);
    v_inserted_count BIGINT;
    v_staging_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO v_staging_count FROM ops.stg_plan_trips_monthly;
    SELECT COUNT(*) INTO v_inserted_count 
    FROM ops.plan_trips_monthly 
    WHERE plan_version = v_plan_version 
    AND created_at >= NOW() - INTERVAL '1 minute';
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'INGESTA COMPLETADA';
    RAISE NOTICE 'Plan Version: %', v_plan_version;
    RAISE NOTICE 'Registros en CSV: %', v_staging_count;
    RAISE NOTICE 'Registros insertados: %', v_inserted_count;
    RAISE NOTICE 'Registros duplicados (ignorados): %', v_staging_count - v_inserted_count;
    RAISE NOTICE '========================================';
END $$;

-- Limpiar staging
DROP TABLE IF EXISTS ops.stg_plan_trips_monthly;
