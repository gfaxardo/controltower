-- =============================================================================
-- FASE 1 — Verificación de base de datos y vistas (REAL drill + margin quality)
-- Ejecutar en PostgreSQL y pegar resultados como evidencia.
-- =============================================================================

-- 1.1 Columna cancelled_trips en ops.real_drill_dim_fact
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'ops' AND table_name = 'real_drill_dim_fact'
ORDER BY ordinal_position;

-- 1.2 Tipo de objeto y columnas de ops.mv_real_drill_dim_agg (vista o MV)
SELECT c.column_name, c.data_type
FROM information_schema.columns c
WHERE c.table_schema = 'ops' AND c.table_name = 'mv_real_drill_dim_agg'
ORDER BY c.ordinal_position;

-- 1.3 ¿Existe cancelled_trips en mv_real_drill_dim_agg?
SELECT EXISTS (
  SELECT 1 FROM information_schema.columns
  WHERE table_schema = 'ops' AND table_name = 'mv_real_drill_dim_agg' AND column_name = 'cancelled_trips'
) AS mv_has_cancelled_trips;

-- 1.4 Tabla ops.real_margin_quality_audit
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'ops' AND table_name = 'real_margin_quality_audit'
) AS table_margin_quality_audit_exists;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'ops' AND table_name = 'real_margin_quality_audit'
ORDER BY ordinal_position;

-- 1.5 Vistas fuente: cancelled_trips en day_v2 y week_v3
SELECT 'mv_real_lob_day_v2' AS obj,
       EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'ops' AND table_name = 'mv_real_lob_day_v2' AND column_name = 'cancelled_trips') AS has_cancelled_trips
UNION ALL
SELECT 'mv_real_lob_week_v3',
       EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'ops' AND table_name = 'mv_real_lob_week_v3' AND column_name = 'cancelled_trips')
UNION ALL
SELECT 'mv_real_lob_month_v3',
       EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'ops' AND table_name = 'mv_real_lob_month_v3' AND column_name = 'cancelled_trips');

-- 1.6 Muestra real_drill_dim_fact: grain, filas recientes (sin cancelled_trips para no fallar si no existe)
SELECT period_grain, period_start, breakdown,
       COUNT(*) AS rows_count,
       SUM(trips) AS total_trips,
       SUM(margin_total) AS total_margin
FROM ops.real_drill_dim_fact
WHERE period_start >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY period_grain, period_start, breakdown
ORDER BY period_start DESC, breakdown
LIMIT 20;

-- 1.7 Solo si cancelled_trips existe en real_drill_dim_fact: muestra de valores no nulos
-- (Si falla con "column cancelled_trips does not exist", la columna no está en la tabla.)
-- SELECT period_grain, period_start, breakdown, dimension_key,
--        trips, cancelled_trips, margin_total
-- FROM ops.real_drill_dim_fact
-- WHERE period_start >= CURRENT_DATE - INTERVAL '14 days'
--   AND cancelled_trips IS NOT NULL AND cancelled_trips <> 0
-- LIMIT 10;
