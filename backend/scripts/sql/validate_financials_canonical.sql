-- VALIDACIONES OBLIGATORIAS PARA KPIs FINANCIEROS CANÓNICOS
-- Ejecutar después de aplicar migraciones 011 y 012

-- A) Enero 2026 PE: Validar revenue_yego_plan
-- Esperado: SUM(revenue_yego_plan) ≈ 263,428.97 (según archivo)
SELECT 
    'A) Enero 2026 PE - Revenue Plan' as validacion,
    SUM(revenue_yego_plan) as revenue_yego_plan_total,
    263428.97 as esperado,
    ABS(SUM(revenue_yego_plan) - 263428.97) as diferencia,
    CASE 
        WHEN ABS(SUM(revenue_yego_plan) - 263428.97) < 100 THEN '✓ OK'
        ELSE '✗ ALERTA: Diferencia significativa'
    END as status
FROM ops.v_plan_trips_monthly_latest
WHERE EXTRACT(YEAR FROM month) = 2026
AND EXTRACT(MONTH FROM month) = 1
AND country = 'PE';

-- B) Real 2025: Validar revenue_yego_real = SUM(comision_empresa_asociada)
SELECT 
    'B) Real 2025 - Revenue YEGO' as validacion,
    SUM(revenue_yego_real) as revenue_yego_real_total,
    (SELECT SUM(ABS(COALESCE(comision_empresa_asociada, 0)))
     FROM public.trips_all
     WHERE condicion = 'Completado'
     AND EXTRACT(YEAR FROM fecha_inicio_viaje) = 2025) as desde_trips_all,
    ABS(SUM(revenue_yego_real) - 
        (SELECT SUM(ABS(COALESCE(comision_empresa_asociada, 0)))
         FROM public.trips_all
         WHERE condicion = 'Completado'
         AND EXTRACT(YEAR FROM fecha_inicio_viaje) = 2025)) as diferencia,
    CASE 
        WHEN ABS(SUM(revenue_yego_real) - 
                 (SELECT SUM(ABS(COALESCE(comision_empresa_asociada, 0)))
                  FROM public.trips_all
                  WHERE condicion = 'Completado'
                  AND EXTRACT(YEAR FROM fecha_inicio_viaje) = 2025)) < 1 THEN '✓ OK'
        ELSE '✗ ALERTA: No coincide con trips_all'
    END as status
FROM ops.mv_real_financials_monthly
WHERE year = 2025;

-- C) take_rate_real: Validar que esté entre 2% y 6%
SELECT 
    'C) Take Rate Real - Rango' as validacion,
    MIN(take_rate_real) as take_rate_min,
    MAX(take_rate_real) as take_rate_max,
    AVG(take_rate_real) as take_rate_promedio,
    COUNT(*) FILTER (WHERE take_rate_real < 0.02 OR take_rate_real > 0.06) as fuera_de_rango,
    CASE 
        WHEN COUNT(*) FILTER (WHERE take_rate_real < 0.02 OR take_rate_real > 0.06) = 0 THEN '✓ OK'
        ELSE '✗ ALERTA: Hay valores fuera del rango 2%-6%'
    END as status
FROM ops.mv_real_financials_monthly
WHERE year = 2025
AND take_rate_real IS NOT NULL;

-- D) Validar que no haya proxy 3% en REAL
SELECT 
    'D) Proxy 3% en REAL' as validacion,
    COUNT(*) as registros_con_proxy,
    CASE 
        WHEN COUNT(*) = 0 THEN '✓ OK: No hay proxy en REAL'
        ELSE '✗ ALERTA: Se encontró proxy en REAL (PROHIBIDO)'
    END as status
FROM ops.mv_real_financials_monthly
WHERE year = 2025
AND revenue_yego_real = trips_real * (gmv_real / NULLIF(trips_real, 0)) * 0.03;

-- E) Validar que GMV no se use como revenue
SELECT 
    'E) GMV como Revenue' as validacion,
    COUNT(*) as registros_gmv_como_revenue,
    CASE 
        WHEN COUNT(*) = 0 THEN '✓ OK: GMV no se usa como revenue'
        ELSE '✗ ALERTA: Se encontró GMV usado como revenue (PROHIBIDO)'
    END as status
FROM ops.mv_real_financials_monthly
WHERE year = 2025
AND ABS(revenue_yego_real - gmv_real) < 0.01;

-- F) Validar estructura de vista plan
SELECT 
    'F) Estructura Vista Plan' as validacion,
    COUNT(*) as registros_con_revenue_yego_plan,
    COUNT(*) FILTER (WHERE revenue_yego_plan IS NOT NULL) as registros_con_revenue,
    COUNT(*) FILTER (WHERE is_estimated = true) as registros_estimados,
    COUNT(*) FILTER (WHERE is_estimated = false) as registros_explicitos,
    CASE 
        WHEN COUNT(*) > 0 THEN '✓ OK: Vista plan tiene estructura correcta'
        ELSE '✗ ALERTA: Vista plan vacía o sin estructura'
    END as status
FROM ops.v_plan_trips_monthly_latest
WHERE EXTRACT(YEAR FROM month) = 2026;
