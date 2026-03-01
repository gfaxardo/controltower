-- =============================================================================
-- DRIVER LIFECYCLE — Índices para optimizar cohort refresh
-- Ejecutar con autocommit (CREATE INDEX CONCURRENTLY no puede ir en transacción).
-- =============================================================================

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_weekly_stats_driver_week
  ON ops.mv_driver_weekly_stats (driver_key, week_start);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_weekly_stats_park_week
  ON ops.mv_driver_weekly_stats (park_id, week_start);

ANALYZE ops.mv_driver_weekly_stats;
