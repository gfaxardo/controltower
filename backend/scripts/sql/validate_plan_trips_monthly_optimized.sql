-- ============================================================================
-- PASO B: VALIDACIONES POST-INGESTA DE PLAN (OPTIMIZADO)
-- ============================================================================
-- Script para validar coherencia entre Plan y Real usando agregado mensual
-- 
-- Variable: {PLAN_VERSION_PLACEHOLDER} - Se reemplaza automáticamente por Python
-- ============================================================================

-- Limpiar validaciones previas de esta versión
DELETE FROM ops.plan_validation_results 
WHERE plan_version = '{PLAN_VERSION_PLACEHOLDER}';

-- ============================================================================
-- 1. VALIDACIONES MÍNIMAS OBLIGATORIAS (RÁPIDAS)
-- ============================================================================

-- 1.1. Duplicados en PLAN
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
    lob_base,
    segment,
    month,
    severity,
    message,
    row_count
)
SELECT 
    '{PLAN_VERSION_PLACEHOLDER}' as plan_version,
    'duplicate_plan' as validation_type,
    p.country,
    p.city,
    p.lob_base,
    p.segment,
    p.month,
    'error' as severity,
    'Duplicado en PLAN por clave (plan_version,country,city_norm,lob_base,segment,month)' as message,
    COUNT(*) - 1 as row_count
FROM ops.plan_trips_monthly p
WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
GROUP BY p.plan_version, p.country, p.city, p.city_norm, p.lob_base, p.segment, p.month, COALESCE(p.park_id, '__NA__')
HAVING COUNT(*) > 1;

-- 1.2. Segment inválido
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
    lob_base,
    segment,
    month,
    severity,
    message,
    row_count
)
SELECT 
    '{PLAN_VERSION_PLACEHOLDER}' as plan_version,
    'invalid_segment' as validation_type,
    p.country,
    p.city,
    p.lob_base,
    p.segment,
    p.month,
    'error' as severity,
    'Segment inválido (debe ser b2b o b2c)' as message,
    COUNT(*) as row_count
FROM ops.plan_trips_monthly p
WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
AND p.segment IS NOT NULL
AND p.segment NOT IN ('b2b', 'b2c')
GROUP BY p.country, p.city, p.lob_base, p.segment, p.month;

-- 1.3. Month inválido
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
    lob_base,
    segment,
    month,
    severity,
    message,
    row_count
)
SELECT 
    '{PLAN_VERSION_PLACEHOLDER}' as plan_version,
    'invalid_month' as validation_type,
    p.country,
    p.city,
    p.lob_base,
    p.segment,
    p.month,
    'error' as severity,
    'Month inválido (NULL o fuera de rango)' as message,
    COUNT(*) as row_count
FROM ops.plan_trips_monthly p
WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
AND (p.month IS NULL OR p.month < '2020-01-01'::DATE OR p.month > '2100-12-31'::DATE)
GROUP BY p.country, p.city, p.lob_base, p.segment, p.month;

-- 1.4. Valores nulos o <= 0
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
    lob_base,
    segment,
    month,
    severity,
    message,
    row_count
)
SELECT 
    '{PLAN_VERSION_PLACEHOLDER}' as plan_version,
    'invalid_metrics' as validation_type,
    p.country,
    p.city,
    p.lob_base,
    p.segment,
    p.month,
    'warning' as severity,
    'Métricas inválidas: projected_trips, projected_drivers o projected_ticket nulos o <= 0' as message,
    COUNT(*) as row_count
FROM ops.plan_trips_monthly p
WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
AND (
    p.projected_trips IS NULL OR p.projected_trips <= 0
    OR p.projected_drivers IS NULL OR p.projected_drivers <= 0
    OR p.projected_ticket IS NULL OR p.projected_ticket <= 0
)
GROUP BY p.country, p.city, p.lob_base, p.segment, p.month;

-- ============================================================================
-- 2. VALIDACIONES PLAN VS REAL (USANDO AGREGADO)
-- ============================================================================

