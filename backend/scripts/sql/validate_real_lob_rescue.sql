-- =============================================================================
-- Validación: Real LOB modo incremental (rescue)
-- Ejecutar tras: alembic upgrade head
-- Si OK: python -m scripts.backfill_real_lob_mvs --from YYYY-MM-01 --to YYYY-MM-01
-- =============================================================================

-- 1) Coverage modo incremental (ops.v_real_lob_coverage)
SELECT '1) Coverage Real LOB (modo incremental)' AS paso;
SELECT min_trip_date_loaded, max_trip_date_loaded, recent_days_config, computed_at
FROM ops.v_real_lob_coverage;

-- 2) Temp usage (pg_stat_database)
SELECT '2) Temp usage pg_stat_database' AS paso;
SELECT datname, temp_files, pg_size_pretty(temp_bytes) AS temp_bytes
FROM pg_stat_database
WHERE datname = current_database();

-- 3) work_mem / maintenance_work_mem
SELECT '3) work_mem / maintenance_work_mem' AS paso;
SHOW work_mem;
SHOW maintenance_work_mem;

-- 4) Canon: source_table, COUNT
SELECT '4) Canon: source_table, COUNT' AS paso;
SELECT source_table, COUNT(*) AS cnt
FROM ops.v_trips_real_canon
GROUP BY source_table
ORDER BY source_table;

-- 5) Freshness
SELECT '5) Freshness (ops.v_real_freshness_trips)' AS paso;
SELECT * FROM ops.v_real_freshness_trips ORDER BY country;

-- 6) Drill breakdown=lob: sin duplicados (filas vs distinct dimension_key debe coincidir)
SELECT '6) Drill breakdown=lob: filas vs distinct (debe coincidir)' AS paso;
SELECT period_start, country, COUNT(*) AS rows, COUNT(DISTINCT dimension_key) AS uniq
FROM ops.mv_real_drill_dim_agg
WHERE breakdown = 'lob' AND period_grain = 'month'
GROUP BY period_start, country
HAVING COUNT(*) <> COUNT(DISTINCT dimension_key)
LIMIT 20;
-- Si vacío: OK

-- 7) Service type breakdown existe
SELECT '7) Service types (breakdown=service_type)' AS paso;
SELECT DISTINCT dimension_key
FROM ops.mv_real_drill_dim_agg
WHERE breakdown = 'service_type'
ORDER BY dimension_key;

-- 8) Consistencia SUM(trips) por breakdown (lob, park, service_type)
SELECT '8) Consistencia SUM(trips) por breakdown' AS paso;
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
