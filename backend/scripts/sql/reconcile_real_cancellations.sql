-- Reconciliación cancelaciones REAL: fuente raíz vs drill (FASE 5).
-- Ajustar :country y :period_start según datos. Ejecutar en psql con variables o sustituir manualmente.

-- Parámetros (sustituir o usar \set en psql)
-- \set country 'co'
-- \set period_start '2025-02-01'

-- 1) Cancelaciones en fuente raíz (trips_all + trips_2026) para el mes
WITH params AS (
    SELECT 'co'::text AS country, '2025-02-01'::date AS period_start
),
root_all AS (
    SELECT COUNT(*) FILTER (WHERE t.condicion = 'Completado') AS completed,
           COUNT(*) FILTER (WHERE t.condicion = 'Cancelado' OR t.condicion ILIKE '%cancel%') AS cancelled
    FROM public.trips_all t
    CROSS JOIN params p
    WHERE t.fecha_inicio_viaje >= p.period_start
      AND t.fecha_inicio_viaje < p.period_start + INTERVAL '1 month'
),
root_2026 AS (
    SELECT COUNT(*) FILTER (WHERE t.condicion = 'Completado') AS completed,
           COUNT(*) FILTER (WHERE t.condicion = 'Cancelado' OR t.condicion ILIKE '%cancel%') AS cancelled
    FROM public.trips_2026 t
    CROSS JOIN params p
    WHERE t.fecha_inicio_viaje >= p.period_start
      AND t.fecha_inicio_viaje < p.period_start + INTERVAL '1 month'
),
root_agg AS (
    SELECT
        (SELECT completed FROM root_all) + COALESCE((SELECT completed FROM root_2026), 0) AS completed,
        (SELECT cancelled FROM root_all) + COALESCE((SELECT cancelled FROM root_2026), 0) AS cancelled
),
-- 2) Drill fact mismo periodo (breakdown lob, país)
drill_agg AS (
    SELECT SUM(d.trips) AS completed, SUM(d.cancelled_trips) AS cancelled
    FROM ops.real_drill_dim_fact d
    CROSS JOIN params p
    WHERE d.country = p.country
      AND d.period_grain = 'month'
      AND d.period_start = p.period_start
      AND d.breakdown = 'lob'
)
SELECT 'root' AS layer, (SELECT completed FROM root_agg) AS completed, (SELECT cancelled FROM root_agg) AS cancelled
UNION ALL
SELECT 'drill_lob', (SELECT completed FROM drill_agg), (SELECT cancelled FROM drill_agg);
