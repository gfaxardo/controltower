-- Restore Driver Lifecycle v1 (rollback automático si consistency falla)
-- NO ejecutar manualmente salvo rollback.

-- DROP (dependientes primero)
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_lifecycle_monthly_kpis CASCADE;
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_monthly_stats CASCADE;
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_lifecycle_weekly_kpis CASCADE;
DROP VIEW IF EXISTS ops.v_driver_weekly_churn_reactivation CASCADE;
DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_weekly_stats CASCADE;

-- CREATE (orden de dependencias)
-- ops.mv_driver_weekly_stats
CREATE MATERIALIZED VIEW ops.mv_driver_weekly_stats AS
 WITH driver_week_park AS (
         SELECT v_driver_lifecycle_trips_completed.conductor_id,
            date_trunc('week'::text, v_driver_lifecycle_trips_completed.completion_ts)::date AS week_start,
            v_driver_lifecycle_trips_completed.park_id,
            count(*) AS trips_in_park,
            min(v_driver_lifecycle_trips_completed.tipo_servicio::text) AS tipo_servicio,
            min(v_driver_lifecycle_trips_completed.segment) AS segment
           FROM ops.v_driver_lifecycle_trips_completed
          WHERE v_driver_lifecycle_trips_completed.park_id IS NOT NULL AND btrim(COALESCE(v_driver_lifecycle_trips_completed.park_id::text, ''::text)) <> ''::text
          GROUP BY v_driver_lifecycle_trips_completed.conductor_id, (date_trunc('week'::text, v_driver_lifecycle_trips_completed.completion_ts)::date), v_driver_lifecycle_trips_completed.park_id
        ), total_trips AS (
         SELECT v_driver_lifecycle_trips_completed.conductor_id,
            date_trunc('week'::text, v_driver_lifecycle_trips_completed.completion_ts)::date AS week_start,
            count(*) AS trips_completed_week
           FROM ops.v_driver_lifecycle_trips_completed
          GROUP BY v_driver_lifecycle_trips_completed.conductor_id, (date_trunc('week'::text, v_driver_lifecycle_trips_completed.completion_ts)::date)
        ), ranked AS (
         SELECT driver_week_park.conductor_id,
            driver_week_park.week_start,
            driver_week_park.park_id,
            driver_week_park.trips_in_park,
            driver_week_park.tipo_servicio,
            driver_week_park.segment,
            row_number() OVER (PARTITION BY driver_week_park.conductor_id, driver_week_park.week_start ORDER BY driver_week_park.trips_in_park DESC, driver_week_park.park_id) AS rn
           FROM driver_week_park
        ), dominant AS (
         SELECT ranked.conductor_id,
            ranked.week_start,
            ranked.park_id,
            ranked.tipo_servicio,
            ranked.segment
           FROM ranked
          WHERE ranked.rn = 1
        )
 SELECT t.conductor_id AS driver_key,
    t.week_start,
    t.trips_completed_week,
        CASE
            WHEN t.trips_completed_week >= 20 THEN 'FT'::text
            ELSE 'PT'::text
        END AS work_mode_week,
    d.park_id,
    d.tipo_servicio,
    d.segment,
    true AS is_active_week
   FROM total_trips t
     LEFT JOIN dominant d ON d.conductor_id::text = t.conductor_id::text AND d.week_start = t.week_start;
WITH DATA;
-- ops.v_driver_weekly_churn_reactivation
CREATE OR REPLACE VIEW ops.v_driver_weekly_churn_reactivation AS
 WITH bounds AS (
         SELECT mv_driver_weekly_stats.driver_key,
            mv_driver_weekly_stats.week_start,
            mv_driver_weekly_stats.trips_completed_week,
            mv_driver_weekly_stats.work_mode_week,
            mv_driver_weekly_stats.park_id,
            mv_driver_weekly_stats.tipo_servicio,
            mv_driver_weekly_stats.segment,
            mv_driver_weekly_stats.is_active_week,
            lag(mv_driver_weekly_stats.trips_completed_week) OVER (PARTITION BY mv_driver_weekly_stats.driver_key ORDER BY mv_driver_weekly_stats.week_start) AS prev_week_trips
           FROM ops.mv_driver_weekly_stats
        )
 SELECT bounds.driver_key,
    bounds.week_start,
    bounds.trips_completed_week,
    bounds.work_mode_week,
    bounds.park_id,
    bounds.tipo_servicio,
    bounds.segment,
    bounds.is_active_week,
    bounds.prev_week_trips > 0 AND COALESCE(bounds.trips_completed_week, 0::bigint) = 0 AS churn_flow_week,
    COALESCE(bounds.prev_week_trips, 0::bigint) = 0 AND bounds.trips_completed_week > 0 AS reactivated_week
   FROM bounds;
