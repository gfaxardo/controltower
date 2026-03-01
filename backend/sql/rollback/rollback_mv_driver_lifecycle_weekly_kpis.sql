-- Rollback: DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_lifecycle_weekly_kpis CASCADE;
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