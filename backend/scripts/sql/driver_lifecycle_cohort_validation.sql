-- =============================================================================
-- DRIVER LIFECYCLE — FASE 6: Validaciones de cohortes
-- =============================================================================

-- 1) cohort_size = drivers cuyo activation_week = cohort_week (por cohort_week y park_id)
WITH base_cohort AS (
  SELECT
    DATE_TRUNC('week', b.activation_ts)::date AS cohort_week,
    w.park_id,
    COUNT(*) AS expected_size
  FROM ops.mv_driver_lifecycle_base b
  LEFT JOIN ops.mv_driver_weekly_stats w
    ON w.driver_key = b.driver_key
    AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
  WHERE b.activation_ts IS NOT NULL
  GROUP BY DATE_TRUNC('week', b.activation_ts)::date, w.park_id
)
SELECT
  k.cohort_week::text,
  k.park_id,
  k.cohort_size AS mv_size,
  c.expected_size,
  (k.cohort_size - c.expected_size) AS diff,
  CASE WHEN k.cohort_size <> c.expected_size THEN 'FAIL' ELSE 'OK' END AS status
FROM ops.mv_driver_cohort_kpis k
LEFT JOIN base_cohort c ON c.cohort_week = k.cohort_week AND c.park_id IS NOT DISTINCT FROM k.park_id
WHERE k.cohort_size <> COALESCE(c.expected_size, 0)
ORDER BY k.cohort_week DESC
LIMIT 20;

-- 2) retention_w1 <= 1 (y w4, w8, w12)
SELECT cohort_week, park_id, retention_w1, retention_w4, retention_w8, retention_w12
FROM ops.mv_driver_cohort_kpis
WHERE retention_w1 > 1 OR retention_w4 > 1 OR retention_w8 > 1 OR retention_w12 > 1;
-- Esperado: 0 filas

-- 3) No hay drivers contados fuera de cohorte (cada driver_key aparece solo en su cohort_week)
WITH cohort_weeks AS (
  SELECT driver_key, cohort_week FROM ops.mv_driver_cohorts_weekly
),
activation_week AS (
  SELECT driver_key, DATE_TRUNC('week', activation_ts)::date AS act_week
  FROM ops.mv_driver_lifecycle_base
  WHERE activation_ts IS NOT NULL
)
SELECT c.driver_key, c.cohort_week, a.act_week,
  CASE WHEN c.cohort_week <> a.act_week THEN 'FAIL' ELSE 'OK' END AS status
FROM cohort_weeks c
JOIN activation_week a ON a.driver_key = c.driver_key
WHERE c.cohort_week <> a.act_week
LIMIT 20;
-- Esperado: 0 filas
