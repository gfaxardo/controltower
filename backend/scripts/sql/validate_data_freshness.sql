-- Validación Freshness & Coverage (Fase G).
-- Ejecutar tras migración 072 y al menos una corrida de run_data_freshness_audit.

-- 1) Fuente base más fresca: trips_all vs trips_2026
SELECT '1) MAX fecha en fuentes base' AS paso;
SELECT 'trips_all' AS source_name, MAX(fecha_inicio_viaje)::date AS max_date FROM public.trips_all
UNION ALL
SELECT 'trips_2026', MAX(fecha_inicio_viaje)::date FROM public.trips_2026
WHERE EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'trips_2026');

-- 2) Real LOB: canon vs fact
SELECT '2) Real LOB: canon vs real_rollup_day_fact' AS paso;
SELECT MAX(fecha_inicio_viaje)::date AS canon_max FROM ops.v_trips_real_canon;
SELECT MAX(trip_day) AS rollup_max FROM ops.real_rollup_day_fact;
SELECT MAX(period_start) AS drill_max FROM ops.real_drill_dim_fact;

-- 3) Driver Lifecycle: trips_unified vs mv_driver_lifecycle_base
SELECT '3) Driver Lifecycle' AS paso;
SELECT MAX(completion_ts)::date AS source_max FROM ops.v_driver_lifecycle_trips_completed;
SELECT MAX(last_completed_ts)::date AS derived_max FROM ops.mv_driver_lifecycle_base;

-- 4) Supply: weekly
SELECT '4) Supply weekly' AS paso;
SELECT MAX(week_start) AS supply_weekly_max FROM ops.mv_supply_segments_weekly;

-- 5) Última auditoría (ops.data_freshness_audit)
SELECT '5) Última auditoría por dataset' AS paso;
SELECT dataset_name, source_max_date, derived_max_date, expected_latest_date, lag_days, status, alert_reason, checked_at
FROM ops.data_freshness_audit a
WHERE checked_at = (SELECT MAX(checked_at) FROM ops.data_freshness_audit)
ORDER BY dataset_name;

-- 6) Datasets con status distinto de OK (alertas)
SELECT '6) Alertas (status != OK)' AS paso;
SELECT dataset_name, status, alert_reason, source_max_date, derived_max_date
FROM ops.data_freshness_audit
WHERE checked_at = (SELECT MAX(checked_at) FROM ops.data_freshness_audit)
  AND status != 'OK'
ORDER BY dataset_name;
