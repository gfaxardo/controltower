-- Rollback: DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_lifecycle_monthly_kpis CASCADE;
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