-- ops.mv_driver_lifecycle_weekly_kpis
CREATE MATERIALIZED VIEW ops.mv_driver_lifecycle_weekly_kpis AS
 WITH week_calendar AS (
         SELECT DISTINCT mv_driver_weekly_stats.week_start
           FROM ops.mv_driver_weekly_stats
        ), activations_week AS (
         SELECT date_trunc('week'::text, mv_driver_lifecycle_base.activation_ts)::date AS week_start,
            count(*) AS activations
           FROM ops.mv_driver_lifecycle_base
          WHERE mv_driver_lifecycle_base.activation_ts IS NOT NULL
          GROUP BY (date_trunc('week'::text, mv_driver_lifecycle_base.activation_ts)::date)
        ), active_drivers_week AS (
         SELECT mv_driver_weekly_stats.week_start,
            count(DISTINCT mv_driver_weekly_stats.driver_key) AS active_drivers
           FROM ops.mv_driver_weekly_stats
          GROUP BY mv_driver_weekly_stats.week_start
        ), churn_flow_week AS (
         SELECT w_1.week_start,
            count(DISTINCT w_1.driver_key) AS churn_flow
           FROM ops.mv_driver_weekly_stats w_1
          WHERE NOT (EXISTS ( SELECT 1
                   FROM ops.mv_driver_weekly_stats n
                  WHERE n.driver_key::text = w_1.driver_key::text AND n.week_start = (w_1.week_start + 7)))
          GROUP BY w_1.week_start
        ), reactivated_week AS (
         SELECT v_driver_weekly_churn_reactivation.week_start,
            count(*) AS reactivated
           FROM ops.v_driver_weekly_churn_reactivation
          WHERE v_driver_weekly_churn_reactivation.reactivated_week
          GROUP BY v_driver_weekly_churn_reactivation.week_start
        )
 SELECT w.week_start,
    COALESCE(ax.activations, 0::bigint) AS activations,
    COALESCE(ad.active_drivers, 0::bigint) AS active_drivers,
    COALESCE(cf.churn_flow, 0::bigint) AS churn_flow,
    COALESCE(rx.reactivated, 0::bigint) AS reactivated
   FROM week_calendar w
     LEFT JOIN activations_week ax ON ax.week_start = w.week_start
     LEFT JOIN active_drivers_week ad ON ad.week_start = w.week_start
     LEFT JOIN churn_flow_week cf ON cf.week_start = w.week_start
     LEFT JOIN reactivated_week rx ON rx.week_start = w.week_start;
WITH DATA;
-- ops.mv_driver_monthly_stats
CREATE MATERIALIZED VIEW ops.mv_driver_monthly_stats AS
 WITH month_trips AS (
         SELECT v_driver_lifecycle_trips_completed.conductor_id,
            date_trunc('month'::text, v_driver_lifecycle_trips_completed.completion_ts)::date AS month_start,
            v_driver_lifecycle_trips_completed.park_id,
            v_driver_lifecycle_trips_completed.tipo_servicio,
            v_driver_lifecycle_trips_completed.segment
           FROM ops.v_driver_lifecycle_trips_completed
        ), agg AS (
         SELECT month_trips.conductor_id,
            month_trips.month_start,
            count(*) AS trips_completed_month,
            min(month_trips.park_id::text) AS park_id_mode,
            min(month_trips.tipo_servicio::text) AS tipo_servicio_mode,
            min(month_trips.segment) AS segment_mode
           FROM month_trips
          GROUP BY month_trips.conductor_id, month_trips.month_start
        )
 SELECT agg.conductor_id AS driver_key,
    agg.month_start,
    agg.trips_completed_month,
        CASE
            WHEN agg.trips_completed_month >= 80 THEN 'FT'::text
            ELSE 'PT'::text
        END AS work_mode_month,
    agg.park_id_mode AS park_id,
    agg.tipo_servicio_mode AS tipo_servicio,
    agg.segment_mode AS segment,
    true AS is_active_month
   FROM agg;
WITH DATA;
-- ops.mv_driver_lifecycle_monthly_kpis
CREATE MATERIALIZED VIEW ops.mv_driver_lifecycle_monthly_kpis AS
 WITH month_calendar AS (
         SELECT DISTINCT mv_driver_monthly_stats.month_start
           FROM ops.mv_driver_monthly_stats
        ), activations_month AS (
         SELECT date_trunc('month'::text, mv_driver_lifecycle_base.activation_ts)::date AS month_start,
            count(*) AS activations
           FROM ops.mv_driver_lifecycle_base
          WHERE mv_driver_lifecycle_base.activation_ts IS NOT NULL
          GROUP BY (date_trunc('month'::text, mv_driver_lifecycle_base.activation_ts)::date)
        ), active_drivers_month AS (
         SELECT mv_driver_monthly_stats.month_start,
            count(DISTINCT mv_driver_monthly_stats.driver_key) AS active_drivers
           FROM ops.mv_driver_monthly_stats
          GROUP BY mv_driver_monthly_stats.month_start
        )
 SELECT m.month_start,
    COALESCE(ax.activations, 0::bigint) AS activations,
    COALESCE(ad.active_drivers, 0::bigint) AS active_drivers
   FROM month_calendar m
     LEFT JOIN activations_month ax ON ax.month_start = m.month_start
     LEFT JOIN active_drivers_month ad ON ad.month_start = m.month_start;
WITH DATA;