-- 2.1. Orphan Plan: combinaciones en PLAN que no existen en REAL (para meses pasados/presentes)
-- Usa plan_city_resolved_norm si está disponible, si no usa city_norm
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
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
    p.lob_base,
    p.segment,
    p.month,
    CASE 
        WHEN p.month >= DATE_TRUNC('month', CURRENT_DATE)::DATE THEN 'info'
        ELSE 'warning'
    END as severity,
    CASE 
        WHEN p.month >= DATE_TRUNC('month', CURRENT_DATE)::DATE THEN 'Plan sin equivalente en Real (mes futuro - OK)'
        ELSE 'Combinación en Plan sin equivalente en Real para mes pasado/presente'
    END as message,
    COUNT(*) as row_count
FROM ops.plan_trips_monthly p
WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
AND NOT EXISTS (
    SELECT 1
    FROM ops.mv_real_trips_monthly r
    WHERE r.month = p.month
    AND r.city_norm = COALESCE(p.plan_city_resolved_norm, p.city_norm)
    AND r.lob_base = p.lob_base
    AND r.segment = p.segment
)
GROUP BY p.country, p.city, p.lob_base, p.segment, p.month;

-- 2.2. Orphan Real: combinaciones en REAL sin PLAN (warning informativo)
-- Usa plan_city_resolved_norm si está disponible, si no usa city_norm
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
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
    r.country,
    r.city,
    r.lob_base,
    r.segment,
    r.month,
    'info' as severity,
    'Combinación en Real sin Plan correspondiente (información para revisión)' as message,
    COUNT(*) as row_count
FROM ops.mv_real_trips_monthly r
WHERE r.month >= (
    SELECT MIN(month) FROM ops.plan_trips_monthly 
    WHERE plan_version = '{PLAN_VERSION_PLACEHOLDER}'
)
AND r.month <= (
    SELECT MAX(month) FROM ops.plan_trips_monthly 
    WHERE plan_version = '{PLAN_VERSION_PLACEHOLDER}'
)
AND NOT EXISTS (
    SELECT 1
    FROM ops.plan_trips_monthly p
    WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
    AND p.month = r.month
    AND COALESCE(p.plan_city_resolved_norm, p.city_norm) = r.city_norm
    AND p.lob_base = r.lob_base
    AND p.segment = r.segment
)
GROUP BY r.country, r.city, r.lob_base, r.segment, r.month;

-- 2.3. City mismatch: city_norm inexistente en dim_park
-- Usa plan_city_resolved_norm si está disponible, si no usa city_norm
INSERT INTO ops.plan_validation_results (
    plan_version,
    validation_type,
    country,
    city,
    lob_base,
    segment,
    month,
    severity,
    message,
    row_count
)
SELECT 
    '{PLAN_VERSION_PLACEHOLDER}' as plan_version,
    'city_mismatch' as validation_type,
    p.country,
    p.city,
    p.lob_base,
    p.segment,
    p.month,
    'warning' as severity,
    CASE 
        WHEN p.plan_city_resolved_norm IS NULL THEN 'city_norm inexistente en dim_park (city puede no estar mapeada correctamente)'
        ELSE 'plan_city_resolved_norm inexistente en dim_park (mapeo en plan_city_map puede estar incorrecto)'
    END as message,
    COUNT(*) as row_count
FROM ops.plan_trips_monthly p
WHERE p.plan_version = '{PLAN_VERSION_PLACEHOLDER}'
AND (
    -- Si tiene plan_city_resolved_norm, validar que exista en dim_park
    (p.plan_city_resolved_norm IS NOT NULL 
     AND NOT EXISTS (
         SELECT 1
         FROM dim.dim_park dp
         WHERE LOWER(TRIM(COALESCE(dp.city, ''))) = p.plan_city_resolved_norm
     ))
    OR
    -- Si no tiene plan_city_resolved_norm, validar city_norm original
    (p.plan_city_resolved_norm IS NULL 
     AND p.city_norm IS NOT NULL
     AND NOT EXISTS (
         SELECT 1
         FROM dim.dim_park dp
         WHERE LOWER(TRIM(COALESCE(dp.city, ''))) = p.city_norm
     ))
)
GROUP BY p.country, p.city, p.lob_base, p.segment, p.month;

-- ============================================================================
-- REPORTE DE VALIDACIONES
-- ============================================================================
-- (El reporte se genera en Python después de ejecutar las validaciones)
