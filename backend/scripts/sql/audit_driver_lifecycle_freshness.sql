-- =============================================================================
-- AUDITORÍA FRESHNESS: Driver Lifecycle
-- Compara MAX(last_completed_ts) en MV vs MAX(completion_ts) en trips_all
-- =============================================================================

-- 1) MAPEO trips_all: columnas timestamp/date
SELECT '1) Columnas timestamp en trips_all' AS paso;
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'trips_all'
  AND data_type IN ('timestamp without time zone', 'timestamp with time zone', 'date')
ORDER BY column_name;

-- 2) Columna status/condicion y valores
SELECT '2) Valores de condicion (top 30)' AS paso;
SELECT condicion, COUNT(*) AS cnt
FROM public.trips_all
GROUP BY condicion
ORDER BY cnt DESC
LIMIT 30;

-- 3) Candidatos completion_ts: fecha_finalizacion, fecha_inicio_viaje
SELECT '3) Stats por columna timestamp (trips Completado)' AS paso;
SELECT
  'fecha_finalizacion' AS col,
  MIN(fecha_finalizacion) AS min_val,
  MAX(fecha_finalizacion) AS max_val,
  COUNT(*) FILTER (WHERE fecha_finalizacion IS NULL) AS nulls,
  COUNT(*) AS total
FROM public.trips_all
WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
UNION ALL
SELECT
  'fecha_inicio_viaje',
  MIN(fecha_inicio_viaje),
  MAX(fecha_inicio_viaje),
  COUNT(*) FILTER (WHERE fecha_inicio_viaje IS NULL),
  COUNT(*)
FROM public.trips_all
WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
UNION ALL
SELECT
  'COALESCE(fecha_finalizacion, fecha_inicio_viaje)',
  MIN(COALESCE(fecha_finalizacion, fecha_inicio_viaje)),
  MAX(COALESCE(fecha_finalizacion, fecha_inicio_viaje)),
  COUNT(*) FILTER (WHERE COALESCE(fecha_finalizacion, fecha_inicio_viaje) IS NULL),
  COUNT(*)
FROM public.trips_all
WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL;

-- 4) MAX completion_ts FUENTE (trips_all con mismo filtro que v_driver_lifecycle_trips_completed)
SELECT '4) MAX completion_ts en FUENTE (trips_all)' AS paso;
SELECT MAX(COALESCE(fecha_finalizacion, fecha_inicio_viaje)) AS max_completion_ts_fuente
FROM public.trips_all
WHERE condicion = 'Completado'
  AND conductor_id IS NOT NULL
  AND fecha_inicio_viaje IS NOT NULL;

-- 5) MAX last_completed_ts en MV
SELECT '5) MAX last_completed_ts en MV' AS paso;
SELECT MAX(last_completed_ts) AS max_last_completed_ts_mv
FROM ops.mv_driver_lifecycle_base;

-- 6) COMPARACIÓN directa
SELECT '6) COMPARACIÓN' AS paso;
WITH fuente AS (
  SELECT MAX(COALESCE(fecha_finalizacion, fecha_inicio_viaje)) AS max_ts
  FROM public.trips_all
  WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
),
mv AS (
  SELECT MAX(last_completed_ts) AS max_ts FROM ops.mv_driver_lifecycle_base
)
SELECT
  f.max_ts AS fuente_max,
  m.max_ts AS mv_max,
  CASE WHEN f.max_ts = m.max_ts THEN 'OK' ELSE 'DIFERENCIA' END AS resultado,
  EXTRACT(EPOCH FROM (f.max_ts - m.max_ts)) AS diff_seconds
FROM fuente f, mv m;

-- 7) ¿Hay trips más recientes que el MAX de la MV? (trips fuera del scope)
SELECT '7) Trips con completion_ts > MAX(mv) (si hay, explicar)' AS paso;
SELECT COUNT(*) AS trips_mas_recientes_que_mv
FROM public.trips_all
WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
  AND COALESCE(fecha_finalizacion, fecha_inicio_viaje) > (SELECT MAX(last_completed_ts) FROM ops.mv_driver_lifecycle_base);

-- 8) Sample de esos trips (si existen)
SELECT '8) Sample trips más recientes que MV (top 5)' AS paso;
SELECT conductor_id, fecha_inicio_viaje, fecha_finalizacion,
       COALESCE(fecha_finalizacion, fecha_inicio_viaje) AS completion_ts,
       condicion
FROM public.trips_all
WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
  AND COALESCE(fecha_finalizacion, fecha_inicio_viaje) > (SELECT MAX(last_completed_ts) FROM ops.mv_driver_lifecycle_base)
ORDER BY COALESCE(fecha_finalizacion, fecha_inicio_viaje) DESC
LIMIT 5;
