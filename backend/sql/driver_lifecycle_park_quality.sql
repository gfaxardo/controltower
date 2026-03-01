-- =============================================================================
-- DRIVER LIFECYCLE — Quality Gate Park
-- null_share = % driver-weeks con park_id NULL.
-- Si null_share > 0.05 (5%): WARNING fuerte.
-- =============================================================================

SELECT
  COUNT(*) FILTER (WHERE park_id IS NULL) * 1.0 / NULLIF(COUNT(*), 0) AS null_share,
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE park_id IS NULL) AS null_count
FROM ops.mv_driver_weekly_stats;
