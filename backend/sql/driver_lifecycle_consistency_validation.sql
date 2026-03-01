-- =============================================================================
-- DRIVER LIFECYCLE — Validación de consistencia matemática
-- Regla crítica: Σ KPI por park = KPI global (por semana).
-- Si hay diff, mostrar semana y diff; no continuar a siguiente fase.
-- =============================================================================

-- A) Σ activations por park = activations global
-- Activations por park: base join weekly_stats (park en semana de activación)
-- Global: ops.mv_driver_lifecycle_weekly_kpis.activations
WITH activations_by_park AS (
  SELECT
    w.week_start,
    w.park_id,
    COUNT(*) AS activations
  FROM ops.mv_driver_lifecycle_base b
  JOIN ops.mv_driver_weekly_stats w
    ON w.driver_key = b.driver_key
    AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
  WHERE b.activation_ts IS NOT NULL
    AND w.park_id IS NOT NULL
  GROUP BY w.week_start, w.park_id
),
sum_activations_by_week AS (
  SELECT week_start, SUM(activations) AS sum_activations
  FROM activations_by_park
  GROUP BY week_start
)
SELECT
  k.week_start::text AS week_start,
  k.activations AS global_activations,
  COALESCE(s.sum_activations, 0) AS sum_by_park,
  (k.activations - COALESCE(s.sum_activations, 0)) AS diff_activations,
  CASE WHEN k.activations <> COALESCE(s.sum_activations, 0) THEN 'FAIL' ELSE 'OK' END AS status
FROM ops.mv_driver_lifecycle_weekly_kpis k
LEFT JOIN sum_activations_by_week s ON s.week_start = k.week_start
WHERE k.activations <> COALESCE(s.sum_activations, 0)
ORDER BY k.week_start DESC
LIMIT 50;
-- Si devuelve filas: hay inconsistencias. Causa probable: drivers con activation_ts en esa semana
-- que no tienen fila en mv_driver_weekly_stats para esa semana (o park_id NULL).

-- B) Σ churn_flow por park = churn_flow global
-- Churn por park: drivers en weekly_stats (week_start, park_id) que no tienen fila en week_start+7
WITH churn_by_park AS (
  SELECT
    w.week_start,
    w.park_id,
    COUNT(DISTINCT w.driver_key) AS churned
  FROM ops.mv_driver_weekly_stats w
  WHERE w.park_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM ops.mv_driver_weekly_stats n
      WHERE n.driver_key = w.driver_key AND n.week_start = w.week_start + 7
    )
  GROUP BY w.week_start, w.park_id
),
sum_churn_by_week AS (
  SELECT week_start, SUM(churned) AS sum_churned
  FROM churn_by_park
  GROUP BY week_start
)
SELECT
  k.week_start::text AS week_start,
  k.churn_flow AS global_churn_flow,
  COALESCE(s.sum_churned, 0) AS sum_by_park,
  (k.churn_flow - COALESCE(s.sum_churned, 0)) AS diff_churn,
  CASE WHEN k.churn_flow <> COALESCE(s.sum_churned, 0) THEN 'FAIL' ELSE 'OK' END AS status
FROM ops.mv_driver_lifecycle_weekly_kpis k
LEFT JOIN sum_churn_by_week s ON s.week_start = k.week_start
WHERE k.churn_flow <> COALESCE(s.sum_churned, 0)
ORDER BY k.week_start DESC
LIMIT 50;

-- C) Σ reactivated por park = reactivated global
WITH react_by_park AS (
  SELECT week_start, park_id, COUNT(*) AS reactivated
  FROM ops.v_driver_weekly_churn_reactivation
  WHERE reactivated_week AND park_id IS NOT NULL
  GROUP BY week_start, park_id
),
sum_react_by_week AS (
  SELECT week_start, SUM(reactivated) AS sum_reactivated
  FROM react_by_park
  GROUP BY week_start
)
SELECT
  k.week_start::text AS week_start,
  k.reactivated AS global_reactivated,
  COALESCE(s.sum_reactivated, 0) AS sum_by_park,
  (k.reactivated - COALESCE(s.sum_reactivated, 0)) AS diff_reactivated,
  CASE WHEN k.reactivated <> COALESCE(s.sum_reactivated, 0) THEN 'FAIL' ELSE 'OK' END AS status
FROM ops.mv_driver_lifecycle_weekly_kpis k
LEFT JOIN sum_react_by_week s ON s.week_start = k.week_start
WHERE k.reactivated <> COALESCE(s.sum_reactivated, 0)
ORDER BY k.week_start DESC
LIMIT 50;

-- D) Σ active_drivers por park = active_drivers global
-- Por semana, cada driver puede tener una sola fila en weekly_stats (driver_key, week_start).
-- Esa fila tiene un único park_id (dominante). Por tanto suma por park = total.
WITH active_by_park AS (
  SELECT week_start, park_id, COUNT(DISTINCT driver_key) AS active_drivers
  FROM ops.mv_driver_weekly_stats
  GROUP BY week_start, park_id
),
sum_active_by_week AS (
  SELECT week_start, SUM(active_drivers) AS sum_active
  FROM active_by_park
  GROUP BY week_start
)
SELECT
  k.week_start::text AS week_start,
  k.active_drivers AS global_active_drivers,
  COALESCE(s.sum_active, 0) AS sum_by_park,
  (k.active_drivers - COALESCE(s.sum_active, 0)) AS diff_active_drivers,
  CASE WHEN k.active_drivers <> COALESCE(s.sum_active, 0) THEN 'FAIL' ELSE 'OK' END AS status
FROM ops.mv_driver_lifecycle_weekly_kpis k
LEFT JOIN sum_active_by_week s ON s.week_start = k.week_start
WHERE k.active_drivers <> COALESCE(s.sum_active, 0)
ORDER BY k.week_start DESC
LIMIT 50;

-- Resumen: ejecutar los 4 bloques. Si alguno devuelve filas → hay bug (investigar antes de FASE 2+).
-- Causas probables:
-- A) Activations: driver activó en semana W pero no tiene fila en weekly_stats para W (ej. park_id NULL en trips).
-- B) Churn: inconsistencia en definición de "no aparece en W+1".
-- C) Reactivated: vista churn_reactivation puede filtrar por park_id y dejar fuera algunos.
-- D) Active: driver con fila en weekly_stats pero park_id NULL (no debería si park_dominante está bien definido).
