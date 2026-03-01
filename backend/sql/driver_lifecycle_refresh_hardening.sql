-- =============================================================================
-- DRIVER LIFECYCLE — Hardening: refresh con timeout alto y lock_timeout
-- Ejecutar tras deploy. No destructivo (CREATE OR REPLACE).
-- =============================================================================

-- B) Función principal: CONCURRENTLY + statement_timeout 60min + lock_timeout 60s
CREATE OR REPLACE FUNCTION ops.refresh_driver_lifecycle_mvs()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  t0 timestamptz;
  t_start timestamptz := clock_timestamp();
BEGIN
  -- Evitar que un statement_timeout bajo de la sesión cancele el refresh
  PERFORM set_config('statement_timeout', '60min', true);
  -- Esperar locks hasta 5min (evitar fallo prematuro por lock_timeout)
  PERFORM set_config('lock_timeout', '5min', true);

  RAISE NOTICE '[driver_lifecycle] refresh start %', t_start;

  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_base;
  RAISE NOTICE '[driver_lifecycle] base: %s s', round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);

  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_weekly_stats;
  RAISE NOTICE '[driver_lifecycle] weekly_stats: %s s', round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);

  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_monthly_stats;
  RAISE NOTICE '[driver_lifecycle] monthly_stats: %s s', round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);

  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_weekly_kpis;
  RAISE NOTICE '[driver_lifecycle] weekly_kpis: %s s', round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);

  t0 := clock_timestamp();
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_monthly_kpis;
  RAISE NOTICE '[driver_lifecycle] monthly_kpis: %s s', round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);

  RAISE NOTICE '[driver_lifecycle] refresh done in % seconds',
    round(EXTRACT(EPOCH FROM (clock_timestamp() - t_start))::numeric, 1);
END;
$$;

-- C) Función fallback: NO CONCURRENTLY (más rápida, bloquea lecturas durante el refresh)
CREATE OR REPLACE FUNCTION ops.refresh_driver_lifecycle_mvs_nonc()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  t0 timestamptz := clock_timestamp();
BEGIN
  PERFORM set_config('statement_timeout', '60min', true);
  PERFORM set_config('lock_timeout', '5min', true);

  RAISE NOTICE '[driver_lifecycle NONC] refresh start %', t0;

  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_base;
  REFRESH MATERIALIZED VIEW ops.mv_driver_weekly_stats;
  REFRESH MATERIALIZED VIEW ops.mv_driver_monthly_stats;
  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_weekly_kpis;
  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_monthly_kpis;

  RAISE NOTICE '[driver_lifecycle NONC] refresh done in % seconds',
    round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);
END;
$$;

-- Variante: solo las 3 MVs principales (si weekly_stats y monthly_stats no existen)
CREATE OR REPLACE FUNCTION ops.refresh_driver_lifecycle_mvs_3only()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  t0 timestamptz := clock_timestamp();
BEGIN
  PERFORM set_config('statement_timeout', '60min', true);
  PERFORM set_config('lock_timeout', '5min', true);
  RAISE NOTICE '[driver_lifecycle 3only] refresh start %', t0;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_base;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_weekly_kpis;
  REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_lifecycle_monthly_kpis;
  RAISE NOTICE '[driver_lifecycle 3only] refresh done in % seconds',
    round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);
END;
$$;

CREATE OR REPLACE FUNCTION ops.refresh_driver_lifecycle_mvs_nonc_3only()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  t0 timestamptz := clock_timestamp();
BEGIN
  PERFORM set_config('statement_timeout', '60min', true);
  PERFORM set_config('lock_timeout', '5min', true);
  RAISE NOTICE '[driver_lifecycle NONC 3only] refresh start %', t0;
  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_base;
  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_weekly_kpis;
  REFRESH MATERIALIZED VIEW ops.mv_driver_lifecycle_monthly_kpis;
  RAISE NOTICE '[driver_lifecycle NONC 3only] refresh done in % seconds',
    round(EXTRACT(EPOCH FROM (clock_timestamp() - t0))::numeric, 1);
END;
$$;
