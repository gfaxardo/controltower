-- =============================================================================
-- DRIVER LIFECYCLE — Validación de trazabilidad (drilldown por park)
-- FASE D: Verificar que activations por park suman a global; consistencia churn.
-- =============================================================================

-- 1) Activations por park (semana W) = drivers cuya activation_ts cae en W y park = park de esa semana
--    Suma por park en semana W debe coincidir con activations globales de esa semana (por construcción).
WITH act_global AS (
  SELECT DATE_TRUNC('week', activation_ts)::date AS week_start, COUNT(*) AS activations_global
  FROM ops.mv_driver_lifecycle_base
  WHERE activation_ts IS NOT NULL
  GROUP BY 1
),
act_by_park AS (
  SELECT w.week_start, w.park_id, COUNT(*) AS activations
  FROM ops.mv_driver_lifecycle_base b
  JOIN ops.mv_driver_weekly_stats w
    ON w.driver_key = b.driver_key AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
  WHERE b.activation_ts IS NOT NULL AND w.park_id IS NOT NULL
  GROUP BY w.week_start, w.park_id
),
sum_by_week AS (
  SELECT week_start, SUM(activations) AS activations_sum_park
  FROM act_by_park
  GROUP BY week_start
)
SELECT
  g.week_start,
  g.activations_global,
  s.activations_sum_park,
  (g.activations_global - COALESCE(s.activations_sum_park, 0)) AS diff
FROM act_global g
LEFT JOIN sum_by_week s ON s.week_start = g.week_start
ORDER BY g.week_start DESC
LIMIT 20;
-- Esperado: diff = 0 (o drivers sin park asignado en esa semana si los hubiera).

-- 2) Churned por park: consistencia con weekly_stats (drivers en W sin fila en W+1)
-- Conteo global churn (desde weekly_kpis) vs suma de churn por park
SELECT
  k.week_start,
  k.churn_flow AS churn_global,
  COALESCE(x.churn_by_park_sum, 0) AS churn_sum_by_park,
  (k.churn_flow - COALESCE(x.churn_by_park_sum, 0)) AS diff
FROM ops.mv_driver_lifecycle_weekly_kpis k
LEFT JOIN (
  SELECT w.week_start, COUNT(DISTINCT w.driver_key) AS churn_by_park_sum
  FROM ops.mv_driver_weekly_stats w
  WHERE NOT EXISTS (
    SELECT 1 FROM ops.mv_driver_weekly_stats n
    WHERE n.driver_key = w.driver_key AND n.week_start = w.week_start + 7
  )
  GROUP BY w.week_start
) x ON x.week_start = k.week_start
ORDER BY k.week_start DESC
LIMIT 20;
-- Nota: churn_global en weekly_kpis cuenta por week_start; churn_by_park_sum aquí es igual por construcción (mismo criterio).

-- 3) Parks distintos en stats (debe haber al menos uno)
SELECT COUNT(DISTINCT park_id) AS distinct_parks FROM ops.mv_driver_weekly_stats WHERE park_id IS NOT NULL;
