-- =============================================================================
-- DRIVER LIFECYCLE — Validaciones post-refresh (checklist)
-- Ejecutar tras ops.refresh_driver_lifecycle_mvs() o _nonc().
-- =============================================================================

-- 1) Conteos por MV
SELECT 'mv_driver_lifecycle_base' AS mv_name, COUNT(*) AS filas FROM ops.mv_driver_lifecycle_base
UNION ALL
SELECT 'mv_driver_lifecycle_weekly_kpis', COUNT(*) FROM ops.mv_driver_lifecycle_weekly_kpis
UNION ALL
SELECT 'mv_driver_lifecycle_monthly_kpis', COUNT(*) FROM ops.mv_driver_lifecycle_monthly_kpis;

-- 2) Unicidad base (driver_key = PK)
SELECT
  COUNT(*) AS total,
  COUNT(DISTINCT driver_key) AS distinct_driver_key,
  CASE WHEN COUNT(*) = COUNT(DISTINCT driver_key) THEN 'OK' ELSE 'DUPLICADOS' END AS unicidad
FROM ops.mv_driver_lifecycle_base;

-- 3) Freshness (último dato en base)
SELECT MAX(last_completed_ts) AS last_completed_ts FROM ops.mv_driver_lifecycle_base;

-- 4) (Opcional) Rango de semanas/meses en KPIs
SELECT MIN(week_start) AS min_week, MAX(week_start) AS max_week FROM ops.mv_driver_lifecycle_weekly_kpis;
SELECT MIN(month_start) AS min_month, MAX(month_start) AS max_month FROM ops.mv_driver_lifecycle_monthly_kpis;
