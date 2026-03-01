-- =============================================================================
-- DRIVER LIFECYCLE — FASE 5: Cohortes por Park
-- cohort_week = DATE_TRUNC('week', activation_ts)::date
-- park_id = park_dominante en semana de activación (desde mv_driver_weekly_stats)
-- Activo en W+n = tiene trips_completed_week > 0 en esa semana (fila en weekly_stats)
-- =============================================================================

DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_cohort_kpis CASCADE;
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_cohorts_weekly CASCADE;

CREATE MATERIALIZED VIEW ops.mv_driver_cohorts_weekly AS
WITH cohort_base AS (
  SELECT
    b.driver_key,
    DATE_TRUNC('week', b.activation_ts)::date AS cohort_week,
    w.park_id
  FROM ops.mv_driver_lifecycle_base b
  LEFT JOIN ops.mv_driver_weekly_stats w
    ON w.driver_key = b.driver_key
    AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
  WHERE b.activation_ts IS NOT NULL
),
w1 AS (
  SELECT driver_key, cohort_week, 1 AS active_w1
  FROM cohort_base c
  WHERE EXISTS (
    SELECT 1 FROM ops.mv_driver_weekly_stats s
    WHERE s.driver_key = c.driver_key AND s.week_start = c.cohort_week + 7
  )
),
w4 AS (
  SELECT driver_key, cohort_week, 1 AS active_w4
  FROM cohort_base c
  WHERE EXISTS (
    SELECT 1 FROM ops.mv_driver_weekly_stats s
    WHERE s.driver_key = c.driver_key AND s.week_start = c.cohort_week + 28
  )
),
w8 AS (
  SELECT driver_key, cohort_week, 1 AS active_w8
  FROM cohort_base c
  WHERE EXISTS (
    SELECT 1 FROM ops.mv_driver_weekly_stats s
    WHERE s.driver_key = c.driver_key AND s.week_start = c.cohort_week + 56
  )
),
w12 AS (
  SELECT driver_key, cohort_week, 1 AS active_w12
  FROM cohort_base c
  WHERE EXISTS (
    SELECT 1 FROM ops.mv_driver_weekly_stats s
    WHERE s.driver_key = c.driver_key AND s.week_start = c.cohort_week + 84
  )
)
SELECT
  c.driver_key,
  c.cohort_week,
  c.park_id,
  COALESCE(w1.active_w1, 0) AS active_w1,
  COALESCE(w4.active_w4, 0) AS active_w4,
  COALESCE(w8.active_w8, 0) AS active_w8,
  COALESCE(w12.active_w12, 0) AS active_w12
FROM cohort_base c
LEFT JOIN w1 ON w1.driver_key = c.driver_key AND w1.cohort_week = c.cohort_week
LEFT JOIN w4 ON w4.driver_key = c.driver_key AND w4.cohort_week = c.cohort_week
LEFT JOIN w8 ON w8.driver_key = c.driver_key AND w8.cohort_week = c.cohort_week
LEFT JOIN w12 ON w12.driver_key = c.driver_key AND w12.cohort_week = c.cohort_week;

CREATE UNIQUE INDEX ux_mv_driver_cohorts_weekly_driver_cohort
  ON ops.mv_driver_cohorts_weekly (driver_key, cohort_week);

-- Agregado por cohort_week, park_id
CREATE MATERIALIZED VIEW ops.mv_driver_cohort_kpis AS
SELECT
  cohort_week,
  park_id,
  COUNT(*) AS cohort_size,
  SUM(active_w1)::float / NULLIF(COUNT(*), 0) AS retention_w1,
  SUM(active_w4)::float / NULLIF(COUNT(*), 0) AS retention_w4,
  SUM(active_w8)::float / NULLIF(COUNT(*), 0) AS retention_w8,
  SUM(active_w12)::float / NULLIF(COUNT(*), 0) AS retention_w12
FROM ops.mv_driver_cohorts_weekly
GROUP BY cohort_week, park_id;

CREATE UNIQUE INDEX ux_mv_driver_cohort_kpis_cohort_park
  ON ops.mv_driver_cohort_kpis (cohort_week, park_id);
