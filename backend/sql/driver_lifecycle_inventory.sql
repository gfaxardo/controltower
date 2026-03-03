-- =============================================================================
-- DRIVER LIFECYCLE — INVENTARIO BD (solo lectura, NO hace cambios)
-- Ejecutar contra la base y guardar salida para auditoría.
-- =============================================================================

-- 1) MVs y views en schema ops
SELECT schemaname, matviewname FROM pg_matviews WHERE schemaname = 'ops' ORDER BY 2;

-- 2) Conteos (ejecutar cada una por separado; si no existe la MV, anotar "NO existe")
SELECT 'mv_driver_lifecycle_base' AS obj, COUNT(*) AS n FROM ops.mv_driver_lifecycle_base;
SELECT 'mv_driver_lifecycle_weekly_kpis' AS obj, COUNT(*) AS n FROM ops.mv_driver_lifecycle_weekly_kpis;
SELECT 'mv_driver_lifecycle_monthly_kpis' AS obj, COUNT(*) AS n FROM ops.mv_driver_lifecycle_monthly_kpis;
SELECT 'mv_driver_weekly_stats' AS obj, COUNT(*) AS n FROM ops.mv_driver_weekly_stats;
SELECT 'mv_driver_monthly_stats' AS obj, COUNT(*) AS n FROM ops.mv_driver_monthly_stats;
-- 2b) Cohortes (opcional; si no existen las MVs, omitir o comentar)
-- SELECT 'mv_driver_cohorts_weekly' AS obj, COUNT(*) AS n FROM ops.mv_driver_cohorts_weekly;
-- SELECT 'mv_driver_cohort_kpis' AS obj, COUNT(*) AS n FROM ops.mv_driver_cohort_kpis;

-- 3) Funciones refresh disponibles
SELECT n.nspname, p.proname
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'ops' AND p.proname ILIKE '%refresh_driver_lifecycle%'
ORDER BY 2;

-- 4) Columnas reales (information_schema)
SELECT table_name, column_name, data_type, ordinal_position
FROM information_schema.columns
WHERE table_schema = 'ops'
  AND table_name IN ('mv_driver_lifecycle_base', 'mv_driver_weekly_stats', 'mv_driver_lifecycle_weekly_kpis')
ORDER BY table_name, ordinal_position;

-- 5) Freshness + Park quality
SELECT MAX(last_completed_ts) AS max_last_completed_ts FROM ops.mv_driver_lifecycle_base;
SELECT COUNT(DISTINCT park_id) AS parks_distinct FROM ops.mv_driver_weekly_stats;
SELECT COUNT(*) AS total,
       COUNT(*) FILTER (WHERE park_id IS NULL) AS nulls,
       (COUNT(*) FILTER (WHERE park_id IS NULL)::float / NULLIF(COUNT(*), 0)) * 100 AS pct_null
FROM ops.mv_driver_weekly_stats;

-- 6) Viewdefs (solo lectura, para logs/auditoría)
-- Ejecutar y guardar en logs/ manualmente si se desea:
-- SELECT 'mv_driver_lifecycle_base' AS obj, pg_get_viewdef('ops.mv_driver_lifecycle_base'::regclass, true) AS def;
-- SELECT 'mv_driver_weekly_stats' AS obj, pg_get_viewdef('ops.mv_driver_weekly_stats'::regclass, true) AS def;
-- SELECT 'mv_driver_lifecycle_weekly_kpis' AS obj, pg_get_viewdef('ops.mv_driver_lifecycle_weekly_kpis'::regclass, true) AS def;
