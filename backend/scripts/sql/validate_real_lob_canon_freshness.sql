-- =============================================================================
-- Validación: Real LOB canon + freshness + drill (FASE 7)
-- Ejecutar tras: alembic upgrade head
-- =============================================================================

-- Canon: source_table, COUNT
SELECT '1) Canon: source_table, COUNT' AS paso;
SELECT source_table, COUNT(*) AS cnt
FROM ops.v_trips_real_canon
GROUP BY source_table
ORDER BY source_table;

-- Freshness
SELECT '2) Freshness (ops.v_real_freshness_trips)' AS paso;
SELECT * FROM ops.v_real_freshness_trips ORDER BY country;

-- Drill sin duplicados por breakdown (lob)
SELECT '3) Drill breakdown=lob: filas vs distinct dimension_key (debe coincidir)' AS paso;
SELECT period_start, country, COUNT(*) AS rows, COUNT(DISTINCT dimension_key) AS uniq
FROM ops.mv_real_drill_dim_agg
WHERE breakdown = 'lob' AND period_grain = 'month'
GROUP BY period_start, country
HAVING COUNT(*) <> COUNT(DISTINCT dimension_key)
LIMIT 20;
-- Si no devuelve filas: OK (1 fila por LOB por periodo+country+segment)

-- Service types
SELECT '4) Service types (breakdown=service_type)' AS paso;
SELECT DISTINCT dimension_key
FROM ops.mv_real_drill_dim_agg
WHERE breakdown = 'service_type'
ORDER BY dimension_key;

-- Consistencia: SUM(trips) del drill debe coincidir entre breakdowns (lob, park, service_type)
SELECT '5) Consistencia: SUM(trips) por breakdown debe coincidir para mismo periodo' AS paso;
WITH ref AS (
  SELECT country, period_grain, period_start, SUM(trips) AS total_trips
  FROM ops.mv_real_drill_dim_agg
  WHERE breakdown = 'lob'
  GROUP BY country, period_grain, period_start
  LIMIT 1
),
lob_sum AS (SELECT r.country, r.period_grain, r.period_start, SUM(d.trips) AS s FROM ops.mv_real_drill_dim_agg d JOIN ref r ON d.country=r.country AND d.period_grain=r.period_grain AND d.period_start=r.period_start AND d.breakdown='lob' GROUP BY r.country, r.period_grain, r.period_start),
park_sum AS (SELECT r.country, r.period_grain, r.period_start, SUM(d.trips) AS s FROM ops.mv_real_drill_dim_agg d JOIN ref r ON d.country=r.country AND d.period_grain=r.period_grain AND d.period_start=r.period_start AND d.breakdown='park' GROUP BY r.country, r.period_grain, r.period_start),
svc_sum AS (SELECT r.country, r.period_grain, r.period_start, SUM(d.trips) AS s FROM ops.mv_real_drill_dim_agg d JOIN ref r ON d.country=r.country AND d.period_grain=r.period_grain AND d.period_start=r.period_start AND d.breakdown='service_type' GROUP BY r.country, r.period_grain, r.period_start)
SELECT r.country, r.period_start, r.total_trips,
  l.s AS lob_trips, p.s AS park_trips, s.s AS service_type_trips,
  CASE WHEN r.total_trips = l.s AND l.s = p.s AND p.s = s.s THEN 'OK' ELSE 'REVISAR' END AS sanity
FROM ref r
LEFT JOIN lob_sum l ON r.country=l.country AND r.period_grain=l.period_grain AND r.period_start=l.period_start
LEFT JOIN park_sum p ON r.country=p.country AND r.period_grain=p.period_grain AND r.period_start=p.period_start
LEFT JOIN svc_sum s ON r.country=s.country AND r.period_grain=s.period_grain AND r.period_start=s.period_start;
