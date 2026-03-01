-- =============================================================================
-- DRIVER LIFECYCLE — Build (solo datos reales: public.trips_all, public.drivers)
-- Schema: ops. Nombres de columnas reales (no inventados).
-- =============================================================================

-- Crear schema si no existe
CREATE SCHEMA IF NOT EXISTS ops;

-- -----------------------------------------------------------------------------
-- Base: viajes completados con completion_ts y request_ts
-- completion_ts = COALESCE(fecha_finalizacion, fecha_inicio_viaje)
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS ops.v_driver_lifecycle_trips_completed CASCADE;
CREATE VIEW ops.v_driver_lifecycle_trips_completed AS
SELECT
  t.conductor_id,
  t.condicion,
  t.fecha_inicio_viaje AS request_ts,
  COALESCE(t.fecha_finalizacion, t.fecha_inicio_viaje) AS completion_ts,
  t.park_id,
  t.tipo_servicio,
  CASE WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b' ELSE 'b2c' END AS segment
FROM public.trips_all t
WHERE t.condicion = 'Completado'
  AND t.conductor_id IS NOT NULL
  AND t.fecha_inicio_viaje IS NOT NULL;

-- -----------------------------------------------------------------------------
-- D.1) MV driver_lifecycle_base (1 fila por driver)
-- Join drivers por conductor_id = driver_id. registered_ts = drivers.created_at
-- -----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_lifecycle_base CASCADE;
CREATE MATERIALIZED VIEW ops.mv_driver_lifecycle_base AS
WITH first_last AS (
  SELECT
    conductor_id,
    MIN(completion_ts) AS activation_ts,
    MAX(completion_ts) AS last_completed_ts,
    COUNT(*) AS total_trips_completed
  FROM ops.v_driver_lifecycle_trips_completed
  GROUP BY conductor_id
)
SELECT
  f.conductor_id AS driver_key,
  f.activation_ts,
  f.last_completed_ts,
  f.total_trips_completed,
  (f.last_completed_ts::date - f.activation_ts::date) AS lifetime_days,
  EXTRACT(HOUR FROM f.activation_ts)::INT AS activation_hour,
  d.created_at AS registered_ts,
  d.hire_date AS hire_date,
  (f.activation_ts::date - d.created_at::date) AS ttf_days_from_registered,
  d.park_id AS driver_park_id
FROM first_last f
LEFT JOIN public.drivers d ON f.conductor_id = d.driver_id;

CREATE UNIQUE INDEX ux_mv_driver_lifecycle_base_driver
  ON ops.mv_driver_lifecycle_base (driver_key);

-- -----------------------------------------------------------------------------
-- D.2) MV driver_weekly_stats (driver-week)
-- week_start = lunes. Dims: park_id y tipo_servicio por modo (primer trip de la semana)
-- -----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_weekly_stats CASCADE;
CREATE MATERIALIZED VIEW ops.mv_driver_weekly_stats AS
WITH week_trips AS (
  SELECT
    conductor_id,
    DATE_TRUNC('week', completion_ts)::date AS week_start,
    completion_ts,
    park_id,
    tipo_servicio,
    segment
  FROM ops.v_driver_lifecycle_trips_completed
),
agg AS (
  SELECT
    conductor_id,
    week_start,
    COUNT(*) AS trips_completed_week,
    MIN(park_id) AS park_id_mode,
    MIN(tipo_servicio) AS tipo_servicio_mode,
    MIN(segment) AS segment_mode
  FROM week_trips
  GROUP BY conductor_id, week_start
),
-- Umbral PT/FT: 20 trips/week (calibrar con percentiles después)
work_mode AS (
  SELECT
    conductor_id,
    week_start,
    trips_completed_week,
    park_id_mode,
    tipo_servicio_mode,
    segment_mode,
    CASE WHEN trips_completed_week >= 20 THEN 'FT' ELSE 'PT' END AS work_mode_week
  FROM agg
)
SELECT
  w.conductor_id AS driver_key,
  w.week_start,
  w.trips_completed_week,
  w.work_mode_week,
  w.park_id_mode AS park_id,
  w.tipo_servicio_mode AS tipo_servicio,
  w.segment_mode AS segment,
  TRUE AS is_active_week
FROM work_mode w;

CREATE UNIQUE INDEX ux_mv_driver_weekly_stats_driver_week
  ON ops.mv_driver_weekly_stats (driver_key, week_start);

