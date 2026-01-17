-- ============================================================================
-- PASO B: VALIDACIONES POST-INGESTA DE PLAN
-- ============================================================================
-- Script para validar coherencia entre Plan y Real
-- 
-- USO:
--   psql -d yego_integral -v plan_version="'ruta27_v1'" -f validate_plan_trips_monthly.sql
-- ============================================================================

-- Variable requerida (se reemplaza en Python):
-- :plan_version - Versión del plan a validar

-- Nota: Esta variable se reemplaza automáticamente por el script Python
-- No usar SET plan_version directamente, usar reemplazo de string

-- Limpiar validaciones previas de esta versión
-- La variable será reemplazada por el script Python
DELETE FROM ops.plan_validation_results 
WHERE plan_version = '{PLAN_VERSION_PLACEHOLDER}';

-- ============================================================================
-- 1. DETECTAR CITIES/LOB/SEGMENT EN PLAN QUE NO EXISTEN EN REAL
-- ============================================================================
-- Orphan Plan: combinaciones en plan sin equivalente en real
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
    park_id,
    lob_base,
    segment,
    month,
    severity,
    message,
    row_count
)
SELECT 
    '{PLAN_VERSION_PLACEHOLDER}' as plan_version,
    'orphan_plan' as validation_type,
    p.country,
    p.city,
    p.park_id,
    p.lob_base,
    p.segment,
    p.month,
    'warning' as severity,
    'Combinación en Plan sin equivalente en Real (park_id/lob/segment)' as message,
    COUNT(*) as row_count
FROM ops.plan_trips_monthly p
WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
AND NOT EXISTS (
    -- Verificar si existe en trips_all con condicion='Completado'
    SELECT 1
    FROM public.trips_all t
    INNER JOIN dim.dim_park dp ON t.park_id = dp.park_id
    WHERE t.condicion = 'Completado'
    AND (p.park_id IS NULL OR t.park_id = p.park_id)
    AND (p.country IS NULL OR dp.country = p.country)
    AND (p.city IS NULL OR dp.city = p.city)
    AND (
        p.lob_base IS NULL 
        OR dp.default_line_of_business = p.lob_base
        OR t.tipo_servicio LIKE '%' || p.lob_base || '%'
    )
)
GROUP BY p.country, p.city, p.park_id, p.lob_base, p.segment, p.month;

-- ============================================================================
-- 2. DETECTAR REAL SIN PLAN (solo warning, no error)
-- ============================================================================
-- Orphan Real: combinaciones en real sin plan correspondiente
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
    park_id,
    lob_base,
    segment,
    month,
    severity,
    message,
    row_count
)
SELECT 
    '{PLAN_VERSION_PLACEHOLDER}' as plan_version,
    'orphan_real' as validation_type,
    dp.country,
    dp.city,
    t.park_id,
    COALESCE(dp.default_line_of_business, t.tipo_servicio) as lob_base,
    NULL as segment,  -- Real no tiene segment
    DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE as month,
    'info' as severity,
    'Combinación en Real sin Plan correspondiente (solo warning)' as message,
    COUNT(*) as row_count
FROM public.trips_all t
INNER JOIN dim.dim_park dp ON t.park_id = dp.park_id
WHERE t.condicion = 'Completado'
AND DATE_TRUNC('month', t.fecha_inicio_viaje) >= (
    SELECT MIN(month) FROM ops.plan_trips_monthly 
    WHERE plan_version = '{PLAN_VERSION_PLACEHOLDER}'
)
AND DATE_TRUNC('month', t.fecha_inicio_viaje) <= (
    SELECT MAX(month) FROM ops.plan_trips_monthly 
    WHERE plan_version = '{PLAN_VERSION_PLACEHOLDER}'
)
AND NOT EXISTS (
    SELECT 1
    FROM ops.plan_trips_monthly p
    WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
    AND p.month = DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE
    AND (p.park_id IS NULL OR p.park_id = t.park_id)
    AND (p.country IS NULL OR p.country = dp.country)
    AND (p.city IS NULL OR p.city = dp.city)
    AND (
        p.lob_base IS NULL 
        OR p.lob_base = dp.default_line_of_business
        OR p.lob_base = t.tipo_servicio
    )
)
GROUP BY dp.country, dp.city, t.park_id, COALESCE(dp.default_line_of_business, t.tipo_servicio), DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE;

-- ============================================================================
-- 3. DETECTAR COMBINACIONES HUÉRFANAS (plan sin datos reales históricos)
-- ============================================================================
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
    park_id,
    lob_base,
    segment,
    month,
    severity,
    message,
    row_count
)
SELECT 
    '{PLAN_VERSION_PLACEHOLDER}' as plan_version,
    'missing_combo' as validation_type,
    p.country,
    p.city,
    p.park_id,
    p.lob_base,
    p.segment,
    p.month,
    'info' as severity,
    'Plan sin datos reales históricos en trips_all (combinación nueva o sin historial)' as message,
    COUNT(*) as row_count
FROM ops.plan_trips_monthly p
WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
AND p.month >= DATE_TRUNC('month', CURRENT_DATE)::DATE  -- Solo meses futuros
AND NOT EXISTS (
    SELECT 1
    FROM public.trips_all t
    INNER JOIN dim.dim_park dp ON t.park_id = dp.park_id
    WHERE t.condicion = 'Completado'
    AND (p.park_id IS NULL OR t.park_id = p.park_id)
    AND (p.country IS NULL OR dp.country = p.country)
    AND (p.city IS NULL OR dp.city = p.city)
    AND (
        p.lob_base IS NULL 
        OR dp.default_line_of_business = p.lob_base
        OR t.tipo_servicio LIKE '%' || p.lob_base || '%'
    )
)
GROUP BY p.country, p.city, p.park_id, p.lob_base, p.segment, p.month;

-- ============================================================================
-- REPORTE DE VALIDACIONES
-- ============================================================================
DO $$
DECLARE
    v_plan_version TEXT := '{PLAN_VERSION_PLACEHOLDER}';
    v_total_warnings INTEGER;
    v_total_errors INTEGER;
    v_total_info INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total_errors FROM ops.plan_validation_results WHERE plan_version = v_plan_version AND severity = 'error';
    SELECT COUNT(*) INTO v_total_warnings FROM ops.plan_validation_results WHERE plan_version = v_plan_version AND severity = 'warning';
    SELECT COUNT(*) INTO v_total_info FROM ops.plan_validation_results WHERE plan_version = v_plan_version AND severity = 'info';
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VALIDACIONES POST-INGESTA';
    RAISE NOTICE 'Plan Version: %', v_plan_version;
    RAISE NOTICE 'Errores: %', v_total_errors;
    RAISE NOTICE 'Warnings: %', v_total_warnings;
    RAISE NOTICE 'Info: %', v_total_info;
    RAISE NOTICE '========================================';
END $$;

-- Consulta para ver validaciones detalladas
SELECT 
    validation_type,
    severity,
    COUNT(*) as count,
    SUM(row_count) as total_rows_affected
FROM ops.plan_validation_results
WHERE plan_version = '{PLAN_VERSION_PLACEHOLDER}'
GROUP BY validation_type, severity
ORDER BY 
    CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
    validation_type;
