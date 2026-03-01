-- Rollback: DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_monthly_stats CASCADE;
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