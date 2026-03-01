-- Ejecutar después de crear ops.mv_driver_cohorts_weekly y ops.mv_driver_cohort_kpis.
-- Añade refresh de cohort MVs a la función principal y nonc.

CREATE OR REPLACE FUNCTION ops.refresh_driver_lifecycle_mvs()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  t0 timestamptz := clock_timestamp();
BEGIN
  PERFORM set_config('statement_timeout', '60min', true);
  PERFORM set_config('lock_timeout', '60s', true);
  RAISE NOTICE '[driver_lifecycle] refresh start %', t0;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_base;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_weekly_stats;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_monthly_stats;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_weekly_kpis;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_monthly_kpis;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_cohorts_weekly;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_cohort_kpis;
  RAISE NOTICE '[driver_lifecycle] refresh done in % seconds', round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);
END;
$$;

CREATE OR REPLACE FUNCTION ops.refresh_driver_lifecycle_mvs_nonc()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  t0 timestamptz := clock_timestamp();
BEGIN
  PERFORM set_config('statement_timeout', '60min', true);
  PERFORM set_config('lock_timeout', '60s', true);
  RAISE NOTICE '[driver_lifecycle NONC] refresh start %', t0;
  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_base;
  REFRESH MATERIALIZED VIEW ops.mv_driver_weekly_stats;
  REFRESH MATERIALIZED VIEW ops.mv_driver_monthly_stats;
  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_weekly_kpis;
  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_monthly_kpis;
  REFRESH MATERIALIZED VIEW ops.mv_driver_cohorts_weekly;
  REFRESH MATERIALIZED VIEW ops.mv_driver_cohort_kpis;
  RAISE NOTICE '[driver_lifecycle NONC] refresh done in % seconds', round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);
END;
$$;
