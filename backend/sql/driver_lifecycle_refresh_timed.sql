-- =============================================================================
-- DRIVER LIFECYCLE — Refresh con benchmark (breakdown por paso)
-- Retorna tabla (step, duration_sec) para medición.
-- =============================================================================

CREATE OR REPLACE FUNCTION ops.refresh_driver_lifecycle_mvs_timed()
RETURNS TABLE(step text, duration_sec numeric)
LANGUAGE plpgsql
AS $$
DECLARE
  t0 timestamptz;
  t1 timestamptz;
BEGIN
  PERFORM set_config('statement_timeout', '60min', true);
  PERFORM set_config('lock_timeout', '60s', true);

  -- Base
  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_base;
  t1 := clock_timestamp();
  step := 'mv_driver_lifecycle_base'; duration_sec := round(EXTRACT(EPOCH FROM (t1 - t0))::numeric, 1);
  RETURN NEXT;

  -- Weekly stats
  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_weekly_stats;
  t1 := clock_timestamp();
  step := 'mv_driver_weekly_stats'; duration_sec := round(EXTRACT(EPOCH FROM (t1 - t0))::numeric, 1);
  RETURN NEXT;

  -- Monthly stats
  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_monthly_stats;
  t1 := clock_timestamp();
  step := 'mv_driver_monthly_stats'; duration_sec := round(EXTRACT(EPOCH FROM (t1 - t0))::numeric, 1);
  RETURN NEXT;

  -- Weekly KPIs
  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_weekly_kpis;
  t1 := clock_timestamp();
  step := 'mv_driver_lifecycle_weekly_kpis'; duration_sec := round(EXTRACT(EPOCH FROM (t1 - t0))::numeric, 1);
  RETURN NEXT;

  -- Monthly KPIs
  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_monthly_kpis;
  t1 := clock_timestamp();
  step := 'mv_driver_lifecycle_monthly_kpis'; duration_sec := round(EXTRACT(EPOCH FROM (t1 - t0))::numeric, 1);
  RETURN NEXT;

  -- Cohorts (si existen)
  IF EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname = 'ops' AND matviewname = 'mv_driver_cohorts_weekly') THEN
    t0 := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_cohorts_weekly;
    t1 := clock_timestamp();
    step := 'mv_driver_cohorts_weekly'; duration_sec := round(EXTRACT(EPOCH FROM (t1 - t0))::numeric, 1);
    RETURN NEXT;

    t0 := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_cohort_kpis;
    t1 := clock_timestamp();
    step := 'mv_driver_cohort_kpis'; duration_sec := round(EXTRACT(EPOCH FROM (t1 - t0))::numeric, 1);
    RETURN NEXT;
  END IF;
END;
$$;
