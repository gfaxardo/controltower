-- =============================================================================
-- DRIVER LIFECYCLE — Validaciones (queries de chequeo)
-- Ejecutar tras refresh de MVs para sanity checks.
--
-- NOTA: scripts.run_driver_lifecycle_build usa versiones optimizadas inline
-- (acotadas por fecha, reltuples, etc.) para evitar timeouts. Este archivo
-- se mantiene como referencia para ejecución manual.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1) Activations = drivers cuyo MIN(completion_ts) cae en la semana/mes
-- -----------------------------------------------------------------------------
-- Semanal: activations en MV deben coincidir con count de drivers cuya activation_ts cae en esa semana
SELECT
  k.week_start,
  k.activations AS activations_mv,
  COALESCE(c.direct_activations, 0) AS activations_direct,
  k.activations - COALESCE(c.direct_activations, 0) AS diff
FROM ops.mv_driver_lifecycle_weekly_kpis k
LEFT JOIN (
  SELECT
    DATE_TRUNC('week', activation_ts)::date AS week_start,
    COUNT(*) AS direct_activations
  FROM ops.mv_driver_lifecycle_base
  WHERE activation_ts IS NOT NULL
  GROUP BY 1
) c ON c.week_start = k.week_start
ORDER BY k.week_start DESC
LIMIT 20;
-- Esperado: diff = 0 en todas las filas.

-- Mensual: mismo chequeo
SELECT
  k.month_start,
  k.activations AS activations_mv,
  COALESCE(c.direct_activations, 0) AS activations_direct,
  k.activations - COALESCE(c.direct_activations, 0) AS diff
FROM ops.mv_driver_lifecycle_monthly_kpis k
LEFT JOIN (
  SELECT DATE_TRUNC('month', activation_ts)::date AS month_start, COUNT(*) AS direct_activations
  FROM ops.mv_driver_lifecycle_base
  WHERE activation_ts IS NOT NULL
  GROUP BY 1
) c ON c.month_start = k.month_start
ORDER BY k.month_start DESC
LIMIT 20;

-- -----------------------------------------------------------------------------
-- 2) Join coverage: % trips con conductor_id mapeado a drivers
-- -----------------------------------------------------------------------------
SELECT
  (SELECT COUNT(*) FROM public.trips_all WHERE condicion = 'Completado' AND conductor_id IS NOT NULL) AS trips_completed_with_driver,
  COUNT(*) AS trips_matched_to_drivers,
  ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM public.trips_all WHERE condicion = 'Completado' AND conductor_id IS NOT NULL), 0), 2) AS pct_trips_mapped
FROM public.trips_all t
INNER JOIN public.drivers d ON t.conductor_id = d.driver_id
WHERE t.condicion = 'Completado' AND t.conductor_id IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 3) TtF: distribución min/median/p90 y outliers negativos
-- -----------------------------------------------------------------------------
SELECT
  MIN(ttf_days_from_registered) AS ttf_min,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ttf_days_from_registered) AS ttf_median,
  PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY ttf_days_from_registered) AS ttf_p90,
  COUNT(*) FILTER (WHERE ttf_days_from_registered < 0) AS outliers_negative
FROM ops.mv_driver_lifecycle_base
WHERE registered_ts IS NOT NULL AND ttf_days_from_registered IS NOT NULL;

-- Outliers: listar drivers con activation_ts < created_at
SELECT driver_key, activation_ts, registered_ts, ttf_days_from_registered
FROM ops.mv_driver_lifecycle_base
WHERE ttf_days_from_registered < 0
ORDER BY ttf_days_from_registered
LIMIT 20;

-- -----------------------------------------------------------------------------
-- 4) Sanity: reactivated sin haber churned (flujo lógico)
-- La definición usada: reactivated_week = (prev_week_trips = 0 or null) and trips > 0.
-- Incluye tanto "primera activación" como "vuelta tras inactividad". No hay flag
-- "estaba churned" explícito sin calendario expandido; este query verifica que
-- no haya contradicciones obvias (ej. mismo driver con dos "activations" en distintas semanas).
-- -----------------------------------------------------------------------------
-- Verificar que cada driver tiene una sola activation_ts (está en base 1 fila por driver)
SELECT COUNT(*), COUNT(DISTINCT driver_key) FROM ops.mv_driver_lifecycle_base;
-- Esperado: ambos iguales.

-- Verificar unicidad (driver_key, week_start) en weekly_stats
SELECT driver_key, week_start, COUNT(*)
FROM ops.mv_driver_weekly_stats
GROUP BY driver_key, week_start
HAVING COUNT(*) > 1;
-- Esperado: 0 filas.