-- -----------------------------------------------------------------------------
-- Churn/Reactivation: vistas derivadas por ventana 14d y 28d
-- churn_14d: última actividad > 14 días antes del fin de semana
-- -----------------------------------------------------------------------------
DROP VIEW IF EXISTS ops.v_driver_weekly_churn_reactivation CASCADE;
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
    LAG(trips_completed_week) OVER (PARTITION BY driver_key ORDER BY week_start) AS prev_week_trips,
    LEAD(trips_completed_week) OVER (PARTITION BY driver_key ORDER BY week_start) AS next_week_trips
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
-- D.3) MV driver_monthly_stats (driver-month)
-- -----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_monthly_stats CASCADE;
CREATE MATERIALIZED VIEW ops.mv_driver_monthly_stats AS
WITH month_trips AS (
  SELECT
    conductor_id,
    DATE_TRUNC('month', completion_ts)::date AS month_start,
    park_id,
    tipo_servicio,
    segment
  FROM ops.v_driver_lifecycle_trips_completed
),
agg AS (
  SELECT
    conductor_id,
    month_start,
    COUNT(*) AS trips_completed_month,
    MIN(park_id) AS park_id_mode,
    MIN(tipo_servicio) AS tipo_servicio_mode,
    MIN(segment) AS segment_mode
  FROM month_trips
  GROUP BY conductor_id, month_start
)
SELECT
  conductor_id AS driver_key,
  month_start,
  trips_completed_month,
  CASE WHEN trips_completed_month >= 80 THEN 'FT' ELSE 'PT' END AS work_mode_month,
  park_id_mode AS park_id,
  tipo_servicio_mode AS tipo_servicio,
  segment_mode AS segment,
  TRUE AS is_active_month
FROM agg;

CREATE UNIQUE INDEX ux_mv_driver_monthly_stats_driver_month
  ON ops.mv_driver_monthly_stats (driver_key, month_start);

-- -----------------------------------------------------------------------------
-- D.4) MV weekly_kpis (agregado por week_start). Semana ISO = lunes.
-- -----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_lifecycle_weekly_kpis CASCADE;
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
-- Churn flow: drivers que estaban activos en week_start W y no aparecen en W+1
churn_flow_week AS (
  SELECT
    w.week_start,
    COUNT(DISTINCT w.driver_key) AS churn_flow
  FROM ops.mv_driver_weekly_stats w
  WHERE NOT EXISTS (
    SELECT 1 FROM ops.mv_driver_weekly_stats n
    WHERE n.driver_key = w.driver_key
      AND n.week_start = w.week_start + 7
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

-- -----------------------------------------------------------------------------
-- D.4b) MV monthly_kpis (agregado por month)
-- -----------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_lifecycle_monthly_kpis CASCADE;
CREATE MATERIALIZED VIEW ops.mv_driver_lifecycle_monthly_kpis AS
WITH month_calendar AS (
  SELECT DISTINCT month_start FROM ops.mv_driver_monthly_stats
),
activations_month AS (
  SELECT DATE_TRUNC('month', activation_ts)::date AS month_start, COUNT(*) AS activations
  FROM ops.mv_driver_lifecycle_base
  WHERE activation_ts IS NOT NULL
  GROUP BY 1
),
active_drivers_month AS (
  SELECT month_start, COUNT(DISTINCT driver_key) AS active_drivers
  FROM ops.mv_driver_monthly_stats
  GROUP BY month_start
)
SELECT
  m.month_start,
  COALESCE(ax.activations, 0) AS activations,
  COALESCE(ad.active_drivers, 0) AS active_drivers
FROM month_calendar m
LEFT JOIN activations_month ax ON ax.month_start = m.month_start
LEFT JOIN active_drivers_month ad ON ad.month_start = m.month_start;

CREATE UNIQUE INDEX ux_mv_driver_lifecycle_monthly_kpis_month
  ON ops.mv_driver_lifecycle_monthly_kpis (month_start);

-- -----------------------------------------------------------------------------
-- D.5) Función refresh (hardening: timeout 60min, lock_timeout 60s, CONCURRENTLY)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION ops.refresh_driver_lifecycle_mvs()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  t0 timestamptz := clock_timestamp();
BEGIN
  PERFORM set_config('statement_timeout', '60min', true);
  PERFORM set_config('lock_timeout', '60s', true);
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_base;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_weekly_stats;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_monthly_stats;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_weekly_kpis;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_monthly_kpis;
  RAISE NOTICE '[driver_lifecycle] refresh done in % s', round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);
END;
$$;

-- Comentario: v_driver_weekly_churn_reactivation es VIEW sobre MVs, no requiere refresh.
-- Tras el build, ejecutar sql/driver_lifecycle_refresh_hardening.sql para:
--   - Duración por paso (RAISE NOTICE)
--   - Fallback nonc (refresh_driver_lifecycle_mvs_nonc)
--   - Variante 3only (solo base, weekly_kpis, monthly_kpis)
