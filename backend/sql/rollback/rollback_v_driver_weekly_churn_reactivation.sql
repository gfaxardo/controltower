-- Rollback: DROP VIEW IF EXISTS ops.v_driver_weekly_churn_reactivation CASCADE;
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