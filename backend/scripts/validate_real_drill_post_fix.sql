-- =============================================================================
-- VALIDACIONES CRÍTICAS — Real LOB Drill (post 052)
-- Ejecutar después de: alembic upgrade head
-- Recomendado: SET statement_timeout = '120s';
-- =============================================================================

SET statement_timeout = '120s';

-- A) Flotas CO no nulas: distribución por park_bucket
SELECT park_bucket, COUNT(*) AS cnt
FROM ops.mv_real_rollup_day
WHERE country = 'co'
GROUP BY 1
ORDER BY 2 DESC;
-- Verificar: filas con park_bucket OK, SIN_PARK_ID, PARK_NO_CATALOG según esperado.

-- B) Country unk: cuántas filas quedan sin mapear
SELECT COUNT(*) AS unk_count
FROM ops.mv_real_rollup_day
WHERE country = 'unk';
-- Revisar ops.v_real_drill_unk_sample para detalle.

-- C) Márgenes no negativos (vista drill)
SELECT MIN(margin_total_pos) AS min_margin_total_pos,
       MIN(margin_unit_pos) AS min_margin_unit_pos
FROM ops.v_real_drill_country_month
WHERE trips > 0;
-- Esperado: ambos >= 0.

-- D) CO último mes por park (top 50 flotas activas)
SELECT park_id,
       park_name_resolved,
       park_bucket,
       SUM(trips) AS trips
FROM ops.v_real_drill_park_month
WHERE country = 'co'
  AND period_start >= date_trunc('month', CURRENT_DATE - interval '1 month')::date
GROUP BY park_id, park_name_resolved, park_bucket
ORDER BY trips DESC
LIMIT 50;
-- Verificar: aparecen todas las flotas activas esperadas.

-- =============================================================================
-- OPCIONAL: muestra de filas con country='unk'
-- =============================================================================
-- SELECT * FROM ops.v_real_drill_unk_sample LIMIT 20;

-- =============================================================================
-- REFRESH MV (recomendado diario)
-- =============================================================================
-- REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_rollup_day;
