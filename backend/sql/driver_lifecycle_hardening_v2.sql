-- =============================================================================
-- DRIVER LIFECYCLE — Hardening v2
-- FASE 2: park_dominante_semana = park_id con mayor trips_completed_week por driver+week.
--         Empate → menor park_id (determinístico).
-- FASE 3: weekly_kpis desde una sola fuente (activations vía join base; resto desde weekly_stats).
-- Ejecutar en transacción: si falla → rollback automático desde Python.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- FASE 2: Redefinición de ops.mv_driver_weekly_stats con park_dominante
-- Documentación: park_dominante_semana = argmax_park COUNT(*) por (driver, week, park).
--                Desempate: MIN(park_id). Una sola MV, una sola lógica.
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS ops.v_driver_weekly_churn_reactivation CASCADE;
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_lifecycle_weekly_kpis CASCADE;
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_weekly_stats CASCADE;

CREATE MATERIALIZED VIEW ops.mv_driver_weekly_stats AS
WITH driver_week_park AS (
  SELECT
    conductor_id,
    DATE_TRUNC('week', completion_ts)::date AS week_start,
    park_id,
    COUNT(*) AS trips_in_park,
    MIN(tipo_servicio) AS tipo_servicio,
    MIN(segment) AS segment
  FROM ops.v_driver_lifecycle_trips_completed
  WHERE park_id IS NOT NULL AND TRIM(COALESCE(park_id::text, '')) != ''
  GROUP BY conductor_id, DATE_TRUNC('week', completion_ts)::date, park_id
),
total_trips AS (
  SELECT
    conductor_id,
    DATE_TRUNC('week', completion_ts)::date AS week_start,
    COUNT(*) AS trips_completed_week
  FROM ops.v_driver_lifecycle_trips_completed
  GROUP BY conductor_id, DATE_TRUNC('week', completion_ts)::date
),
ranked AS (
  SELECT
    conductor_id,
    week_start,
    park_id,
    trips_in_park,
    tipo_servicio,
    segment,
    ROW_NUMBER() OVER (
      PARTITION BY conductor_id, week_start
      ORDER BY trips_in_park DESC, park_id ASC
    ) AS rn
  FROM driver_week_park
),
dominant AS (
  SELECT conductor_id, week_start, park_id, tipo_servicio, segment
  FROM ranked
  WHERE rn = 1
)
SELECT
  t.conductor_id AS driver_key,
  t.week_start,
  t.trips_completed_week,
  CASE WHEN t.trips_completed_week >= 20 THEN 'FT' ELSE 'PT' END AS work_mode_week,
  d.park_id,
  d.tipo_servicio,
  d.segment,
  TRUE AS is_active_week
FROM total_trips t
LEFT JOIN dominant d ON d.conductor_id = t.conductor_id AND d.week_start = t.week_start;

CREATE UNIQUE INDEX ux_mv_driver_weekly_stats_driver_week
  ON ops.mv_driver_weekly_stats (driver_key, week_start);

COMMENT ON MATERIALIZED VIEW ops.mv_driver_weekly_stats IS
  'Driver-week con park_dominante_semana = park_id con mayor trips en la semana; desempate: menor park_id. Una sola fuente para KPIs por park.';

-- Recrear vista churn/reactivation (depende de weekly_stats)
CREATE VIEW ops.v_driver_weekly_churn_reactivation AS
WITH bounds AS (
  SELECT
    driver_key,
    week_start,
    trips_completed_week,
    work_mode_week,
    park_id,
    tipo_servicio,
    segment,
    is_active_week,
    LAG(trips_completed_week) OVER (PARTITION BY driver_key ORDER BY week_start) AS prev_week_trips
  FROM ops.mv_driver_weekly_stats
)
SELECT
  driver_key,
  week_start,
  trips_completed_week,
  work_mode_week,
  park_id,
  tipo_servicio,
  segment,
  is_active_week,
  (prev_week_trips > 0 AND COALESCE(trips_completed_week, 0) = 0) AS churn_flow_week,
  (COALESCE(prev_week_trips, 0) = 0 AND trips_completed_week > 0) AS reactivated_week
FROM bounds;

-- -----------------------------------------------------------------------------
-- FASE 3: ops.mv_driver_lifecycle_weekly_kpis — una sola fuente
-- Activations: desde base (join week_start); active_drivers, churn_flow, reactivated: desde weekly_stats.
-- Garantía: Σ por park = global porque weekly_stats tiene una fila por (driver, week) con park_id.
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW ops.mv_driver_lifecycle_weekly_kpis AS
WITH week_calendar AS (
  SELECT DISTINCT week_start FROM ops.mv_driver_weekly_stats
),
activations_week AS (
  SELECT DATE_TRUNC('week', activation_ts)::date AS week_start, COUNT(*) AS activations
  FROM ops.mv_driver_lifecycle_base
  WHERE activation_ts IS NOT NULL
  GROUP BY 1
),
active_drivers_week AS (
  SELECT week_start, COUNT(DISTINCT driver_key) AS active_drivers
  FROM ops.mv_driver_weekly_stats
  GROUP BY week_start
),
churn_flow_week AS (
  SELECT w.week_start, COUNT(DISTINCT w.driver_key) AS churn_flow
  FROM ops.mv_driver_weekly_stats w
  WHERE NOT EXISTS (
    SELECT 1 FROM ops.mv_driver_weekly_stats n
    WHERE n.driver_key = w.driver_key AND n.week_start = w.week_start + 7
  )
  GROUP BY w.week_start
),
reactivated_week AS (
  SELECT week_start, COUNT(*) AS reactivated
  FROM ops.v_driver_weekly_churn_reactivation
  WHERE reactivated_week
  GROUP BY week_start
)
SELECT
  w.week_start,
  COALESCE(ax.activations, 0) AS activations,
  COALESCE(ad.active_drivers, 0) AS active_drivers,
  COALESCE(cf.churn_flow, 0) AS churn_flow,
  COALESCE(rx.reactivated, 0) AS reactivated
FROM week_calendar w
LEFT JOIN activations_week ax ON ax.week_start = w.week_start
LEFT JOIN active_drivers_week ad ON ad.week_start = w.week_start
LEFT JOIN churn_flow_week cf ON cf.week_start = w.week_start
LEFT JOIN reactivated_week rx ON rx.week_start = w.week_start;

CREATE UNIQUE INDEX ux_mv_driver_lifecycle_weekly_kpis_week
  ON ops.mv_driver_lifecycle_weekly_kpis (week_start);

COMMIT;
