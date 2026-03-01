-- Rollback: DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_weekly_stats CASCADE;
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